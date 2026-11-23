import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { routes } from '../../app.routes';
import { SettingsComponent } from './settings.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { clearAuthStorage, readAuthToken, writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { IconComponent } from '../../shared/icon.component';

describe('SettingsComponent', () => {
  let component: SettingsComponent;
  let state: RibbitStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState({}, '', '/');
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    httpMock = TestBed.inject(HttpTestingController);
    state.setUserName('João Lucas');
    component = TestBed.runInInjectionContext(() => new SettingsComponent());
  });

  afterEach(() => {
    window.history.replaceState({}, '', '/');
    clearAuthStorage();
    localStorage.clear();
  });

  it('should compute user initials accurately', () => {
    expect(component['userInitials']()).toBe('JL');

    state.setUserName('Lucas');
    expect(component['userInitials']()).toBe('LU');
  });

  it('should allow editing and saving display name', () => {
    component['startEditingName']();
    expect(component['isEditingName']()).toBe(true);

    component['nameDraft'].set('João Silva');
    component['saveName']();

    expect(state.userName()).toBe('João Silva');
    expect(component['isEditingName']()).toBe(false);
  });

  it('should allow canceling name edit', () => {
    component['startEditingName']();
    component['nameDraft'].set('Outro Nome');
    component['cancelEditingName']();

    expect(state.userName()).toBe('João Lucas');
    expect(component['isEditingName']()).toBe(false);
  });

  it('should initiate Spotify OAuth via GET /api/spotify/authorize and redirect to authorization_url', () => {
    writeAuthToken('jwt-token');
    const redirectSpy = vi
      .spyOn(
        component as unknown as { navigateToExternalUrl: (url: string) => void },
        'navigateToExternalUrl',
      )
      .mockImplementation(() => {});

    component['connectSpotify']();
    expect(component['isLinkingSpotify']()).toBe(true);

    const authReq = httpMock.expectOne('/api/spotify/authorize');
    expect(authReq.request.method).toBe('GET');
    authReq.flush({
      authorization_url: 'https://accounts.spotify.com/authorize?client_id=test&state=signed-jwt',
    });

    expect(redirectSpy).toHaveBeenCalledWith(
      'https://accounts.spotify.com/authorize?client_id=test&state=signed-jwt',
    );
  });

  it('should reject insecure, off-domain, or missing authorization_url payloads', () => {
    writeAuthToken('jwt-token');
    const redirectSpy = vi
      .spyOn(
        component as unknown as { navigateToExternalUrl: (url: string) => void },
        'navigateToExternalUrl',
      )
      .mockImplementation(() => {});

    const invalidPayloads: readonly Record<string, unknown>[] = [
      { authorization_url: 'http://accounts.spotify.com/authorize?client_id=test' },
      { authorization_url: 'https://evil.example/phish' },
      {},
    ];
    for (const payload of invalidPayloads) {
      component['connectSpotify']();
      const authReq = httpMock.expectOne('/api/spotify/authorize');
      authReq.flush(payload);

      expect(redirectSpy).not.toHaveBeenCalled();
      expect(component['isLinkingSpotify']()).toBe(false);
      expect(component['spotifyFeedback']()?.type).toBe('error');
    }
  });

  it('should preserve callback params on session-expired 401 and clean URL on OAuth state 401', () => {
    const pastExp = Math.floor(Date.now() / 1000) - 60;
    const expiredJwt = `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: '7', exp: pastExp })).replace(/=+$/, '')}.sig`;
    writeAuthToken(expiredJwt);
    window.history.replaceState({}, '', '/callback?code=c1&state=s1');

    component.ngOnInit();
    httpMock
      .expectOne('/api/spotify/callback')
      .flush({ detail: 'Token has expired.' }, { status: 401, statusText: 'Unauthorized' });

    expect(readAuthToken()).toBeNull();
    expect(window.location.search).toBe('?code=c1&state=s1');

    const futureExp = Math.floor(Date.now() / 1000) + 3600;
    const validJwt = `eyJhbGciOiJIUzI1NiJ9.${btoa(JSON.stringify({ sub: '7', exp: futureExp })).replace(/=+$/, '')}.sig`;
    writeAuthToken(validJwt);
    window.history.replaceState({}, '', '/callback?code=c2&state=s2');

    const retryComp = TestBed.runInInjectionContext(() => new SettingsComponent());
    retryComp.ngOnInit();
    httpMock.expectOne('/api/spotify/callback').flush(
      {
        error: 'AuthenticationRequiredError',
        message: 'Invalid or mismatched Spotify OAuth state parameter.',
      },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(readAuthToken()).toBe(validJwt);
    expect(window.location.pathname).toBe('/settings');
    expect(window.location.search).toBe('');
    expect(retryComp['spotifyFeedback']()?.type).toBe('error');
  });

  it('should surface unlink failure cleanly and keep reconnect functional', () => {
    writeAuthToken('jwt-token');
    const redirectSpy = vi
      .spyOn(
        component as unknown as { navigateToExternalUrl: (url: string) => void },
        'navigateToExternalUrl',
      )
      .mockImplementation(() => {});

    component['disconnectSpotify']();
    httpMock
      .expectOne((r) => r.url === '/api/spotify/connection' && r.method === 'DELETE')
      .flush({ detail: 'Internal Server Error' }, { status: 500, statusText: 'Server Error' });

    expect(component['isLinkingSpotify']()).toBe(false);
    expect(component['spotifyFeedback']()?.type).toBe('error');

    component['connectSpotify']();
    httpMock.expectOne('/api/spotify/authorize').flush({
      authorization_url: 'https://accounts.spotify.com/authorize?client_id=test&state=ok',
    });
    expect(redirectSpy).toHaveBeenCalledWith(
      'https://accounts.spotify.com/authorize?client_id=test&state=ok',
    );
  });

  it('should remove blocked genre', () => {
    state.blockedGenres.set(['Metal', 'Sertanejo']);
    expect(state.blockedGenres()).toContain('Metal');

    component['removeBlockedGenre']('Metal');
    expect(state.blockedGenres()).not.toContain('Metal');
    expect(state.blockedGenres()).toContain('Sertanejo');
  });

  it('should cancel subscription and downgrade to Free', () => {
    state.setPlan('Individual');
    expect(state.currentPlan()).toBe('Individual');

    component['cancelSubscription']();
    expect(state.currentPlan()).toBe('Free');
  });

  it('should trigger delete modal and logout', () => {
    component['openDeleteModal']();
    expect(state.activeModal()).toBe('delete');

    component['logout']();
    expect(state.authView()).toBe('login');
  });

  it('should validate and update user password via ProfileApiService', () => {
    component['currentPassword'].set('');
    component['newPassword'].set('');
    component['updatePassword']();
    expect(component['passwordError']()).toContain('Informe a senha atual');

    component['currentPassword'].set('oldpass123');
    component['newPassword'].set('123');
    component['updatePassword']();
    expect(component['passwordError']()).toContain('mínimo 6 caracteres');

    component['newPassword'].set('newsecret123');
    component['updatePassword']();
    expect(component['isChangingPassword']()).toBe(true);

    const req = httpMock.expectOne('/api/profile/me');
    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual({
      display_name: undefined,
      new_password: 'newsecret123',
      current_password: 'oldpass123',
    });
    req.flush({
      user_id: 9,
      email: 'joao@ribbit.app',
      display_name: 'João Lucas',
      age: 26,
      plan_id: 1,
      is_admin: false,
    });

    expect(component['isChangingPassword']()).toBe(false);
    expect(component['passwordSuccess']()).toBe('Senha alterada com sucesso!');
    expect(component['currentPassword']()).toBe('');
    expect(component['newPassword']()).toBe('');
  });

  it('should navigate to the unified parental control screen (/family)', () => {
    component['goToFamily']();
    expect(state.activePage()).toBe('family');
  });

  it('should make settings inputs fluid and stack plan status box on mobile', () => {
    const componentStyles = readFileSync(resolve(__dirname, './settings.component.css'), 'utf8');

    expect(componentStyles).toMatch(/\.settings-input\s*\{[^}]*font-size:\s*1rem/);
    expect(componentStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.settings-input\s*\{[^}]*min-width:\s*0/,
    );
    expect(componentStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.plan-status-box\s*\{[^}]*flex-direction:\s*column/,
    );
  });
});

