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
});
