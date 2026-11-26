import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import {
  ApiError,
  isPremiumRequiredError,
  toApiError,
  translateApiErrorMessage,
} from './api-error';

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
    expect(
      toApiError(
        new HttpErrorResponse({
          status: 401,
          error: { message: 'Current password is required and must match.' },
        }),
      ).message,
    ).toBe('A senha atual é obrigatória e deve estar correta.');
    expect(
      toApiError(
        new HttpErrorResponse({
          status: 400,
          error: { message: 'This Spotify account is already linked to another Ribbit profile.' },
        }),
      ).message,
    ).toBe('Esta conta do Spotify já está vinculada a outro perfil do Ribbit.');
    expect(
      toApiError(
        new HttpErrorResponse({
          status: 409,
          error: { message: 'You have already reviewed this track.' },
        }),
      ).message,
    ).toBe(
      'Você já avaliou esta música. Para alterar sua nota ou comentário, exclua sua avaliação atual e envie uma nova.',
    );
  });

  it('translates backend validation and resource error patterns', () => {
    expect(translateApiErrorMessage('Email user@example.com is already in use.')).toBe(
      'Este e-mail já está em uso.',
    );
    expect(translateApiErrorMessage('Primary user 12 not found.')).toBe(
      'Conta principal não encontrada.',
    );
    expect(translateApiErrorMessage("Track 'Night Drive' by 'DJ Ribbit' already exists.")).toBe(
      'Esta faixa já existe no catálogo.',
    );
    expect(translateApiErrorMessage('String should have at least 8 characters')).toBe(
      'O campo deve ter pelo menos 8 caracteres.',
    );
    expect(translateApiErrorMessage('Rating must be between 1 and 5.')).toBe(
      'A nota deve ser entre 1 e 5 estrelas.',
    );
    expect(translateApiErrorMessage('Input should be greater than or equal to -2')).toBe(
      'O valor deve ser maior ou igual a -2.',
    );
    expect(translateApiErrorMessage('Year must be between 1900 and 2100')).toBe(
      'O ano deve estar entre 1900 e 2100.',
    );
    expect(translateApiErrorMessage('Family plan profile limit of 4 reached.')).toBe(
      'Limite de 4 perfis do Plano Família atingido.',
    );
  });
});
