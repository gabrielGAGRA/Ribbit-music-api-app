import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  isPremiumRequiredError,
  isSpotifyConnectionRequiredError,
  isSpotifyPremiumRequiredError,
} from './api-error';
import { AuthSessionNotifier } from './auth-session.notifier';
import {
  clearAdminAuthToken,
  clearAuthStorage,
  createAdminHttpContext,
  readAdminAuthToken,
  readAuthToken,
  writeAdminAuthToken,
  writeAuthToken,
} from './auth-token.storage';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let notifier: AuthSessionNotifier;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    notifier = TestBed.inject(AuthSessionNotifier);
  });

  afterEach(() => {
    httpMock.verify();
    clearAuthStorage();
    clearAdminAuthToken();
  });

  it('attaches Admin Authorization Bearer header for /api/admin requests and clears admin token on 401', () => {
    writeAuthToken('listener-jwt');
    writeAdminAuthToken('admin-jwt-999');

    http.get('/api/admin/dashboard').subscribe({ error: () => {} });

    const req = httpMock.expectOne('/api/admin/dashboard');
    expect(req.request.headers.get('Authorization')).toBe('Bearer admin-jwt-999');
    req.flush(
      { error: 'AuthenticationRequiredError', message: 'Expired admin token' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(readAdminAuthToken()).toBeNull();
    expect(readAuthToken()).toBe('listener-jwt');
  });

  it('prioritizes admin token over listener token when createAdminHttpContext() is attached on non-/api/admin endpoints', () => {
    writeAuthToken('expired-listener-jwt');
    writeAdminAuthToken('valid-admin-jwt');

    http
      .get('/api/tracks/search?limit=100', { context: createAdminHttpContext() })
      .subscribe({ error: () => {} });

    const req = httpMock.expectOne('/api/tracks/search?limit=100');
    expect(req.request.headers.get('Authorization')).toBe('Bearer valid-admin-jwt');
    req.flush(
      { error: 'AuthenticationRequiredError', message: 'Expired admin token' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(readAdminAuthToken()).toBeNull();
    expect(readAuthToken()).toBe('expired-listener-jwt');
  });

  it('attaches Authorization Bearer header when token is stored', () => {
    writeAuthToken('jwt-token-123');

    http.get('/api/profile/me').subscribe();

    const req = httpMock.expectOne('/api/profile/me');
    expect(req.request.headers.get('Authorization')).toBe('Bearer jwt-token-123');
    req.flush({});
  });

  it('clears session and notifies listeners on 401 from protected endpoints', () => {
    writeAuthToken('expired-token');
    const spy = vi.fn();
    notifier.onUnauthorized(spy);

    let capturedError: unknown;
    http.get('/api/discovery/next').subscribe({
      error: (err: unknown) => {
        capturedError = err;
      },
    });

    const req = httpMock.expectOne('/api/discovery/next');
    req.flush(
      { error: 'AuthenticationRequiredError', message: 'Invalid token' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(readAuthToken()).toBeNull();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(capturedError).toBeInstanceOf(ApiError);
    expect((capturedError as ApiError).message).toBe('Invalid token');
  });

  it('does not clear session or notify unauthorized listeners on 401 from POST /api/auth/google', () => {
    writeAuthToken('existing-token');
    const spy = vi.fn();
    notifier.onUnauthorized(spy);

    let capturedError: unknown;
    http.post('/api/auth/google', { id_token: 'demo-token' }).subscribe({
      error: (err: unknown) => {
        capturedError = err;
      },
    });

    const req = httpMock.expectOne('/api/auth/google');
    req.flush(
      { detail: 'Invalid or expired Google ID token.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(readAuthToken()).toBe('existing-token');
    expect(spy).not.toHaveBeenCalled();
    expect(capturedError).toBeInstanceOf(ApiError);
    expect((capturedError as ApiError).status).toBe(401);
  });

  it('normalizes 403 domain errors and flags premium requirement', () => {
    let capturedError: unknown;
    http.get('/api/profile/stats').subscribe({
      error: (err: unknown) => {
        capturedError = err;
      },
    });

    const req = httpMock.expectOne('/api/profile/stats');
    req.flush(
      { error: 'PermissionDeniedError', message: 'Feature exclusive to Premium subscribers.' },
      { status: 403, statusText: 'Forbidden' },
    );

    expect(isPremiumRequiredError(capturedError)).toBe(true);
  });

  it('differentiates Spotify connection required error and does not treat as Ribbit premium', () => {
    let capturedError: unknown;
    http.post('/api/jams', { room_name: 'Pond' }).subscribe({
      error: (err: unknown) => {
        capturedError = err;
      },
    });

    const req = httpMock.expectOne('/api/jams');
    req.flush(
      {
        error: 'SpotifyConnectionRequiredError',
        message: 'Conecte sua conta do Spotify para utilizar o Pond.',
        details: { rule_name: 'spotify_connection_required' },
      },
      { status: 403, statusText: 'Forbidden' },
    );

    expect(isSpotifyConnectionRequiredError(capturedError)).toBe(true);
    expect(isSpotifyPremiumRequiredError(capturedError)).toBe(false);
    expect(isPremiumRequiredError(capturedError)).toBe(false);
  });

  it('differentiates Spotify premium required error and does not treat as Ribbit premium', () => {
    let capturedError: unknown;
    http.post('/api/jams', { room_name: 'Pond' }).subscribe({
      error: (err: unknown) => {
        capturedError = err;
      },
    });

    const req = httpMock.expectOne('/api/jams');
    req.flush(
      {
        error: 'SpotifyPremiumRequiredError',
        message: 'Uma conta Spotify Premium é necessária para esta funcionalidade.',
        details: { rule_name: 'spotify_premium_required' },
      },
      { status: 403, statusText: 'Forbidden' },
    );

    expect(isSpotifyConnectionRequiredError(capturedError)).toBe(false);
    expect(isSpotifyPremiumRequiredError(capturedError)).toBe(true);
    expect(isPremiumRequiredError(capturedError)).toBe(false);
  });

  it('classifies SpotifyAuthError and SpotifyForbiddenError as connection required rather than Ribbit premium', () => {
    for (const errorCode of ['SpotifyAuthError', 'SpotifyForbiddenError']) {
      let capturedError: unknown;
      http.post('/api/playlists/1/export-spotify', {}).subscribe({
        error: (err: unknown) => {
          capturedError = err;
        },
      });

      const req = httpMock.expectOne('/api/playlists/1/export-spotify');
      req.flush(
        {
          error: errorCode,
          message: 'Autenticação do Spotify expirada ou insuficiente.',
        },
        { status: 403, statusText: 'Forbidden' },
      );

      expect(isSpotifyConnectionRequiredError(capturedError)).toBe(true);
      expect(isSpotifyPremiumRequiredError(capturedError)).toBe(false);
      expect(isPremiumRequiredError(capturedError)).toBe(false);
    }
  });

  it('preserves active Ribbit session when POST /api/spotify/callback returns 401 for Spotify OAuth state with unexpired Bearer JWT', () => {
    const futureExp = Math.floor(Date.now() / 1000) + 3600;
    const validJwt = `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: '7', exp: futureExp })).replace(/=+$/, '')}.sig`;
    writeAuthToken(validJwt);

    const onUnauthorizedSpy = vi.fn();
    notifier.onUnauthorized(onUnauthorizedSpy);

    for (const msg of [
      'Invalid or mismatched Spotify OAuth state parameter.',
      'Token has expired.',
    ]) {
      let capturedError: unknown;
      http.post('/api/spotify/callback', { code: 'abc', state: 'bad' }).subscribe({
        error: (err: unknown) => {
          capturedError = err;
        },
      });

      const req = httpMock.expectOne('/api/spotify/callback');
      req.flush(
        { error: 'AuthenticationRequiredError', message: msg },
        { status: 401, statusText: 'Unauthorized' },
      );

      expect(readAuthToken()).toBe(validJwt);
      expect(onUnauthorizedSpy).not.toHaveBeenCalled();
      expect((capturedError as ApiError).status).toBe(401);
    }
  });

  it('clears active Ribbit session when POST /api/spotify/callback returns 401 and Bearer JWT is expired', () => {
    const pastExp = Math.floor(Date.now() / 1000) - 60;
    const expiredJwt = `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: '7', exp: pastExp })).replace(/=+$/, '')}.sig`;
    writeAuthToken(expiredJwt);

    const onUnauthorizedSpy = vi.fn();
    notifier.onUnauthorized(onUnauthorizedSpy);

    http.post('/api/spotify/callback', { code: 'abc', state: 'signed' }).subscribe({
      error: () => {},
    });

    const req = httpMock.expectOne('/api/spotify/callback');
    req.flush(
      { error: 'AuthenticationRequiredError', message: 'Token has expired.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(readAuthToken()).toBeNull();
    expect(onUnauthorizedSpy).toHaveBeenCalledTimes(1);
  });

  it('preserves active session when POST /api/profile/family/members returns 401 for child account credentials', () => {
    const futureExp = Math.floor(Date.now() / 1000) + 3600;
    const validJwt = `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: '2', exp: futureExp })).replace(/=+$/, '')}.sig`;
    writeAuthToken(validJwt);

    const onUnauthorizedSpy = vi.fn();
    notifier.onUnauthorized(onUnauthorizedSpy);

    let capturedError: unknown;
    http
      .post('/api/profile/family/members', {
        email: 'existing@ribbit.app',
        password: 'wrong-password',
      })
      .subscribe({
        error: (err: unknown) => {
          capturedError = err;
        },
      });

    const req = httpMock.expectOne('/api/profile/family/members');
    req.flush(
      { error: 'AuthenticationRequiredError', message: 'Invalid credentials.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(readAuthToken()).toBe(validJwt);
    expect(onUnauthorizedSpy).not.toHaveBeenCalled();
    expect(capturedError).toBeInstanceOf(ApiError);
    expect((capturedError as ApiError).status).toBe(401);
  });

  it('clears active session when POST /api/profile/family/members returns 401 for expired or missing Bearer user', () => {
    writeAuthToken('expired-or-unknown-jwt');

    const onUnauthorizedSpy = vi.fn();
    notifier.onUnauthorized(onUnauthorizedSpy);

    http
      .post('/api/profile/family/members', {
        email: 'child@ribbit.app',
        password: 'Password123!',
      })
      .subscribe({ error: () => {} });

    const req = httpMock.expectOne('/api/profile/family/members');
    req.flush(
      { error: 'AuthenticationRequiredError', message: 'User not found.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(readAuthToken()).toBeNull();
    expect(onUnauthorizedSpy).toHaveBeenCalledTimes(1);
  });
});
