import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { readAdminAuthToken } from '../../core/auth-token.storage';
import { DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD } from './admin.mock';
import { AdminDomainError, AdminStateService } from './admin-state.service';

describe('AdminStateService', () => {
  let service: AdminStateService;

  beforeEach(() => {
    localStorage.clear();
    service = new AdminStateService();
  });

  it('authenticates valid admin credentials and persists isolated session', () => {
    expect(service.isAuthenticated()).toBe(false);

    const session = service.loginAdmin(DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD);

    expect(session.is_admin).toBe(true);
    expect(service.isAuthenticated()).toBe(true);
    expect(localStorage.getItem('ribbit-admin-session')).toContain(DEFAULT_ADMIN_EMAIL);

    const reloaded = new AdminStateService();
    expect(reloaded.currentAdmin()?.email).toBe(DEFAULT_ADMIN_EMAIL);

    reloaded.logoutAdmin();
    expect(reloaded.isAuthenticated()).toBe(false);
  });

  it('rejects wrong password and non-admin accounts on login', () => {
    expect(() => service.loginAdmin(DEFAULT_ADMIN_EMAIL, 'wrong-pass')).toThrowError(
      AdminDomainError,
    );
    expect(() => service.loginAdmin('joao.lucas@ribbit.app', 'RibbitUser123!')).toThrow(
      'Acesso restrito a administradores.',
    );
  });

  it('computes executive dashboard and audience metrics excluding family dependents from net revenue', () => {
    const dashboard = service.executiveDashboard();
    // 8 users total; titulars on paid plans: 3 Individual (3 * 14.9 = 44.7) + 1 Família (27.9) = 72.6
    expect(dashboard.total_users).toBe(8);
    expect(dashboard.estimated_net_revenue).toBe(72.6);
    expect(dashboard.users_by_plan['Família']).toBe(3);
    expect(dashboard.revenue_by_plan['Família']).toBe(27.9);

    const audience = service.audienceReport();
    expect(audience.total_tracks).toBe(7);
    expect(audience.active_tracks).toBe(5);
    expect(audience.blocked_genres['Sertanejo']).toBe(4);
  });

  it('promotes users to admin and prevents administrator self-demotion', () => {
    service.loginAdmin(DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD);

    const promoted = service.promoteUserToAdmin(3);
    expect(promoted.is_admin).toBe(true);
    expect(service.administrators().some((admin) => admin.user_id === 3)).toBe(true);

    expect(() => service.updateAdminRole(1, false)).toThrow(
      'Administrador não pode revogar o próprio acesso.',
    );

    const demoted = service.updateAdminRole(2, false);
    expect(demoted.is_admin).toBe(false);
  });

  it('updates plans and enforces unique name, non-negative price, and dependent capacity', () => {
    const updated = service.updatePlan(2, {
      new_name: 'Ribbit Individual Plus',
      new_price: 16.9,
      max_profiles: 2,
    });
    expect(updated.name).toBe('Ribbit Individual Plus');
    expect(updated.monthly_price).toBe(16.9);
    expect(service.executiveDashboard().estimated_net_revenue).toBe(78.6);

    expect(() => service.updatePlan(2, { new_name: '   ' })).toThrow(
      'O nome do plano é obrigatório.',
    );
    expect(() => service.updatePlan(2, { new_name: 'Free' })).toThrow(
      'Já existe um plano com esse nome.',
    );
    expect(() => service.updatePlan(2, { new_price: -5 })).toThrow(
      'O preço mensal não pode ser negativo.',
    );
    // Plan 3 (Família) has Carolina + 2 dependents = 3 occupied profiles
    expect(() => service.updatePlan(3, { max_profiles: 2 })).toThrow(
      'O limite não pode ser menor que os perfis já vinculados.',
    );
  });

  it('searches active tracks, toggles block/explicit flags, deletes reviews, and resets demo state', () => {
    expect(service.searchCatalogTracks('Liniker').length).toBe(1);

    service.setTrackBlocked(103, true);
    expect(service.blockedTracks().some((track) => track.track_id === 103)).toBe(true);
    expect(service.searchCatalogTracks('Liniker').length).toBe(0);

    service.setTrackExplicit(101, true);
    expect(service.activeTracks().find((track) => track.track_id === 101)?.explicit).toBe(true);

    const initialReviews = service.topModerationReviews().length;
    service.deleteReview(503);
    expect(service.topModerationReviews().length).toBe(initialReviews - 1);

    service.resetDemoData();
    expect(service.topModerationReviews().length).toBe(initialReviews);
    expect(service.activeTracks().length).toBe(5);
  });

  it('updates track genre and validates input with offline fallback', () => {
    expect(() => service.updateTrackGenre(101, '   ')).toThrow('O gênero da faixa é obrigatório.');

    service.updateTrackGenre(101, 'Indie Psychedelic').subscribe((res) => {
      expect(res.track_id).toBe(101);
      expect(res.genre).toBe('Indie Psychedelic');
    });

    const track = service.activeTracks().find((t) => t.track_id === 101);
    expect(track?.genre).toBe('Indie Psychedelic');
  });

  it('compacts and synchronizes catalog delta tables with fallback', () => {
    service.compactCatalog().subscribe((res) => {
      expect(res.new_version).toBeTypeOf('number');
      expect(res.message).toContain('compactado com sucesso');
    });

    service.syncCatalog().subscribe((res) => {
      expect(res.synced).toBe(true);
      expect(res.version).toBeTypeOf('number');
      expect(res.message).toContain('sincronizado com sucesso');
    });
    expect(service.isUsingLocalFallback()).toBe(true);
    expect(service.dataSourceMode()).toBe('local-fallback');
  });
});

