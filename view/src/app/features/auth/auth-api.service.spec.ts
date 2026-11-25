import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AuthApiService } from './auth-api.service';

describe('AuthApiService', () => {
  let service: AuthApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('executes login, register, and Google OAuth endpoints', () => {
    service.login({ email: 'a@ribbit.app', password: 'secret' }).subscribe();
    const loginReq = httpMock.expectOne('/api/auth/login');
    expect(loginReq.request.method).toBe('POST');
    loginReq.flush({ access_token: 'tok', token_type: 'bearer', user: { user_id: 1 } });

    service
      .register({
        email: 'new@ribbit.app',
        password: 'secret',
        display_name: 'New User',
        birth_date: '2000-01-01',
      })
      .subscribe();
    const regReq = httpMock.expectOne('/api/auth/register');
    expect(regReq.request.method).toBe('POST');
    regReq.flush({ access_token: 'tok2', token_type: 'bearer', user: { user_id: 2 } });

    service.getGoogleClientId().subscribe();
    const cidReq = httpMock.expectOne('/api/auth/google/client-id');
    expect(cidReq.request.method).toBe('GET');
    cidReq.flush({ client_id: 'cid-123' });

    service.getGoogleAuthorizeUrl().subscribe();
    const authUrlReq = httpMock.expectOne('/api/auth/google/authorize');
    expect(authUrlReq.request.method).toBe('GET');
    authUrlReq.flush({ authorize_url: 'https://accounts.google.com/o/oauth2/auth' });

    service.completeGoogleOAuthSession().subscribe();
    const sessReq = httpMock.expectOne('/api/auth/google/session');
    expect(sessReq.request.method).toBe('POST');
    sessReq.flush({ access_token: 'tok3', token_type: 'bearer', user: { user_id: 3 } });

    service.loginWithGoogle({ id_token: 'id-tok' }).subscribe();
    const gReq = httpMock.expectOne('/api/auth/google');
    expect(gReq.request.method).toBe('POST');
    gReq.flush({ access_token: 'tok4', token_type: 'bearer', user: { user_id: 4 } });
  });
});
