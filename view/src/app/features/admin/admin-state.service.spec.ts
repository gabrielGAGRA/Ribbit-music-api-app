import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AuthSessionNotifier } from '../../core/auth-session.notifier';
import { readAdminAuthToken, writeAdminAuthToken } from '../../core/auth-token.storage';
import { AdminDomainError, AdminStateService } from './admin-state.service';

describe('AdminStateService', () => {
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
    service.ngOnDestroy();
  });

  function flushHydration(overrides?: {
    activeTracks?: unknown[];
    blockedTracks?: unknown[];
    reviews?: unknown[];
  }): void {
    httpMock.expectOne('/api/admin/plans').flush([
      { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
      { plan_id: 2, name: 'Individual', monthly_price: 19.9, max_profiles: 1 },
      { plan_id: 3, name: 'Família', monthly_price: 29.9, max_profiles: 6 },
    ]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 42,
      estimated_net_revenue: 228.9,
      users_by_plan: { Free: 31, Individual: 10, Família: 1 },
      revenue_by_plan: { Free: 0, Individual: 199.0, Família: 29.9 },
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
    httpMock.expectOne('/api/admin/tracks?limit=100').flush(
      overrides?.activeTracks ?? [
        {
          track_id: 500,
          title: 'Evidências',
          artist: 'Chitãozinho & Xororó',
          duration_seconds: 280,
          genre: 'Sertanejo',
          explicit: false,
          is_deleted: false,
        },
      ],
    );
    httpMock.expectOne('/api/admin/blocked-tracks').flush(
      overrides?.blockedTracks ?? [
        {
          track_id: 501,
          title: 'Faixa Bloqueada',
          artist: 'Artista X',
          duration_seconds: 180,
          genre: 'Pop',
          explicit: true,
          is_deleted: true,
        },
      ],
    );
    httpMock.expectOne('/api/admin/reviews').flush(
      overrides?.reviews ?? [
        {
          review_id: 900,
          user_id: 2,
          track_id: 500,
          rating: 5,
          text: 'Clássico absoluto!',
          likes_count: 15,
          is_deleted: false,
          author_name: 'Ouvinte Pro',
          track_title: 'Evidências',
          track_artist: 'Chitãozinho & Xororó',
        },
      ],
    );
  }

  it('starts unauthenticated without mock data and authenticates via POST /api/admin/login', () => {
    expect(service.isAuthenticated()).toBe(false);
    expect(service.plans().length).toBe(0);
    expect(service.usersWithPlans().length).toBe(0);
    expect(service.activeTracks().length).toBe(0);

    let authenticatedEmail = '';
    service.loginAdmin('admin@ribbit.app', 'secret123').subscribe((session) => {
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
    expect(service.isAuthenticated()).toBe(true);
    expect(readAdminAuthToken()).toBe('admin-jwt-token');

    flushHydration();

    expect(service.hasHydrated()).toBe(true);
    expect(service.executiveDashboard().total_users).toBe(42);
    expect(service.executiveDashboard().estimated_net_revenue).toBe(228.9);
    expect(service.audienceReport().total_tracks).toBe(120);
    expect(service.blockedGenreRanking()[0]?.genre).toBe('Sertanejo');
    expect(service.usersWithPlans().length).toBe(2);
    expect(service.activeTracks().length).toBe(1);
    expect(service.blockedTracks().length).toBe(1);
    expect(service.topModerationReviews()[0]?.author_name).toBe('Ouvinte Pro');
  });

  it('surfaces backend authentication errors without falling back to local mocks', () => {
    let capturedError: unknown;
    service.loginAdmin('admin@ribbit.app', 'wrong-pass').subscribe({
      error: (err: unknown) => {
        capturedError = err;
      },
    });

    const loginReq = httpMock.expectOne('/api/admin/login');
    loginReq.flush(
      { error: 'AuthenticationRequiredError', message: 'Invalid credentials.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(service.isAuthenticated()).toBe(false);
    expect(capturedError).toBeInstanceOf(AdminDomainError);
    expect((capturedError as AdminDomainError).message).toBe('Invalid credentials.');
  });

  it('drops restored session if admin JWT token is missing and clears session on 401 notification', () => {
    localStorage.setItem(
      'ribbit-admin-session',
      JSON.stringify({
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Local',
        is_admin: true,
      }),
    );

    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const restoredWithoutToken = TestBed.inject(AdminStateService);
    expect(restoredWithoutToken.isAuthenticated()).toBe(false);
    restoredWithoutToken.ngOnDestroy();

    writeAdminAuthToken('valid-token');
    localStorage.setItem(
      'ribbit-admin-session',
      JSON.stringify({
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Local',
        is_admin: true,
      }),
    );

    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const restoredWithToken = TestBed.inject(AdminStateService);
    const activeNotifier = TestBed.inject(AuthSessionNotifier);
    expect(restoredWithToken.isAuthenticated()).toBe(true);

    activeNotifier.notifyAdminUnauthorized();
    expect(restoredWithToken.isAuthenticated()).toBe(false);
    expect(localStorage.getItem('ribbit-admin-session')).toBeNull();
    restoredWithToken.ngOnDestroy();
  });

  it('registers new administrator via POST /api/admin/administrators and refreshes metrics', () => {
    service.hydrateFromBackend();
    flushHydration();

    let createdEmail = '';
    service
      .registerAdministrator({
        email: 'novo@usp.br',
        password: 'password123',
        display_name: 'Novo Admin',
        age: 29,
      })
      .subscribe((user) => {
        createdEmail = user.email;
      });

    const postReq = httpMock.expectOne('/api/admin/administrators');
    expect(postReq.request.method).toBe('POST');
    expect(postReq.request.body).toEqual({
      email: 'novo@usp.br',
      password: 'password123',
      display_name: 'Novo Admin',
      age: 29,
    });
    postReq.flush({
      user_id: 9,
      email: 'novo@usp.br',
      display_name: 'Novo Admin',
      age: 29,
      plan_id: 1,
      is_admin: true,
    });

    expect(createdEmail).toBe('novo@usp.br');
    expect(service.administrators().some((a) => a.user_id === 9)).toBe(true);

    httpMock.expectOne('/api/admin/users').flush([]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 43,
      estimated_net_revenue: 228.9,
      users_by_plan: { Free: 32, Individual: 10, Família: 1 },
      revenue_by_plan: { Free: 0, Individual: 199.0, Família: 29.9 },
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 43,
      total_tracks: 120,
      active_tracks: 115,
      blocked_genres: {},
    });
  });

  it('updates admin role via PUT /api/admin/administrators/{id} and prevents self-demotion', () => {
    service.loginAdmin('admin@ribbit.app', 'secret123').subscribe();
    httpMock.expectOne('/api/admin/login').flush({
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
    flushHydration();

    let selfErr: unknown;
    service.updateAdminRole(1, false).subscribe({
      error: (err: unknown) => {
        selfErr = err;
      },
    });
    expect(selfErr).toBeInstanceOf(AdminDomainError);
    expect((selfErr as AdminDomainError).message).toContain('revogar o próprio acesso');

    service.promoteUserToAdmin(2).subscribe();
    const promoteReq = httpMock.expectOne('/api/admin/administrators/2');
    expect(promoteReq.request.method).toBe('PUT');
    expect(promoteReq.request.body).toEqual({ is_admin: true });
    promoteReq.flush({
      user_id: 2,
      email: 'listener@ribbit.app',
      display_name: 'Ouvinte Pro',
      age: 24,
      plan_id: 2,
      is_admin: true,
    });
    expect(service.administrators().some((a) => a.user_id === 2)).toBe(true);
    expect(service.usersWithPlans().find((u) => u.user_id === 2)?.is_admin).toBe(true);
  });

  it('updates plans via PUT /api/admin/plans/{id} and refreshes dashboard metrics', () => {
    service.hydrateFromBackend();
    flushHydration();

    service
      .updatePlan(2, { new_name: 'Ribbit Pro+', new_price: 21.9, max_profiles: 2 })
      .subscribe();

    const planReq = httpMock.expectOne('/api/admin/plans/2');
    expect(planReq.request.method).toBe('PUT');
    expect(planReq.request.body).toEqual({
      new_name: 'Ribbit Pro+',
      new_price: 21.9,
      max_profiles: 2,
    });
    planReq.flush({ plan_id: 2, name: 'Ribbit Pro+', monthly_price: 21.9, max_profiles: 2 });

    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 42,
      estimated_net_revenue: 248.9,
      users_by_plan: { Free: 31, 'Ribbit Pro+': 10, Família: 1 },
      revenue_by_plan: { Free: 0, 'Ribbit Pro+': 219.0, Família: 29.9 },
    });
    httpMock.expectOne('/api/admin/users').flush([]);

    expect(service.plans().find((p) => p.plan_id === 2)?.name).toBe('Ribbit Pro+');
    expect(service.executiveDashboard().estimated_net_revenue).toBe(248.9);
  });

  it('handles track search, block/restore, explicit, genre, compact, sync, and review delete errors', () => {
    service.hydrateFromBackend();
    flushHydration();

    service.fetchCatalogTracksFromBackend('no-match').subscribe();
    const searchReq = httpMock.expectOne('/api/admin/tracks?limit=100&query=no-match');
    searchReq.flush([]);
    expect(service.activeTracks().length).toBe(0);

    service.fetchCatalogTracksFromBackend('').subscribe();
    httpMock.expectOne('/api/admin/tracks?limit=100').flush([
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
    expect(service.activeTracks().length).toBe(1);

    service.setTrackBlocked(500, true).subscribe();
    const blockReq = httpMock.expectOne('/api/admin/tracks/500/block');
    expect(blockReq.request.method).toBe('PUT');
    blockReq.flush({ track_id: 500, blocked: true });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 42,
      total_tracks: 120,
      active_tracks: 114,
      blocked_genres: {},
    });
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 42,
      estimated_net_revenue: 500,
      users_by_plan: {},
      revenue_by_plan: {},
    });
    expect(service.activeTracks().length).toBe(0);
    expect(service.blockedTracks().some((t) => t.track_id === 500)).toBe(true);

    let compactError: unknown;
    service.compactCatalog().subscribe({
      error: (err: unknown) => {
        compactError = err;
      },
    });
    httpMock
      .expectOne('/api/admin/catalog/compact')
      .flush(
        { error: 'ExternalServiceError', message: 'Catalog file storage is not configured.' },
        { status: 503, statusText: 'Service Unavailable' },
      );
    expect(compactError).toBeInstanceOf(AdminDomainError);
    expect((compactError as AdminDomainError).message).toBe(
      'Catalog file storage is not configured.',
    );

    let deleteReviewError: unknown;
    service.deleteReview(900).subscribe({
      error: (err: unknown) => {
        deleteReviewError = err;
      },
    });
    httpMock
      .expectOne('/api/admin/reviews/900')
      .flush(
        { error: 'EntityNotFoundError', message: 'Review with ID 900 not found.' },
        { status: 404, statusText: 'Not Found' },
      );
    expect(deleteReviewError).toBeInstanceOf(AdminDomainError);
    expect((deleteReviewError as AdminDomainError).message).toBe('Review with ID 900 not found.');
  });

  it('cancels in-flight hydration when logoutAdmin is called before requests settle', () => {
    service.loginAdmin('admin@ribbit.app', 'secret123').subscribe();
    httpMock.expectOne('/api/admin/login').flush({
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

    const pendingPlans = httpMock.expectOne('/api/admin/plans');
    const pendingDashboard = httpMock.expectOne('/api/admin/dashboard');
    const pendingAudience = httpMock.expectOne('/api/admin/audience');
    const pendingUsers = httpMock.expectOne('/api/admin/users');
    const pendingAdmins = httpMock.expectOne('/api/admin/administrators');
    const pendingTracks = httpMock.expectOne('/api/admin/tracks?limit=100');
    const pendingBlocked = httpMock.expectOne('/api/admin/blocked-tracks');
    const pendingReviews = httpMock.expectOne('/api/admin/reviews');

    service.logoutAdmin();

    expect(pendingPlans.cancelled).toBe(true);
    expect(pendingDashboard.cancelled).toBe(true);
    expect(pendingAudience.cancelled).toBe(true);
    expect(pendingUsers.cancelled).toBe(true);
    expect(pendingAdmins.cancelled).toBe(true);
    expect(pendingTracks.cancelled).toBe(true);
    expect(pendingBlocked.cancelled).toBe(true);
    expect(pendingReviews.cancelled).toBe(true);
    expect(service.isAuthenticated()).toBe(false);
    expect(service.hasHydrated()).toBe(false);
    expect(service.isLoading()).toBe(false);
  });

  it('loads admin catalog with sortBy/minDislikes and normalizes track metrics', () => {
    service
      .loadAdminCatalog({
        query: 'Rock',
        sortBy: 'dislikes_desc',
        minDislikes: 2,
      })
      .subscribe((tracks) => {
        expect(tracks.length).toBe(1);
        expect(tracks[0]?.dislikes_count).toBe(5);
        expect(tracks[0]?.likes_count).toBe(0);
      });

    const req = httpMock.expectOne(
      '/api/admin/tracks?limit=100&query=Rock&sort_by=dislikes_desc&min_dislikes=2',
    );
    expect(req.request.method).toBe('GET');
    req.flush([
      {
        track_id: 12,
        title: 'Heavy Riff',
        artist: 'Band',
        duration_seconds: 220,
        genre: 'Rock',
        explicit: false,
        is_deleted: false,
        dislikes_count: 5,
      },
    ]);
  });
});
