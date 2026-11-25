import { describe, expect, it, vi } from 'vitest';
import {
  recordSpotifyOAuthInitiatorOrigin,
  redirectSpotifyCallbackIfNeeded,
  resolveSpotifyCallbackOriginRedirect,
} from './spotify-oauth-origin';

describe('spotify-oauth-origin', () => {
  it('resolves loopback redirects and handles invalid origins safely', () => {
    expect(
      resolveSpotifyCallbackOriginRedirect(
        {
          origin: 'http://localhost:4200',
          protocol: 'http:',
          hostname: 'localhost',
          port: '4200',
          pathname: '/discover',
          search: '',
        },
        '',
        null,
      ),
    ).toBeNull();

    expect(
      resolveSpotifyCallbackOriginRedirect(
        {
          origin: 'http://127.0.0.1:4200',
          protocol: 'http:',
          hostname: '127.0.0.1',
          port: '4200',
          pathname: '/callback',
          search: '?code=abc&state=xyz',
        },
        '',
        null,
      ),
    ).toBe('http://localhost:4200/callback?code=abc&state=xyz');

    expect(redirectSpotifyCallbackIfNeeded()).toBe(false);

    recordSpotifyOAuthInitiatorOrigin('not-a-valid-url');
    vi.restoreAllMocks();
  });
});
