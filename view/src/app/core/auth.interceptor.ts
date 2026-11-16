import type { HttpInterceptorFn } from '@angular/common/http';
import { HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { toApiError } from './api-error';
import { AuthSessionNotifier } from './auth-session.notifier';
import {
  clearAdminAuthToken,
  clearAuthStorage,
  IS_ADMIN_API_REQUEST,
  readAdminAuthToken,
  readAuthToken,
} from './auth-token.storage';

function isPublicAuthEndpoint(url: string): boolean {
  return (
    url.includes('/api/auth/login') ||
    url.includes('/api/auth/entrar') ||
    url.includes('/api/auth/register') ||
    url.includes('/api/auth/cadastrar') ||
    url.includes('/api/auth/google') ||
    url.includes('/api/admin/login')
  );
}

function hasUnexpiredJwtExp(token: string): boolean {
  const payloadSegment = token.split('.')[1];
  if (!payloadSegment) return false;
  try {
    const normalized = payloadSegment.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
    const decoded = JSON.parse(atob(padded)) as { exp?: unknown };
    return typeof decoded.exp === 'number' && decoded.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

function isSpotifyOAuthState401(
  url: string,
  err: HttpErrorResponse,
  token: string | null,
): boolean {
  if (!url.includes('/api/spotify/callback') || !token) {
    return false;
  }
  const msg = toApiError(err).message;
  if (msg.includes('Spotify OAuth state')) {
    return true;
  }
  if (msg.includes('bearer token') || msg.includes('Authentication required')) {
    return false;
  }
  return hasUnexpiredJwtExp(token);
}

function isBearerAuthFailureMessage(msg: string): boolean {
  const normalized = msg.toLowerCase();
  return (
    normalized.includes('bearer token') ||
    normalized.includes('authentication required') ||
    normalized.includes('user not found') ||
    normalized.includes('invalid token') ||
    normalized.includes('unsupported token algorithm') ||
    normalized.includes('token missing subject') ||
    normalized.includes('token has expired')
  );
}

function isSecondaryCredential401(
  url: string,
  err: HttpErrorResponse,
  token: string | null,
): boolean {
  if (!token) {
    return false;
  }
  const isFamilyAdd = url.includes('/api/profile/family/members');
  const isProfileUpdate = url.includes('/api/profile/me');
  if (!isFamilyAdd && !isProfileUpdate) {
    return false;
  }
  const msg = toApiError(err).message;
  if (isBearerAuthFailureMessage(msg)) {
    return false;
  }
  if (
    (isFamilyAdd && msg.includes('Invalid credentials')) ||
    (isProfileUpdate && msg.includes('Current password'))
  ) {
    return true;
  }
  return hasUnexpiredJwtExp(token);
}

function shouldClearSessionOn401(
  url: string,
  err: HttpErrorResponse,
  token: string | null,
): boolean {
  if (isPublicAuthEndpoint(url)) {
    return false;
  }
  return !isSpotifyOAuthState401(url, err, token) && !isSecondaryCredential401(url, err, token);
}

function isAdminRouteActive(): boolean {
  return typeof location !== 'undefined' && location.pathname.startsWith('/admin');
}

/** Attaches Bearer credentials to /api calls and normalizes backend errors. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const notifier = inject(AuthSessionNotifier);
  const isAdminRequest =
    req.url.startsWith('/api/admin') ||
    req.context.get(IS_ADMIN_API_REQUEST) ||
    isAdminRouteActive();
  const token = isAdminRequest
    ? (readAdminAuthToken() ?? readAuthToken())
    : (readAuthToken() ?? readAdminAuthToken());

  const shouldAttach =
    req.url.startsWith('/api') && token !== null && !req.headers.has('Authorization');
  const outgoing = shouldAttach
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(outgoing).pipe(
    catchError((err: unknown) => {
      if (
        err instanceof HttpErrorResponse &&
        err.status === 401 &&
        shouldClearSessionOn401(req.url, err, token)
      ) {
        if (isAdminRequest) {
          clearAdminAuthToken();
        } else {
          clearAuthStorage();
          notifier.notifyUnauthorized();
        }
      }
      return throwError(() => toApiError(err));
    }),
  );
};
