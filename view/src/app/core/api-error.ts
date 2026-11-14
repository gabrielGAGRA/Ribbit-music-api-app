import { HttpErrorResponse } from '@angular/common/http';

interface FastApiErrorPayload {
  readonly error?: string;
  readonly message?: string;
  readonly details?: unknown;
  readonly detail?: unknown;
}

interface ExtractedErrorInfo {
  readonly code: string;
  readonly message: string;
  readonly details?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function extractValidationDetail(detail: unknown): ExtractedErrorInfo | null {
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return { code: 'ValidationError', message: detail };
  }
  if (!Array.isArray(detail) || detail.length === 0) {
    return null;
  }
  const first: unknown = detail[0];
  if (isRecord(first) && typeof first['msg'] === 'string') {
    return { code: 'ValidationError', message: first['msg'], details: detail };
  }
  return null;
}

function extractPayloadMessage(payload: unknown, status: number): ExtractedErrorInfo | null {
  if (!isRecord(payload)) {
    return null;
  }
  const typed = payload as FastApiErrorPayload;
  if (typeof typed.message === 'string' && typed.message.trim().length > 0) {
    return {
      code: typeof typed.error === 'string' ? typed.error : `HTTP_${status}`,
      message: typed.message,
      details: typed.details,
    };
  }
  return extractValidationDetail(typed.detail);
}

function fallbackStatusMessage(status: number): ExtractedErrorInfo {
  if (status === 0) {
    return {
      code: 'NetworkError',
      message: 'Não foi possível conectar ao servidor Ribbit.',
    };
  }
  if (status === 401) {
    return {
      code: 'AuthenticationRequiredError',
      message: 'Sua sessão expirou ou as credenciais são inválidas.',
    };
  }
  if (status === 403) {
    return {
      code: 'PermissionDeniedError',
      message: 'Recurso exclusivo para assinantes de planos pagos.',
    };
  }
  return {
    code: `HTTP_${status}`,
    message: 'Não foi possível concluir a operação no servidor.',
  };
}

/** Represents a normalized HTTP error returned by the Ribbit FastAPI backend. */
export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  readonly details?: unknown;

  constructor(options: {
    readonly status: number;
    readonly errorCode: string;
    readonly message: string;
    readonly details?: unknown;
  }) {
    super(options.message);
    this.name = 'ApiError';
    this.status = options.status;
    this.errorCode = options.errorCode;
    this.details = options.details;
  }
}

/** Converts an unknown error into a structured ApiError instance. */
export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) {
    return err;
  }
  if (err instanceof HttpErrorResponse) {
    const extracted =
      extractPayloadMessage(err.error, err.status) ?? fallbackStatusMessage(err.status);
    return new ApiError({
      status: err.status,
      errorCode: extracted.code,
      message: extracted.message,
      details: extracted.details,
    });
  }
  if (err instanceof Error) {
    return new ApiError({
      status: 500,
      errorCode: err.name || 'ClientError',
      message: err.message,
    });
  }
  return new ApiError({
    status: 500,
    errorCode: 'UnknownError',
    message: 'Erro inesperado na comunicação.',
  });
}

/** Checks whether an error is due to Spotify account not being connected. */
export function isSpotifyConnectionRequiredError(err: unknown): boolean {
  const apiErr = toApiError(err);
  if (apiErr.errorCode === 'SpotifyConnectionRequiredError') return true;
  if (isRecord(apiErr.details) && apiErr.details['rule_name'] === 'spotify_connection_required') {
    return true;
  }
  return false;
}

/** Checks whether an error is due to Spotify Premium requirement. */
export function isSpotifyPremiumRequiredError(err: unknown): boolean {
  const apiErr = toApiError(err);
  if (apiErr.errorCode === 'SpotifyPremiumRequiredError') return true;
  if (isRecord(apiErr.details) && apiErr.details['rule_name'] === 'spotify_premium_required') {
    return true;
  }
  return false;
}

/** Checks whether an error is related to Spotify requirements (connection or premium). */
export function isSpotifyError(err: unknown): boolean {
  return isSpotifyConnectionRequiredError(err) || isSpotifyPremiumRequiredError(err);
}

/** Checks whether the given error indicates a paid subscription requirement (403). */
export function isPremiumRequiredError(err: unknown): boolean {
  if (isSpotifyError(err)) {
    return false;
  }
  const apiErr = toApiError(err);
  return apiErr.status === 403;
}
