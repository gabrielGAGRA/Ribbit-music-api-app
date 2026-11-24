import { readAuthToken } from './auth-token.storage';

const OAUTH_ORIGIN_WINDOW_PREFIX = 'ribbit-oauth-origin:';
const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1']);

function hasSpotifyCallbackParams(search: string): boolean {
  if (!search) return false;
  const params = new URLSearchParams(search);
  return params.has('error') || (params.has('code') && params.has('state'));
}

function isAllowedLoopbackOrigin(rawOrigin: string): boolean {
  try {
    const parsed = new URL(rawOrigin);
    return (
      (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
      LOOPBACK_HOSTS.has(parsed.hostname)
    );
  } catch {
    return false;
  }
}

/** Saves the current loopback origin in window.name when Spotify redirect_uri uses another loopback host. */
export function recordSpotifyOAuthInitiatorOrigin(authorizeUrl: string): void {
  if (typeof window === 'undefined') return;
  try {
    const redirectUri = new URL(authorizeUrl).searchParams.get('redirect_uri');
    if (!redirectUri) return;
    const redirectOrigin = new URL(redirectUri).origin;
    const currentOrigin = window.location.origin;
    if (
      redirectOrigin !== currentOrigin &&
      isAllowedLoopbackOrigin(currentOrigin) &&
      isAllowedLoopbackOrigin(redirectOrigin)
    ) {
      window.name = `${OAUTH_ORIGIN_WINDOW_PREFIX}${currentOrigin}`;
    }
  } catch {
    // Ignore malformed URLs
  }
}

/** Computes a redirect URL back to the originating loopback host if /callback landed on a mismatched origin. */
export function resolveSpotifyCallbackOriginRedirect(
  loc: Pick<Location, 'origin' | 'protocol' | 'hostname' | 'port' | 'pathname' | 'search'>,
  windowName: string,
  authToken: string | null = readAuthToken(),
): string | null {
  if (loc.pathname !== '/callback' || !hasSpotifyCallbackParams(loc.search)) {
    return null;
  }

  if (windowName.startsWith(OAUTH_ORIGIN_WINDOW_PREFIX)) {
    const targetOrigin = windowName.slice(OAUTH_ORIGIN_WINDOW_PREFIX.length);
    if (isAllowedLoopbackOrigin(targetOrigin) && targetOrigin !== loc.origin) {
      return `${targetOrigin}/callback${loc.search}`;
    }
  }

  if (loc.hostname === '127.0.0.1' && authToken === null) {
    const portSegment = loc.port ? `:${loc.port}` : '';
    return `${loc.protocol}//localhost${portSegment}/callback${loc.search}`;
  }

  return null;
}

/** Redirects a mismatched-origin /callback load back to the initiator origin before Angular bootstraps. */
export function redirectSpotifyCallbackIfNeeded(): boolean {
  if (typeof window === 'undefined') return false;
  const currentWindowName = window.name;
  if (currentWindowName.startsWith(OAUTH_ORIGIN_WINDOW_PREFIX)) {
    window.name = '';
  }
  const target = resolveSpotifyCallbackOriginRedirect(window.location, currentWindowName);
  if (!target) {
    return false;
  }
  window.location.replace(target);
  return true;
}
