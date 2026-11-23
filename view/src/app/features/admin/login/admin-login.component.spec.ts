import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AdminLoginComponent } from './admin-login.component';
import { clearAdminAuthToken } from '../../../core/auth-token.storage';

describe('AdminLoginComponent', () => {
  let component: AdminLoginComponent;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    clearAdminAuthToken();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
    component = TestBed.runInInjectionContext(() => new AdminLoginComponent());
  });

  afterEach(() => {
    httpMock.verify();
    clearAdminAuthToken();
    localStorage.clear();
  });

  it('requires email and password before calling /api/admin/login', () => {
    component['authenticateAdmin'](new Event('submit'));
    expect(component['errorMessage']()).toContain('Informe e-mail e senha');
    httpMock.expectNone('/api/admin/login');
  });

  it('authenticates an administrator via POST /api/admin/login', () => {
    component['emailDraft'].set('admin@ribbit.app');
    component['passwordDraft'].set('secret123');
    component['authenticateAdmin'](new Event('submit'));

    const req = httpMock.expectOne('/api/admin/login');
    expect(req.request.method).toBe('POST');
    req.flush({
      access_token: 'admin-jwt',
      token_type: 'bearer',
      user: {
        user_id: 1,
        email: 'admin@ribbit.app',
        display_name: 'Admin Root',
        plan_id: 1,
        is_admin: true,
      },
    });

    httpMock
      .match(() => true)
      .forEach((r) => {
        if (!r.cancelled) {
          r.flush([]);
        }
      });
    expect(component['isSubmitting']()).toBe(false);
    expect(component['errorMessage']()).toBe('');
  });
});
