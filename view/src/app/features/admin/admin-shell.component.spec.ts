import { TestBed } from '@angular/core/testing';
import type { ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';
import { Router, UrlTree, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';
import { adminAuthGuard } from './admin-auth.guard';
import { AdminLoginComponent } from './admin-login.component';
import { AdminShellComponent } from './admin-shell.component';
import { AdminStateService } from './admin-state.service';

const STUB_ROUTE: unknown = {};
const STUB_STATE: unknown = {};

describe('Admin Auth Guard, Login & Shell', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([])],
    });
  });

  it('redirects unauthenticated access to /admin/login and allows authenticated admins', () => {
    const blockedResult = TestBed.runInInjectionContext(() =>
      adminAuthGuard(STUB_ROUTE as ActivatedRouteSnapshot, STUB_STATE as RouterStateSnapshot),
    );
    expect(blockedResult instanceof UrlTree).toBe(true);
    expect(TestBed.inject(Router).serializeUrl(blockedResult as UrlTree)).toBe('/admin/login');

    const state = TestBed.inject(AdminStateService);
    state.loginAdmin(state.defaultAdminEmail, state.defaultAdminPassword);

    const allowedResult = TestBed.runInInjectionContext(() =>
      adminAuthGuard(STUB_ROUTE as ActivatedRouteSnapshot, STUB_STATE as RouterStateSnapshot),
    );
    expect(allowedResult).toBe(true);
  });

  it('fills demo credentials, validates login errors, and authenticates on AdminLoginComponent', () => {
    const loginComponent = TestBed.runInInjectionContext(() => new AdminLoginComponent());
    const state = TestBed.inject(AdminStateService);

    loginComponent['authenticateAdmin'](new Event('submit'));
    expect(state.isAuthenticated()).toBe(false);
    expect(loginComponent['errorMessage']()).toContain('Credenciais inválidas');

    loginComponent['fillDemoCredentials']();
    loginComponent['authenticateAdmin'](new Event('submit'));

    expect(state.isAuthenticated()).toBe(true);
    expect(loginComponent['errorMessage']()).toBe('');
  });

  it('switches sections, computes initials, resets demo data, and signs out in AdminShellComponent', () => {
    const state = TestBed.inject(AdminStateService);
    state.loginAdmin(state.defaultAdminEmail, state.defaultAdminPassword);

    const shell = TestBed.runInInjectionContext(() => new AdminShellComponent());
    expect(shell['adminInitials']()).toBe('AL');
    expect(shell['currentNavLabel']()).toBe('Visão Executiva');

    shell['navigateSection']('moderation');
    expect(shell['activeSection']()).toBe('moderation');
    expect(shell['currentNavLabel']()).toBe('Moderação');

    state.deleteReview(501);
    shell['resetDemo']();
    expect(state.topModerationReviews().some((item) => item.review_id === 501)).toBe(true);

    shell['signOutAdmin']();
    expect(state.isAuthenticated()).toBe(false);
    shell.ngOnDestroy();
  });
});
