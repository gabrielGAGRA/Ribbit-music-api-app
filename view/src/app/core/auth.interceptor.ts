import type { HttpInterceptorFn } from '@angular/common/http';
import { HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { toApiError } from './api-error';
import { AuthSessionNotifier } from './auth-session.notifier';
import { clearAuthStorage, readAuthToken } from './auth-token.storage';

function isPublicAuthEndpoint(url: string): boolean {
  return (
    url.includes('/api/auth/login') ||
    url.includes('/api/auth/entrar') ||
    url.includes('/api/auth/register') ||
    url.includes('/api/auth/cadastrar')
  );
}

/** Attaches Bearer credentials to /api calls and normalizes backend errors. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const notifier = inject(AuthSessionNotifier);
  const token = readAuthToken();

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
        !isPublicAuthEndpoint(req.url)
      ) {
        clearAuthStorage();
        notifier.notifyUnauthorized();
      }
      return throwError(() => toApiError(err));
    }),
  );
};
