import { HttpErrorResponse } from '@angular/common/http';

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
  const message = payload['message'];
  if (typeof message === 'string' && message.trim().length > 0) {
    const errorCode = payload['error'];
    return {
      code: typeof errorCode === 'string' ? errorCode : `HTTP_${status}`,
      message,
      details: payload['details'],
    };
  }
  return extractValidationDetail(payload['detail']);
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

const EXACT_PT_BR_ERRORS: Record<string, string> = {
  'Current password is required and must match.':
    'A senha atual é obrigatória e deve estar correta.',
  'Invalid credentials.': 'E-mail ou senha inválidos.',
  'Invalid credentials': 'E-mail ou senha inválidos.',
  'Access restricted to administrators.': 'Acesso restrito a administradores.',
  'User not found.': 'Usuário não encontrado.',
  'Administrator user not found.': 'Administrador não encontrado.',
  'Authenticated user not found.': 'Usuário autenticado não encontrado.',
  'Authentication required.': 'Autenticação obrigatória.',
  'A valid bearer token is required.': 'É necessário um token de autenticação válido.',
  'Token missing subject claim.': 'Sessão inválida. Faça login novamente.',
  'Invalid user ID in token subject.': 'Sessão inválida. Faça login novamente.',
  'Invalid token.': 'Sua sessão expirou. Faça login novamente.',
  'Token has expired.': 'Sua sessão expirou. Faça login novamente.',
  'Feature exclusive to Premium subscribers.': 'Recurso exclusivo para assinantes de planos pagos.',
  'An unexpected error occurred.': 'Ocorreu um erro inesperado no servidor.',
  'Invalid birth date.': 'Data de nascimento inválida.',
  'Birth date cannot be in the future.': 'A data de nascimento não pode estar no futuro.',
  'Default Free plan not found.': 'Plano Free padrão não encontrado.',
  'A plan with this name already exists.': 'Já existe um plano com esse nome.',
  'Plan name is required.': 'O nome do plano é obrigatório.',
  'Track duration must be positive.': 'A duração da faixa deve ser positiva.',
  'Track is restricted for minor users.': 'Esta faixa é restrita para usuários menores de 18 anos.',
  'Track not found or inactive.': 'Faixa não encontrada ou indisponível.',
  'Track not found or deleted.': 'Faixa não encontrada ou removida.',
  'Review not found or deleted.': 'Avaliação não encontrada ou removida.',
  'Only the author can delete this review.': 'Apenas o autor pode excluir esta avaliação.',
  'Playlist not found.': 'Playlist não encontrada.',
  'Playlist does not belong to this user.': 'Esta playlist não pertence à sua conta.',
  'Playlist cover image not found.': 'Imagem de capa da playlist não encontrada.',
  'Interaction for this track was not found.': 'Interação para esta faixa não foi encontrada.',
  'Jam room not found or inactive.': 'Sala Jam não encontrada ou inativa.',
  'Only the jam host can advance playback.': 'Apenas o anfitrião da Jam pode avançar a reprodução.',
  'Only the host can close the Jam.': 'Apenas o anfitrião pode encerrar a Jam.',
  'No tracks in queue to advance.': 'Não há faixas na fila para avançar.',
  'No track currently playing to skip.': 'Nenhuma faixa em reprodução para pular.',
  'Room code format is invalid.': 'O código da sala tem um formato inválido.',
  'User is not a participant in this Jam.': 'Você não é participante desta Jam.',
  'Participant only.': 'Apenas participantes da Jam podem realizar esta ação.',
  'Must join Jam room before interacting.': 'Entre na sala Jam antes de interagir.',
  'Track does not belong to this Jam room queue.': 'A faixa não pertence à fila desta Jam.',
  'Track is not currently in the jam queue.': 'A faixa não está na fila atual da Jam.',
  'The vote must be on the current track.': 'O voto deve ser na faixa em reprodução.',
  'Active track not found or inactive.': 'Faixa ativa não encontrada ou indisponível.',
  'Jam ID is missing.': 'Identificador da Jam não informado.',
  'Current plan does not support family members.':
    'Seu plano atual não oferece suporte a membros da família.',
  'Family member details are incomplete.': 'Os dados do membro da família estão incompletos.',
  'Administrator cannot revoke own access.': 'O administrador não pode revogar o próprio acesso.',
  'Google OAuth 2.0 is not configured on the server.':
    'Login com Google não está configurado no servidor.',
  'No valid Google OAuth session found.': 'Sessão do Google OAuth inválida ou expirada.',
  'Catalog file storage is not configured.': 'Armazenamento do catálogo não configurado.',
  'Playlist repository is not configured.': 'Repositório de playlists não configurado.',
  'Email cannot be blank.': 'O e-mail não pode ficar em branco.',
  'Display name cannot be blank.': 'O nome de exibição não pode ficar em branco.',
  'Age cannot be negative.': 'A idade não pode ser negativa.',
  'Field required': 'Campo obrigatório não preenchido.',
  'Not Found': 'Recurso não encontrado.',
  'This Spotify account is already linked to another Ribbit profile.':
    'Esta conta do Spotify já está vinculada a outro perfil do Ribbit.',
  'Spotify OAuth is not configured.':
    'A integração com o Spotify não está configurada no servidor.',
  'Invalid or mismatched Spotify OAuth state parameter.':
    'Sessão de conexão com o Spotify expirada ou inválida. Tente novamente.',
  'Current plan does not support adding family members.':
    'Seu plano atual não permite adicionar membros da família.',
  'A dependent user cannot manage family members.':
    'Uma conta dependente não pode gerenciar membros da família.',
  'A user cannot add themselves as a dependent.':
    'Você não pode adicionar sua própria conta como dependente.',
  'This user is already linked to another family account.':
    'Este usuário já está vinculado a outra conta família.',
  'This profile does not belong to your family account.':
    'Este perfil não pertence à sua conta família.',
};

