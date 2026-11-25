import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AdminStateService } from '../admin-state.service';
import { AdminUsersComponent } from './admin-users.component';

describe('AdminUsersComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('filters users by search and plan, promotes listeners, registers admins, and blocks self-demotion', () => {
    const state = TestBed.inject(AdminStateService);
    state.loginAdmin('admin@ribbit.app', 'secret123').subscribe();
    httpMock.expectOne('/api/admin/login').flush({
      access_token: 'admin-jwt',
      token_type: 'bearer',
      user: {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Principal',
        age: 30,
        plan_id: 1,
        is_admin: true,
      },
    });
    httpMock.expectOne('/api/admin/plans').flush([
      { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
      { plan_id: 2, name: 'Individual', monthly_price: 14.9, max_profiles: 1 },
      { plan_id: 3, name: 'Família', monthly_price: 27.9, max_profiles: 6 },
    ]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 3,
      estimated_net_revenue: 42.8,
      users_by_plan: { Free: 1, Individual: 1, Família: 1 },
      revenue_by_plan: { Free: 0, Individual: 14.9, Família: 27.9 },
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 3,
      total_tracks: 0,
      active_tracks: 0,
      blocked_genres: {},
    });
    httpMock.expectOne('/api/admin/users').flush([
      {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Principal',
        age: 30,
        plan_name: 'Free',
        is_admin: true,
      },
      {
        user_id: 2,
        email: 'gabriel.agra@usp.br',
        display_name: 'Gabriel Agra',
        age: 24,
        plan_name: 'Individual',
        is_admin: false,
      },
      {
        user_id: 3,
        email: 'familia@ribbit.app',
        display_name: 'Conta Família',
        age: 34,
        plan_name: 'Família',
        is_admin: false,
      },
    ]);
    httpMock.expectOne('/api/admin/administrators').flush([
      {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Principal',
        age: 30,
        plan_id: 1,
        is_admin: true,
      },
    ]);
    httpMock.expectOne('/api/admin/tracks?limit=100').flush([]);
    httpMock.expectOne('/api/admin/blocked-tracks').flush([]);
    httpMock.expectOne('/api/admin/reviews').flush([]);

    const component = TestBed.runInInjectionContext(() => new AdminUsersComponent());

    expect(component['filteredUsers']().length).toBe(3);

    component['selectedPlanFilter'].set('Família');
    expect(component['filteredUsers']().length).toBe(1);

    component['selectedPlanFilter'].set('all');
    component['searchQuery'].set('gabriel');
    expect(component['filteredUsers']().length).toBe(1);

    component['promoteUser'](2);
    const promoteReq = httpMock.expectOne('/api/admin/administrators/2');
    expect(promoteReq.request.method).toBe('PUT');
    expect(promoteReq.request.body).toEqual({ is_admin: true });
    promoteReq.flush({
      user_id: 2,
      email: 'gabriel.agra@usp.br',
      display_name: 'Gabriel Agra',
      age: 24,
      plan_id: 2,
      is_admin: true,
    });
    expect(state.administrators().some((admin) => admin.userId === 2)).toBe(true);

    component['selectTab']('admins');
    component['searchQuery'].set('');
    expect(component['filteredAdministrators']().length).toBe(2);

    component['revokeAdmin'](1);
    expect(component['actionError']()).toContain('revogar o próprio acesso');

    component['revokeAdmin'](2);
    const revokeReq = httpMock.expectOne('/api/admin/administrators/2');
    expect(revokeReq.request.method).toBe('PUT');
    expect(revokeReq.request.body).toEqual({ is_admin: false });
    revokeReq.flush({
      user_id: 2,
      email: 'gabriel.agra@usp.br',
      display_name: 'Gabriel Agra',
      age: 24,
      plan_id: 2,
      is_admin: false,
    });
    expect(component['actionError']()).toBe('');
    expect(state.administrators().some((admin) => admin.userId === 2)).toBe(false);

    component['toggleRegisterForm']();
    component['newAdminName'].set('Fernando Seraco');
    component['newAdminEmail'].set('fernando.seraco@usp.br');
    component['newAdminPassword'].set('secret123');
    component['newAdminAge'].set('28');
    component['submitRegisterAdmin'](new Event('submit'));

    const registerReq = httpMock.expectOne('/api/admin/administrators');
    expect(registerReq.request.method).toBe('POST');
    expect(registerReq.request.body).toEqual({
      email: 'fernando.seraco@usp.br',
      password: 'secret123',
      display_name: 'Fernando Seraco',
      age: 28,
    });
    registerReq.flush({
      user_id: 4,
      email: 'fernando.seraco@usp.br',
      display_name: 'Fernando Seraco',
      age: 28,
      plan_id: 1,
      is_admin: true,
    });

    httpMock.expectOne('/api/admin/users').flush([]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 4,
      estimated_net_revenue: 42.8,
      users_by_plan: { Free: 2, Individual: 1, Família: 1 },
      revenue_by_plan: { Free: 0, Individual: 14.9, Família: 27.9 },
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 4,
      total_tracks: 0,
      active_tracks: 0,
      blocked_genres: {},
    });

    expect(component['showRegisterForm']()).toBe(false);
    expect(state.administrators().some((admin) => admin.userId === 4)).toBe(true);
  });

  it('loads and filters global access history on the 3rd tab including soft-deleted tracks', () => {
    const state = TestBed.inject(AdminStateService);
    const component = TestBed.runInInjectionContext(() => new AdminUsersComponent());

    component['selectTab']('access-history');
    const req = httpMock.expectOne('/api/admin/access-history?limit=100');
    req.flush([
      {
        access_id: 1,
        user_id: 2,
        user_display_name: 'Gabriel Agra',
        user_email: 'gabriel.agra@usp.br',
        track_id: 593,
        track_title: 'Faixa Removida',
        track_artist: 'Ribbit Archive',
        track_genre: 'Pop',
        track_is_deleted: true,
        source: 'play',
        accessed_at: '2026-02-01T10:12:00+00:00',
      },
    ]);

    expect(component['filteredAccessHistory']().length).toBe(1);
    expect(component['filteredAccessHistory']()[0]?.trackIsDeleted).toBe(true);

    component['toggleAccessOnlyDeleted']({
      target: { checked: true },
    } as unknown as Event);
    const filteredReq = httpMock.expectOne('/api/admin/access-history?limit=100&only_deleted=true');
    filteredReq.flush([]);
    expect(state.accessHistory().length).toBe(0);
  });

  it('updates search, plan filter, new admin form drafts, and formats access timestamps', () => {
    const component = TestBed.runInInjectionContext(() => new AdminUsersComponent());

    const input = document.createElement('input');
    input.value = 'alice';
    component['updateSearch']({ target: input } as unknown as Event);
    expect(component['searchQuery']()).toBe('alice');

    const select = document.createElement('select');
    select.innerHTML = '<option value="Pro">Pro</option>';
    select.value = 'Pro';
    component['updatePlanFilter']({ target: select } as unknown as Event);
    expect(component['selectedPlanFilter']()).toBe('Pro');

    input.value = 'Alice';
    component['updateNewAdminName']({ target: input } as unknown as Event);
    input.value = 'alice@ribbit.app';
    component['updateNewAdminEmail']({ target: input } as unknown as Event);
    input.value = 'pass123';
    component['updateNewAdminPassword']({ target: input } as unknown as Event);
    input.value = '25';
    component['updateNewAdminAge']({ target: input } as unknown as Event);

    expect(component['formatAccessTimestamp']('2026-02-01T10:12:00Z')).toBeTruthy();
    expect(component['isCurrentSessionUser'](999)).toBe(false);

    component['newAdminName'].set('A');
    component['submitRegisterAdmin'](new Event('submit'));
    expect(component['registerError']()).toBeTruthy();

    component['promoteUser'](99);
    httpMock
      .expectOne('/api/admin/administrators/99')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });
    expect(component['actionError']()).toBeTruthy();

    component['revokeAdmin'](99);
    httpMock
      .expectOne('/api/admin/administrators/99')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });
    expect(component['actionError']()).toBeTruthy();
  });
});
