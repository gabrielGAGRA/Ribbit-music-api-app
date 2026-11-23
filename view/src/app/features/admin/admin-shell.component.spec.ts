import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import type { ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { Router, UrlTree, provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { adminAuthGuard } from './admin-auth.guard';
import { AdminLoginComponent } from './login/admin-login.component';
import { AdminShellComponent } from './admin-shell.component';
import { AdminStateService } from './admin-state.service';

const STUB_ROUTE: unknown = {};
const STUB_STATE: unknown = {};

describe('Admin Auth Guard, Login & Shell', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function flushHydration(): void {
    httpMock.expectOne('/api/admin/plans').flush([]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 2,
      estimated_net_revenue: 14.9,
      users_by_plan: { Free: 1, Individual: 1 },
      revenue_by_plan: { Free: 0, Individual: 14.9 },
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 2,
      total_tracks: 5,
      active_tracks: 5,
      blocked_genres: {},
    });
    httpMock.expectOne('/api/admin/users').flush([]);
    httpMock.expectOne('/api/admin/administrators').flush([]);
    httpMock.expectOne('/api/admin/tracks?limit=100').flush([]);
    httpMock.expectOne('/api/admin/blocked-tracks').flush([]);
    httpMock.expectOne('/api/admin/reviews').flush([]);
  }

  it('redirects unauthenticated access to /admin/login and allows authenticated admins', () => {
    const blockedResult = TestBed.runInInjectionContext(() =>
      adminAuthGuard(STUB_ROUTE as ActivatedRouteSnapshot, STUB_STATE as RouterStateSnapshot),
    );
    expect(blockedResult instanceof UrlTree).toBe(true);
    expect(TestBed.inject(Router).serializeUrl(blockedResult as UrlTree)).toBe('/admin/login');

    const state = TestBed.inject(AdminStateService);
    state.loginAdmin('admin@ribbit.app', 'secret123').subscribe();
    httpMock.expectOne('/api/admin/login').flush({
      access_token: 'admin-jwt',
      token_type: 'bearer',
      user: {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Administrador Local',
        age: 30,
        plan_id: 1,
        is_admin: true,
      },
    });
    flushHydration();

    const allowedResult = TestBed.runInInjectionContext(() =>
      adminAuthGuard(STUB_ROUTE as ActivatedRouteSnapshot, STUB_STATE as RouterStateSnapshot),
    );
    expect(allowedResult).toBe(true);
  });

  it('validates empty login fields and authenticates against POST /api/admin/login', () => {
    const loginComponent = TestBed.runInInjectionContext(() => new AdminLoginComponent());
    const state = TestBed.inject(AdminStateService);

    loginComponent['authenticateAdmin'](new Event('submit'));
    expect(state.isAuthenticated()).toBe(false);
    expect(loginComponent['errorMessage']()).toContain('Informe e-mail e senha');

    loginComponent['emailDraft'].set('admin@ribbit.app');
    loginComponent['passwordDraft'].set('secret123');
    loginComponent['authenticateAdmin'](new Event('submit'));

    const req = httpMock.expectOne('/api/admin/login');
    expect(req.request.method).toBe('POST');
    req.flush({
      access_token: 'admin-jwt',
      token_type: 'bearer',
      user: {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Administrador Local',
        age: 30,
        plan_id: 1,
        is_admin: true,
      },
    });
    flushHydration();

    expect(state.isAuthenticated()).toBe(true);
    expect(loginComponent['errorMessage']()).toBe('');
  });

  it('switches sections, computes initials, refreshes API data, and signs out in AdminShellComponent', () => {
    const state = TestBed.inject(AdminStateService);
    state.loginAdmin('admin@ribbit.app', 'secret123').subscribe();
    httpMock.expectOne('/api/admin/login').flush({
      access_token: 'admin-jwt',
      token_type: 'bearer',
      user: {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Administrador Local',
        age: 30,
        plan_id: 1,
        is_admin: true,
      },
    });
    flushHydration();

    const shell = TestBed.runInInjectionContext(() => new AdminShellComponent());
    expect(shell['adminInitials']()).toBe('AL');
    expect(shell['currentNavLabel']()).toBe('Visão Executiva');

    shell['navigateSection']('moderation');
    expect(shell['activeSection']()).toBe('moderation');
    expect(shell['currentNavLabel']()).toBe('Moderação');

    shell['refreshBackend']();
    flushHydration();

    shell['signOutAdmin']();
    expect(state.isAuthenticated()).toBe(false);
  });
});