describe('AdminStateService (HTTP integration with /api/admin/*)', () => {
  let service: AdminStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AdminStateService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('authenticates via POST /api/admin/login, stores token, and hydrates all /api/admin/* datasets', () => {
    expect(service.isUsingLocalFallback()).toBe(false);

    let authenticatedEmail = '';
    service.loginAdminWithApi('admin@ribbit.app', 'secret123').subscribe((session) => {
      authenticatedEmail = session.email;
    });

    const loginReq = httpMock.expectOne('/api/admin/login');
    expect(loginReq.request.method).toBe('POST');
    loginReq.flush({
      access_token: 'admin-jwt-token',
      token_type: 'bearer',
      user: {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Real',
        age: 30,
        plan_id: 1,
        is_admin: true,
      },
    });

    expect(authenticatedEmail).toBe('admin@ribbit.app');
    expect(readAdminAuthToken()).toBe('admin-jwt-token');

    httpMock.expectOne('/api/admin/plans').flush([
      { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
      { plan_id: 2, name: 'Individual', monthly_price: 19.9, max_profiles: 1 },
    ]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 42,
      estimated_net_revenue: 199.0,
      users_by_plan: { Free: 32, Individual: 10 },
      revenue_by_plan: { Free: 0, Individual: 199.0 },
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 42,
      total_tracks: 120,
      active_tracks: 115,
      blocked_genres: { Sertanejo: 7, Funk: 3 },
    });
    httpMock.expectOne('/api/admin/users').flush([
      {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Real',
        age: 30,
        plan_name: 'Free',
        is_admin: true,
      },
      {
        user_id: 2,
        email: 'listener@ribbit.app',
        display_name: 'Ouvinte Pro',
        age: 24,
        plan_name: 'Individual',
        is_admin: false,
      },
    ]);
    httpMock.expectOne('/api/admin/administrators').flush([
      {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Real',
        age: 30,
        plan_id: 1,
        is_admin: true,
      },
    ]);
    httpMock.expectOne('/api/tracks/search?limit=100').flush([
      {
        track_id: 500,
        title: 'Evidências',
        artist: 'Chitãozinho & Xororó',
        duration_seconds: 280,
        genre: 'Sertanejo',
        explicit: false,
        is_deleted: false,
      },
    ]);
    httpMock.expectOne('/api/admin/blocked-tracks').flush([
      {
        track_id: 501,
        title: 'Faixa Bloqueada',
        artist: 'Artista X',
        duration_seconds: 180,
        genre: 'Pop',
        explicit: true,
        is_deleted: true,
      },
    ]);
    httpMock.expectOne('/api/admin/reviews').flush([
      {
        review_id: 900,
        user_id: 2,
        track_id: 500,
        rating: 5,
        text: 'Clássico absoluto!',
        likes_count: 15,
        is_deleted: false,
      },
    ]);

    expect(service.isUsingLocalFallback()).toBe(false);
    expect(service.dataSourceMode()).toBe('api');
    expect(service.executiveDashboard().total_users).toBe(42);
    expect(service.executiveDashboard().estimated_net_revenue).toBe(199.0);
    expect(service.audienceReport().total_tracks).toBe(120);
    expect(service.blockedGenreRanking()[0]?.genre).toBe('Sertanejo');
    expect(service.usersWithPlans().length).toBe(2);
    expect(service.activeTracks().length).toBe(1);
    expect(service.blockedTracks().length).toBe(1);
    expect(service.topModerationReviews()[0]?.author_name).toBe('Ouvinte Pro');
  });

  it('sends PUT requests for plan, admin role, track block/explicit, and switches to explicit fallback on network error', () => {
    service.updatePlan(2, { new_name: 'Ribbit Pro+', new_price: 21.9, max_profiles: 1 });
    const planReq = httpMock.expectOne('/api/admin/plans/2');
    expect(planReq.request.method).toBe('PUT');
    planReq.flush({ plan_id: 2, name: 'Ribbit Pro+', monthly_price: 21.9, max_profiles: 1 });
    expect(service.isUsingLocalFallback()).toBe(false);

    service.promoteUserToAdmin(3);
    const roleReq = httpMock.expectOne('/api/admin/administrators/3');
    expect(roleReq.request.method).toBe('PUT');
    expect(roleReq.request.body).toEqual({ is_admin: true });
    roleReq.error(new ProgressEvent('error'));

    expect(service.isUsingLocalFallback()).toBe(true);
    expect(service.fallbackReason()).toContain('/api/admin/administrators/3');
  });

  it('preserves existing activeTracks when fetchCatalogTracksFromBackend(query) returns empty results while blocked tracks exist', () => {
    const initialActiveCount = service.activeTracks().length;
    expect(initialActiveCount).toBeGreaterThan(0);
    expect(service.blockedTracks().length).toBeGreaterThan(0);

    service.fetchCatalogTracksFromBackend('no-match-query').subscribe();
    const searchReq = httpMock.expectOne('/api/tracks/search?limit=50&query=no-match-query');
    searchReq.flush([]);

    expect(service.activeTracks().length).toBe(initialActiveCount);
  });

  it('marks isUsingLocalFallback as true when an admin session is restored from localStorage without an admin JWT token', () => {
    localStorage.setItem(
      'ribbit-admin-session',
      JSON.stringify({
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Local',
        is_admin: true,
      }),
    );
    localStorage.removeItem('ribbit-admin-token');

    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const restoredService = TestBed.inject(AdminStateService);
    httpMock = TestBed.inject(HttpTestingController);

    expect(restoredService.isAuthenticated()).toBe(true);
    expect(restoredService.isUsingLocalFallback()).toBe(true);
    expect(restoredService.dataSourceMode()).toBe('local-fallback');
  });
});