const PATTERN_PT_BR_ERRORS: readonly {
  readonly pattern: RegExp;
  readonly replace: (...args: string[]) => string;
}[] = [
  {
    pattern: /^Email .+ is already in use\.$/i,
    replace: () => 'Este e-mail já está em uso.',
  },
  {
    pattern: /^Primary user .+ not found\.$/i,
    replace: () => 'Conta principal não encontrada.',
  },
  {
    pattern: /^(?:Dependent|Member) user .+ not found\.$/i,
    replace: () => 'Conta dependente não encontrada.',
  },
  {
    pattern: /^Host user .+ not found\.$/i,
    replace: () => 'Anfitrião não encontrado.',
  },
  {
    pattern: /^User(?: with ID)? .+ not found\.$/i,
    replace: () => 'Usuário não encontrado.',
  },
  {
    pattern: /^Plan(?: with ID)? .+ not found\.$/i,
    replace: () => 'Plano não encontrado.',
  },
  {
    pattern: /^Track '.+' by '.+' already exists\.$/i,
    replace: () => 'Esta faixa já existe no catálogo.',
  },
  {
    pattern: /^Track(?: with ID)? .+ not found\.$/i,
    replace: () => 'Faixa não encontrada.',
  },
  {
    pattern: /^Playlist(?: with ID)? .+ not found\.$/i,
    replace: () => 'Playlist não encontrada.',
  },
  {
    pattern: /^Review(?: with ID)? .+ not found\.$/i,
    replace: () => 'Avaliação não encontrada.',
  },
  {
    pattern: /^Jam session .+ not found\.$/i,
    replace: () => 'Sala Jam não encontrada.',
  },
  {
    pattern: /Spotify OAuth state/i,
    replace: () => 'Sessão de conexão com o Spotify expirada ou inválida. Tente novamente.',
  },
  {
    pattern: /^String should have at least (\d+) characters?$/i,
    replace: (_m, n) => `O campo deve ter pelo menos ${n} caracteres.`,
  },
  {
    pattern: /^String should have at most (\d+) characters?$/i,
    replace: (_m, n) => `O campo deve ter no máximo ${n} caracteres.`,
  },
  {
    pattern: /^value is not a valid email address/i,
    replace: () => 'Informe um endereço de e-mail válido.',
  },
  {
    pattern: /^Input should be greater than or equal to (-?\d+)$/i,
    replace: (_m, n) => `O valor deve ser maior ou igual a ${n}.`,
  },
  {
    pattern: /^Input should be less than or equal to (-?\d+)$/i,
    replace: (_m, n) => `O valor deve ser menor ou igual a ${n}.`,
  },
  {
    pattern: /^Year must be between (\d+) and (\d+)/i,
    replace: (_m, min, max) => `O ano deve estar entre ${min} e ${max}.`,
  },
  {
    pattern: /^Family plan profile limit of (\d+) reached\.$/i,
    replace: (_m, n) => `Limite de ${n} perfis do Plano Família atingido.`,
  },
];

/** Translates known English backend/validation error messages into Brazilian Portuguese. */
export function translateApiErrorMessage(rawMessage: string): string {
  const trimmed = rawMessage.trim();
  const stripped = trimmed.replace(/^Value error,\s*/i, '');
  const exact = EXACT_PT_BR_ERRORS[stripped];
  if (exact) {
    return exact;
  }
  for (const entry of PATTERN_PT_BR_ERRORS) {
    const match = entry.pattern.exec(stripped);
    if (match) {
      return entry.replace(...match);
    }
  }
  return trimmed;
}

/** Represents a normalized HTTP error returned by the Ribbit FastAPI backend. */
export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string;
  readonly rawMessage: string;
  readonly details?: unknown;

  constructor(options: {
    readonly status: number;
    readonly errorCode: string;
    readonly message: string;
    readonly rawMessage?: string;
    readonly details?: unknown;
  }) {
    super(options.message);
    this.name = 'ApiError';
    this.status = options.status;
    this.errorCode = options.errorCode;
    this.rawMessage = options.rawMessage ?? options.message;
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
      message: translateApiErrorMessage(extracted.message),
      rawMessage: extracted.message,
      details: extracted.details,
    });
  }
  if (err instanceof Error) {
    return new ApiError({
      status: 500,
      errorCode: err.name || 'ClientError',
      message: err.message,
      rawMessage: err.message,
    });
  }
  return new ApiError({
    status: 500,
    errorCode: 'UnknownError',
    message: 'Erro inesperado na comunicação.',
  });
}

/** Checks whether an error is due to Spotify account not being connected or lacking a valid user OAuth token. */
export function isSpotifyConnectionRequiredError(err: unknown): boolean {
  const apiErr = toApiError(err);
  if (isRecord(apiErr.details) && apiErr.details['rule_name'] === 'spotify_connection_required') {
    return true;
  }
  return false;
}

/** Checks whether an error is due to Spotify Premium requirement. */
export function isSpotifyPremiumRequiredError(err: unknown): boolean {
  const apiErr = toApiError(err);
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
