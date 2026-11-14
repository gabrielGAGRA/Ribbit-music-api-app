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
import { clearAuthStorage, readAuthToken, writeAuthToken } from './auth-token.storage';
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
});