describe('SettingsComponent DOM', () => {
  let state: RibbitStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState({}, '', '/');
    const html = readFileSync(resolve(__dirname, './settings.component.html'), 'utf8');
    const css = readFileSync(resolve(__dirname, './settings.component.css'), 'utf8');
    TestBed.overrideComponent(IconComponent, {
      set: {
        template: '',
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [],
      },
    });
    TestBed.overrideComponent(SettingsComponent, {
      set: {
        template: html,
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [css],
        schemas: [NO_ERRORS_SCHEMA],
      },
    });
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    httpMock = TestBed.inject(HttpTestingController);
    state.setUserName('João Lucas');
  });

  afterEach(() => {
    httpMock.verify();
    window.history.replaceState({}, '', '/');
    clearAuthStorage();
    localStorage.clear();
  });

  it('should keep active SettingsComponent mounted across /callback to /settings and render reconnect + unlink DOM buttons', async () => {
    writeAuthToken('jwt-token');
    window.history.replaceState({}, '', '/callback?code=spotify_code_1&state=signed_state');

    const harness = await RouterTestingHarness.create(
      '/callback?code=spotify_code_1&state=signed_state',
    );
    const mounted = harness.routeDebugElement?.componentInstance as SettingsComponent;
    expect(mounted['isLinkingSpotify']()).toBe(true);

    const callbackReq = httpMock.expectOne('/api/spotify/callback');
    expect(callbackReq.request.method).toBe('POST');
    expect(callbackReq.request.body).toEqual({
      code: 'spotify_code_1',
      state: 'signed_state',
    });
    callbackReq.flush({
      user_id: 12,
      email: 'joao@ribbit.app',
      display_name: 'João Lucas',
      spotify_id: 'real_spotify_user',
      spotify_premium: true,
      plan_id: 1,
      blocked_genres: [],
      is_admin: false,
    });
    harness.detectChanges();

    expect(window.location.pathname).toBe('/settings');
    expect(window.location.search).toBe('');
    expect(mounted['isLinkingSpotify']()).toBe(false);
    expect(state.spotifyId()).toBe('real_spotify_user');
    expect(state.spotifyPremium()).toBe(true);

    const successEl = harness.fixture.nativeElement.querySelector(
      '.settings-success-alert',
    ) as HTMLElement | null;
    expect(successEl).not.toBeNull();
    expect(successEl?.textContent).toContain('real_spotify_user');
    expect(harness.fixture.nativeElement.querySelector('.spotify-connect-btn')).not.toBeNull();
    expect(harness.fixture.nativeElement.querySelector('.spotify-disconnect-btn')).not.toBeNull();
  });

  it('should render DOM error alert for /callback?error=access_denied', async () => {
    writeAuthToken('jwt-token');
    window.history.replaceState({}, '', '/callback?error=access_denied');

    const harness = await RouterTestingHarness.create('/callback?error=access_denied');
    harness.detectChanges();

    expect(window.location.pathname).toBe('/settings');
    const errorEl = harness.fixture.nativeElement.querySelector(
      '.settings-error-alert',
    ) as HTMLElement | null;
    expect(errorEl).not.toBeNull();
    expect(errorEl?.textContent).toContain('cancelada ou recusada');
    httpMock.expectNone('/api/spotify/callback');
  });

  it('should render DOM error alert for incomplete callback query params', async () => {
    writeAuthToken('jwt-token');
    window.history.replaceState({}, '', '/settings?code=missing_state');

    const harness = await RouterTestingHarness.create('/settings?code=missing_state');
    harness.detectChanges();

    expect(window.location.pathname).toBe('/settings');
    const errorEl = harness.fixture.nativeElement.querySelector(
      '.settings-error-alert',
    ) as HTMLElement | null;
    expect(errorEl).not.toBeNull();
    expect(errorEl?.textContent).toContain('ausentes ou inválidos');
    httpMock.expectNone('/api/spotify/callback');
  });
});
