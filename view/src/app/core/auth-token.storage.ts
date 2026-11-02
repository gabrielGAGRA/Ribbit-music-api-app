import type { UserApiDto } from '@ribbit/shared-types';

export const AUTH_TOKEN_KEY = 'ribbit-auth-token';
export const AUTH_USER_KEY = 'ribbit-auth-user';

const LEGACY_STORAGE_KEYS: readonly string[] = [
  'ribbit-history',
  'ribbit-playlists',
  'ribbit-comments',
  'ribbit-user-name',
  'ribbit-plan',
  'ribbit-blocked',
];

function hasStorage(): boolean {
  return typeof localStorage !== 'undefined';
}

/** Reads the persisted JWT access token if present. */
export function readAuthToken(): string | null {
  try {
    if (!hasStorage()) return null;
    const raw = localStorage.getItem(AUTH_TOKEN_KEY);
    return raw && raw.trim().length > 0 ? raw.trim() : null;
  } catch {
    // Storage unavailable in restricted browser contexts
    return null;
  }
}

/** Persists the JWT access token in localStorage. */
export function writeAuthToken(token: string): void {
  try {
    if (hasStorage()) {
      localStorage.setItem(AUTH_TOKEN_KEY, token);
    }
  } catch {
    // Ignore quota or privacy mode errors
  }
}

/** Reads the cached authenticated user payload if available. */
export function readStoredUser(): UserApiDto | null {
  try {
    if (!hasStorage()) return null;
    const raw = localStorage.getItem(AUTH_USER_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      'user_id' in parsed &&
      'display_name' in parsed
    ) {
      return parsed as UserApiDto;
    }
    return null;
  } catch {
    // Corrupted JSON falls back cleanly to unauthenticated
    return null;
  }
}

/** Persists the authenticated user snapshot in localStorage. */
export function writeStoredUser(user: UserApiDto): void {
  try {
    if (hasStorage()) {
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    }
  } catch {
    // Ignore quota or privacy mode errors
  }
}

/** Clears auth session keys and legacy mock keys from localStorage. */
export function clearAuthStorage(): void {
  try {
    if (!hasStorage()) return;
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    for (const key of LEGACY_STORAGE_KEYS) {
      localStorage.removeItem(key);
    }
  } catch {
    // Ignore storage cleanup errors
  }
}
