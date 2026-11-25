import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import { ApiError, isPremiumRequiredError, toApiError } from './api-error';

describe('api-error', () => {
  it('normalizes HttpErrorResponse into ApiError', () => {
    const httpErr = new HttpErrorResponse({
      status: 403,
      error: { message: 'Premium required', error: 'PremiumRequiredError' },
    });
    const apiErr = toApiError(httpErr);
    expect(apiErr).toBeInstanceOf(ApiError);
    expect(apiErr.status).toBe(403);
    expect(isPremiumRequiredError(apiErr)).toBe(true);
  });

  it('wraps standard Error instances', () => {
    const apiErr = toApiError(new Error('Network failure'));
    expect(apiErr.message).toBe('Network failure');
    expect(apiErr.status).toBe(500);
  });

  it('handles validation details, status fallbacks, and unknown error values', () => {
    expect(
      toApiError(new HttpErrorResponse({ status: 422, error: { detail: 'Bad field' } })).message,
    ).toBe('Bad field');
    expect(
      toApiError(new HttpErrorResponse({ status: 422, error: { detail: [{ msg: 'Invalid' }] } }))
        .message,
    ).toBe('Invalid');
    expect(toApiError(new HttpErrorResponse({ status: 0, error: 'raw' })).errorCode).toBe(
      'NetworkError',
    );
    expect(toApiError(new HttpErrorResponse({ status: 401 })).errorCode).toBe(
      'AuthenticationRequiredError',
    );
    expect(toApiError(new HttpErrorResponse({ status: 403 })).errorCode).toBe(
      'PermissionDeniedError',
    );
    expect(toApiError('unknown').status).toBe(500);
  });
});
