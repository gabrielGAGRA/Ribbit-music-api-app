import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthComponent } from './auth.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';

describe('AuthComponent', () => {
  let component: AuthComponent;
  let state: RibbitStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    httpMock = TestBed.inject(HttpTestingController);
    component = TestBed.runInInjectionContext(() => new AuthComponent());
  });

  afterEach(() => {
    localStorage.clear();
    delete (globalThis as { google?: unknown }).google;
  });

  it('should toggle between login and register views', () => {
    state.setAuthView('login');
    expect(component['isRegister']()).toBe(false);

    component['toggleView']();
    expect(component['isRegister']()).toBe(true);

    component['toggleView']();
    expect(component['isRegister']()).toBe(false);
  });

  it('should calculate age correctly from birth date', () => {
    component['birthDateDraft'].set('2000-01-15');
    const age = component['calculatedAge']();
    expect(age).toBeGreaterThanOrEqual(24);
    expect(component['isUnderage']()).toBe(false);
    expect(component['isFutureDate']()).toBe(false);
  });

  it('should block registration for underage birth dates (< 18 years old)', () => {
    const today = new Date();
    const underageYear = today.getFullYear() - 14;
    const formatted = `${underageYear}-05-20`;
    component['birthDateDraft'].set(formatted);

    expect(component['isUnderage']()).toBe(true);
    expect(component['underageWarning']()).toContain(
      'Cadastro direto permitido apenas para maiores de 18 anos',
    );
    expect(component['canSubmitRegister']()).toBe(false);
  });

  it('should block registration for future birth dates', () => {
    const nextYear = new Date().getFullYear() + 2;
    component['birthDateDraft'].set(`${nextYear}-01-01`);

    expect(component['isFutureDate']()).toBe(true);
    expect(component['underageWarning']()).toContain('futuro');
    expect(component['canSubmitRegister']()).toBe(false);
  });

  it('should detect password mismatches and enforce minimum length', () => {
    component['passwordDraft'].set('12345');
    component['confirmPasswordDraft'].set('12345');
    expect(component['passwordTooShort']()).toBe(true);
    expect(component['passwordRequirementHint']()).toContain('6 caracteres (5/6)');
    expect(component['canSubmitRegister']()).toBe(false);

    component['passwordDraft'].set('senhaForte123');
    component['confirmPasswordDraft'].set('outraSenha');
    expect(component['passwordTooShort']()).toBe(false);
    expect(component['passwordRequirementHint']()).toContain('6+ caracteres');
    expect(component['passwordMismatch']()).toBe(true);
    expect(component['canSubmitRegister']()).toBe(false);

    component['confirmPasswordDraft'].set('senhaForte123');
    expect(component['passwordMismatch']()).toBe(false);
  });

  it('should register via POST /api/auth/register and set authenticated state', () => {
    state.setAuthView('register');
    component['nameDraft'].set('Carolina Santos');
    component['emailDraft'].set('carolina@email.com');
    component['birthDateDraft'].set('1998-03-25');
    component['passwordDraft'].set('senhaSegura123');
    component['confirmPasswordDraft'].set('senhaSegura123');
    component['selectedPlanId'].set(2);

    expect(component['canSubmitRegister']()).toBe(true);

    component['submitAuthForm'](new Event('submit'));
    const req = httpMock.expectOne('/api/auth/register');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      email: 'carolina@email.com',
      password: 'senhaSegura123',
      display_name: 'Carolina Santos',
      birth_date: '1998-03-25',
      plan_id: 2,
    });
    req.flush({
      access_token: 'jwt-carolina',
      token_type: 'bearer',
      user: {
        user_id: 12,
        email: 'carolina@email.com',
        display_name: 'Carolina Santos',
        spotify_id: null,
        plan_id: 2,
        blocked_genres: [],
      },
    });

    expect(state.userName()).toBe('Carolina Santos');
    expect(state.currentPlan()).toBe('Individual');
    expect(state['authView']()).toBe('app');
    expect(state.toast()).toContain('Carolina Santos');
  });

  it('should perform login via POST /api/auth/login and surface backend errors on 401', () => {
    state.setAuthView('login');
    component['emailDraft'].set('user@ribbit.app');
    component['passwordDraft'].set('wrongpass');

    component['submitAuthForm'](new Event('submit'));
    const failedReq = httpMock.expectOne('/api/auth/login');
    failedReq.flush(
      { detail: 'Invalid email or password.' },
      { status: 401, statusText: 'Unauthorized' },
    );
    expect(component['errorMessage']()).toContain('Invalid email or password.');
    expect(state['authView']()).toBe('login');

    component['passwordDraft'].set('correctpass');
    component['submitAuthForm'](new Event('submit'));
    const okReq = httpMock.expectOne('/api/auth/login');
    okReq.flush({
      access_token: 'jwt-valid',
      token_type: 'bearer',
      user: {
        user_id: 5,
        email: 'user@ribbit.app',
        display_name: 'Usuário Ribbit',
        spotify_id: null,
        plan_id: 1,
        blocked_genres: [],
      },
    });

    expect(state['authView']()).toBe('app');
    expect(state.toast()).toContain('Login realizado com sucesso');
  });

  it('should transition to forgot-password view on onForgot and return to login on backToLogin', () => {
    state.setAuthView('login');
    expect(component['authView']()).toBe('login');
    expect(component['isForgot']()).toBe(false);

    component['openForgotPassword']();
    expect(component['authView']()).toBe('forgot-password');
    expect(component['isForgot']()).toBe(true);
    expect(state['authView']()).toBe('forgot-password');

    component['backToLogin']();
    expect(component['authView']()).toBe('login');
    expect(component['isForgot']()).toBe(false);
    expect(state['authView']()).toBe('login');
  });

  it('should validate email in requestPasswordReset and show error for invalid inputs', () => {
    component['openForgotPassword']();
    component['emailDraft'].set('invalid-email');

    component['requestPasswordReset']();
    expect(component['errorMessage']()).toBe('Informe um e-mail válido para recuperação.');
    expect(component['forgotSubmitted']()).toBe(false);

    component['requestPasswordReset']('another-invalid');
    expect(component['errorMessage']()).toBe('Informe um e-mail válido para recuperação.');
  });

  it('should request password reset with valid email, set forgotSubmitted, and show success message', () => {
    vi.useFakeTimers();
    try {
      component['openForgotPassword']();
      component['requestPasswordReset']('usuario@ribbit.app');

      expect(component['isSubmitting']()).toBe(true);
      expect(component['errorMessage']()).toBe('');

      vi.advanceTimersByTime(450);

      expect(component['isSubmitting']()).toBe(false);
      expect(component['forgotSubmitted']()).toBe(true);
      expect(state.toast()).toContain(
        'Se este e-mail estiver cadastrado, enviamos as instruções de recuperação.',
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it('should configure mobile auth branding, 16px inputs, and bottom-sheet modals', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');
    const modalsTemplate = readFileSync(
      resolve(__dirname, '../../shared/modals.component.html'),
      'utf8',
    );

    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*900px\)[\s\S]*\.auth-mobile-logo\s*\{[^}]*display:\s*inline-flex/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.modal\s*\{[^}]*border-radius:\s*20px 20px 0 0/,
    );
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*font-size:\s*16px/);
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.event-builder-row\s+select\s*\{[^}]*font-size:\s*16px\s*!important/,
    );
    expect(modalsTemplate.indexOf('bottom-sheet-handle')).toBeLessThan(
      modalsTemplate.indexOf("@if (state.activeModal() === 'save-queue')"),
    );
  });

  it('should prefetch Google client_id in ngOnInit, reuse it on repeated clicks, and initialize GIS once', () => {
    const initialize = vi.fn();
    const prompt = vi.fn();
    (globalThis as Record<string, unknown>)['google'] = {
      accounts: { id: { initialize, prompt } },
    };

    component.ngOnInit();
    httpMock.expectOne('/api/plans').flush([]);
    const clientIdReq = httpMock.expectOne('/api/auth/google/client-id');
    expect(clientIdReq.request.method).toBe('GET');
    clientIdReq.flush({ client_id: '  prefetched-client-id.apps.googleusercontent.com  ' });

    expect(component['googleClientId']()).toBe('prefetched-client-id.apps.googleusercontent.com');

    component['triggerGoogleIdentityServicesPrompt']();
    component['triggerGoogleIdentityServicesPrompt']();
    httpMock.expectNone('/api/auth/google/client-id');
    expect(initialize).toHaveBeenCalledTimes(1);
    expect(initialize).toHaveBeenCalledWith(
      expect.objectContaining({
        client_id: 'prefetched-client-id.apps.googleusercontent.com',
        ux_mode: 'popup',
        cancel_on_tap_outside: true,
      }),
    );
    expect(prompt).toHaveBeenCalledTimes(2);
  });

  it('should fetch client_id on demand, prevent parallel client-id requests, and authenticate via POST /api/auth/google', () => {
    let capturedCallback: ((response: { credential?: string }) => void) | undefined;
    const initialize = vi.fn(
      (config: { callback: (response: { credential?: string }) => void }) => {
        capturedCallback = config.callback;
      },
    );
    const prompt = vi.fn();
    (globalThis as Record<string, unknown>)['google'] = {
      accounts: { id: { initialize, prompt } },
    };

    component['triggerGoogleIdentityServicesPrompt']();
    expect(component['isLoadingGoogleConfig']()).toBe(true);
    component['triggerGoogleIdentityServicesPrompt']();

    const clientIdReq = httpMock.expectOne('/api/auth/google/client-id');
    expect(clientIdReq.request.method).toBe('GET');
    clientIdReq.flush({ client_id: '12345.apps.googleusercontent.com' });

    expect(component['isLoadingGoogleConfig']()).toBe(false);
    expect(component['googleClientId']()).toBe('12345.apps.googleusercontent.com');
    expect(initialize).toHaveBeenCalledWith(
      expect.objectContaining({
        client_id: '12345.apps.googleusercontent.com',
        ux_mode: 'popup',
        cancel_on_tap_outside: true,
      }),
    );
    expect(prompt).toHaveBeenCalledTimes(1);
    expect(capturedCallback).toBeDefined();

    capturedCallback?.({ credential: 'real-google-jwt' });
    const googleReq = httpMock.expectOne('/api/auth/google');
    expect(googleReq.request.method).toBe('POST');
    expect(googleReq.request.body).toEqual({
      id_token: 'real-google-jwt',
    });
    httpMock.expectNone('/api/auth/login');
    httpMock.expectNone('/api/auth/register');

    googleReq.flush({
      access_token: 'jwt-google-direct',
      token_type: 'bearer',
      user: {
        user_id: 20,
        email: 'ana.clara@gmail.com',
        display_name: 'Ana Clara',
        age: null,
        spotify_id: null,
        plan_id: 1,
        blocked_genres: [],
        is_admin: false,
      },
    });

    expect(component['isSubmitting']()).toBe(false);
    expect(component['errorMessage']()).toBe('');
    expect(state['authView']()).toBe('app');
    expect(state.userName()).toBe('Ana Clara');
    expect(state.toast()).toContain('Conectado com Google como Ana Clara.');
  });

  it('should skip delayed client-id prompt if form submission started while config fetch was in flight', () => {
    const initialize = vi.fn();
    const prompt = vi.fn();
    (globalThis as Record<string, unknown>)['google'] = {
      accounts: { id: { initialize, prompt } },
    };

    component['triggerGoogleIdentityServicesPrompt']();
    const clientIdReq = httpMock.expectOne('/api/auth/google/client-id');

    component['emailDraft'].set('user@ribbit.app');
    component['passwordDraft'].set('secret123');
    component['submitAuthForm'](new Event('submit'));
    expect(component['isSubmitting']()).toBe(true);

    clientIdReq.flush({ client_id: 'late-client-id.apps.googleusercontent.com' });
    expect(component['isLoadingGoogleConfig']()).toBe(false);
    expect(initialize).not.toHaveBeenCalled();
    expect(prompt).not.toHaveBeenCalled();

    httpMock.expectOne('/api/auth/login').flush({
      access_token: 'jwt-login',
      token_type: 'bearer',
      user: {
        user_id: 5,
        email: 'user@ribbit.app',
        display_name: 'Usuário Ribbit',
        age: 25,
        spotify_id: null,
        plan_id: 1,
        blocked_genres: [],
        is_admin: false,
      },
    });
  });

  it('should not leak delayed client-id prompt or errors onto forgot-password view', () => {
    const initialize = vi.fn();
    const prompt = vi.fn();
    (globalThis as Record<string, unknown>)['google'] = {
      accounts: { id: { initialize, prompt } },
    };

    component['triggerGoogleIdentityServicesPrompt']();
    const successReq = httpMock.expectOne('/api/auth/google/client-id');
    component['openForgotPassword']();
    expect(component['authView']()).toBe('forgot-password');

    successReq.flush({ client_id: 'late-forgot-client-id.apps.googleusercontent.com' });
    expect(component['isLoadingGoogleConfig']()).toBe(false);
    expect(initialize).not.toHaveBeenCalled();
    expect(prompt).not.toHaveBeenCalled();
    expect(component['errorMessage']()).toBe('');

    component['backToLogin']();
    component['googleClientId'].set(null);
    component['triggerGoogleIdentityServicesPrompt']();
    const failReq = httpMock.expectOne('/api/auth/google/client-id');
    component['openForgotPassword']();

    failReq.flush(
      { detail: 'Google config unreachable.' },
      { status: 500, statusText: 'Internal Server Error' },
    );
    expect(component['isLoadingGoogleConfig']()).toBe(false);
    expect(component['errorMessage']()).toBe('');
  });

  it('should show clear errors when Google client_id is missing or fetch fails', () => {
    component['triggerGoogleIdentityServicesPrompt']();
    const emptyReq = httpMock.expectOne('/api/auth/google/client-id');
    emptyReq.flush({ client_id: null });
    expect(component['errorMessage']()).toBe(
      'Login com Google indisponível: GOOGLE_CLIENT_ID não configurado no servidor.',
    );

    component['triggerGoogleIdentityServicesPrompt']();
    const whitespaceReq = httpMock.expectOne('/api/auth/google/client-id');
    whitespaceReq.flush({ client_id: '   ' });
    expect(component['errorMessage']()).toBe(
      'Login com Google indisponível: GOOGLE_CLIENT_ID não configurado no servidor.',
    );

    component['triggerGoogleIdentityServicesPrompt']();
    const errorReq = httpMock.expectOne('/api/auth/google/client-id');
    errorReq.flush(
      { detail: 'Failed to read Google config.' },
      { status: 500, statusText: 'Internal Server Error' },
    );
    expect(component['errorMessage']()).toContain('Failed to read Google config.');
  });

  it('should show clear error when GIS script is unavailable or prompt is suppressed', () => {
    component['googleClientId'].set('12345.apps.googleusercontent.com');

    component['triggerGoogleIdentityServicesPrompt']();
    expect(component['errorMessage']()).toBe(
      'Serviço de autenticação do Google indisponível no navegador.',
    );

    const initialize = vi.fn();
    const prompt = vi.fn(
      (
        listener?: (notification?: {
          isNotDisplayed?: () => boolean;
          isSkippedMoment?: () => boolean;
        }) => void,
      ) => {
        listener?.({ isNotDisplayed: () => true });
      },
    );
    (globalThis as Record<string, unknown>)['google'] = {
      accounts: { id: { initialize, prompt } },
    };

    component['triggerGoogleIdentityServicesPrompt']();
    expect(component['errorMessage']()).toBe(
      'Não foi possível exibir o modal do Google. Verifique as permissões do navegador.',
    );

    prompt.mockImplementationOnce(
      (
        listener?: (notification?: {
          isNotDisplayed?: () => boolean;
          isSkippedMoment?: () => boolean;
        }) => void,
      ) => {
        listener?.({ isSkippedMoment: () => true });
      },
    );
    component['triggerGoogleIdentityServicesPrompt']();
    expect(component['errorMessage']()).toBe(
      'Não foi possível exibir o modal do Google. Verifique as permissões do navegador.',
    );
  });

  it('should validate empty token and surface 401/500 errors from POST /api/auth/google without fallback', () => {
    component['authenticateWithGoogleIdToken']('   ');
    expect(component['errorMessage']()).toBe('Token do Google inválido.');
    httpMock.expectNone('/api/auth/google');

    component['authenticateWithGoogleIdToken']('expired-google-jwt');
    const unauthorizedReq = httpMock.expectOne('/api/auth/google');
    expect(unauthorizedReq.request.method).toBe('POST');
    unauthorizedReq.flush(
      { detail: 'Invalid or expired Google ID token.' },
      { status: 401, statusText: 'Unauthorized' },
    );
    httpMock.expectNone('/api/auth/login');
    httpMock.expectNone('/api/auth/register');
    expect(component['isSubmitting']()).toBe(false);
    expect(component['errorMessage']()).toContain('Invalid or expired Google ID token.');

    component['authenticateWithGoogleIdToken']('server-error-jwt');
    const serverErrorReq = httpMock.expectOne('/api/auth/google');
    serverErrorReq.flush(
      { detail: 'Google token service error.' },
      { status: 500, statusText: 'Internal Server Error' },
    );
    httpMock.expectNone('/api/auth/login');
    httpMock.expectNone('/api/auth/register');
    expect(component['isSubmitting']()).toBe(false);
    expect(component['errorMessage']()).toContain('Google token service error.');
  });

  it('should reset selectedPlanId to Free when toggling auth view', () => {
    state.setAuthView('register');
    component['selectedPlanId'].set(2);
    expect(component['selectedPlanId']()).toBe(2);

    component['toggleView']();

    expect(component['authView']()).toBe('login');
    expect(component['selectedPlanId']()).toBe(1);
  });

  it('should request /api/auth/google/authorize on onGoogleLogin and navigate to external authorization URL', () => {
    const navSpy = vi
      .spyOn(
        component as unknown as { navigateToExternalUrl: (url: string) => void },
        'navigateToExternalUrl',
      )
      .mockImplementation(() => {});

    component['loginWithGoogle']();
    expect(component['isLoadingGoogleConfig']()).toBe(true);

    const authReq = httpMock.expectOne('/api/auth/google/authorize');
    expect(authReq.request.method).toBe('GET');
    authReq.flush({
      authorization_url: 'https://accounts.google.com/o/oauth2/auth?client_id=cid&state=xyz',
    });

    expect(component['isLoadingGoogleConfig']()).toBe(false);
    expect(navSpy).toHaveBeenCalledWith(
      'https://accounts.google.com/o/oauth2/auth?client_id=cid&state=xyz',
    );
  });

  it('should not navigate to external authorization URL if user navigated to forgot password or started submitting while in flight', () => {
    const navSpy = vi
      .spyOn(
        component as unknown as { navigateToExternalUrl: (url: string) => void },
        'navigateToExternalUrl',
      )
      .mockImplementation(() => {});

    component['loginWithGoogle']();
    expect(component['isLoadingGoogleConfig']()).toBe(true);

    // User switches to forgot view while request is in flight
    component['openForgotPassword']();
    expect(component['isForgot']()).toBe(true);

    const authReq = httpMock.expectOne('/api/auth/google/authorize');
    authReq.flush({
      authorization_url: 'https://accounts.google.com/o/oauth2/auth?client_id=cid&state=xyz',
    });

    expect(component['isLoadingGoogleConfig']()).toBe(false);
    expect(navSpy).not.toHaveBeenCalled();
  });

  it('should complete Google OAuth session when URL query indicates google_auth=complete', () => {
    window.history.pushState({}, '', '/discover?google_auth=complete');
    const historySpy = vi.spyOn(window.history, 'replaceState');

    try {
      component.ngOnInit();
      httpMock.expectOne('/api/plans').flush([]);
      httpMock.expectOne('/api/auth/google/client-id').flush({ client_id: null });

      expect(historySpy).toHaveBeenCalledWith({}, '', '/discover');
      expect(component['isSubmitting']()).toBe(true);

      const sessionReq = httpMock.expectOne('/api/auth/google/session');
      expect(sessionReq.request.method).toBe('POST');
      sessionReq.flush({
        access_token: 'jwt-google-session',
        token_type: 'bearer',
        user: {
          user_id: 33,
          email: 'oauth.user@gmail.com',
          display_name: 'OAuth User',
          plan_id: 1,
          is_admin: false,
        },
      });

      expect(component['isSubmitting']()).toBe(false);
      expect(state['authView']()).toBe('app');
      expect(state.userName()).toBe('OAuth User');
      expect(state.toast()).toContain('Conectado com Google como OAuth User.');
    } finally {
      window.history.pushState({}, '', '/');
    }
  });

  it('should surface friendly error when URL query indicates google_auth_error', () => {
    window.history.pushState({}, '', '/discover?google_auth_error=access_denied');
    const historySpy = vi.spyOn(window.history, 'replaceState');

    try {
      component.ngOnInit();
      httpMock.expectOne('/api/plans').flush([]);
      httpMock.expectOne('/api/auth/google/client-id').flush({ client_id: null });

      expect(historySpy).toHaveBeenCalledWith({}, '', '/discover');
      expect(component['errorMessage']()).toContain('cancelada');
    } finally {
      window.history.pushState({}, '', '/');
    }
  });

  it('should forward to pre-filled register view when URL query indicates google_auth=register', () => {
    window.history.pushState({}, '', '/discover?google_auth=register');
    const historySpy = vi.spyOn(window.history, 'replaceState');

    try {
      component.ngOnInit();
      httpMock.expectOne('/api/plans').flush([]);
      httpMock.expectOne('/api/auth/google/client-id').flush({ client_id: null });

      expect(historySpy).toHaveBeenCalledWith({}, '', '/discover');
      expect(component['isSubmitting']()).toBe(true);

      const sessionReq = httpMock.expectOne('/api/auth/google/session');
      expect(sessionReq.request.method).toBe('POST');
      sessionReq.flush(
        {
          error: 'EntityNotFoundError',
          message: 'Nenhuma conta Ribbit encontrada para este e-mail Google.',
          details: {
            entity_name: 'User',
            registration_required: true,
            email: 'new.oauth@gmail.com',
            display_name: 'New OAuth User',
          },
        },
        { status: 404, statusText: 'Not Found' },
      );

      expect(component['isSubmitting']()).toBe(false);
      expect(component['authView']()).toBe('register');
      expect(state['authView']()).toBe('register');
      expect(component['emailDraft']()).toBe('new.oauth@gmail.com');
      expect(component['nameDraft']()).toBe('New OAuth User');
      expect(component['errorMessage']()).toBe('');
      expect(component['infoMessage']()).toContain('Complete seu cadastro');
    } finally {
      window.history.pushState({}, '', '/');
    }
  });

  it('should consume eagerly captured google_auth=register after initial router redirect strips query params', () => {
    window.history.pushState({}, '', '/?google_auth=register');
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    const freshState = TestBed.inject(RibbitStateService);
    const freshHttpMock = TestBed.inject(HttpTestingController);
    window.history.replaceState({}, '', '/discover');
    const freshComponent = TestBed.runInInjectionContext(() => new AuthComponent());

    try {
      freshComponent.ngOnInit();
      freshHttpMock.expectOne('/api/plans').flush([]);
      freshHttpMock.expectOne('/api/auth/google/client-id').flush({ client_id: null });

      const sessionReq = freshHttpMock.expectOne('/api/auth/google/session');
      expect(sessionReq.request.method).toBe('POST');
      sessionReq.flush(
        {
          error: 'EntityNotFoundError',
          message: 'Nenhuma conta Ribbit encontrada para este e-mail Google.',
          details: {
            entity_name: 'User',
            registration_required: true,
            email: 'early.capture@gmail.com',
            display_name: 'Early Capture User',
          },
        },
        { status: 404, statusText: 'Not Found' },
      );

      expect(freshState['authView']()).toBe('register');
      expect(freshComponent['emailDraft']()).toBe('early.capture@gmail.com');
      expect(freshComponent['nameDraft']()).toBe('Early Capture User');
      expect(freshComponent['infoMessage']()).toContain('Complete seu cadastro');
    } finally {
      freshHttpMock.verify();
      window.history.pushState({}, '', '/');
    }
  });

  it('should hop to callback loopback origin with google_oauth_start=1 before redirecting to Google', () => {
    const navSpy = vi
      .spyOn(
        component as unknown as { navigateToExternalUrl: (url: string) => void },
        'navigateToExternalUrl',
      )
      .mockImplementation(() => {});
    const targetHost = window.location.hostname === 'localhost' ? '127.0.0.1' : 'localhost';
    const portSuffix = window.location.port ? `:${window.location.port}` : '';
    const targetOrigin = `${window.location.protocol}//${targetHost}${portSuffix}`;
    const redirectUri = encodeURIComponent(`${targetOrigin}/api/auth/google/callback`);

    component['loginWithGoogle']();
    httpMock.expectOne('/api/auth/google/authorize').flush({
      authorization_url: `https://accounts.google.com/o/oauth2/v2/auth?redirect_uri=${redirectUri}&state=xyz`,
    });

    expect(navSpy).toHaveBeenCalledWith(`${targetOrigin}/?google_oauth_start=1`);
  });

  it('should auto-start Google authorize flow when google_oauth_start=1 query param is present', () => {
    const navSpy = vi
      .spyOn(
        component as unknown as { navigateToExternalUrl: (url: string) => void },
        'navigateToExternalUrl',
      )
      .mockImplementation(() => {});
    window.history.pushState({}, '', '/?google_oauth_start=1');

    try {
      component.ngOnInit();
      httpMock.expectOne('/api/plans').flush([]);
      httpMock.expectOne('/api/auth/google/client-id').flush({ client_id: null });

      const authReq = httpMock.expectOne('/api/auth/google/authorize');
      authReq.flush({
        authorization_url: 'https://accounts.google.com/o/oauth2/v2/auth?client_id=cid&state=xyz',
      });

      expect(navSpy).toHaveBeenCalledWith(
        'https://accounts.google.com/o/oauth2/v2/auth?client_id=cid&state=xyz',
      );
    } finally {
      window.history.pushState({}, '', '/');
    }
  });

  it('should forward to pre-filled register view when POST /api/auth/google returns 404 registration_required', () => {
    component['authenticateWithGoogleIdToken']('valid-unregistered-google-jwt');
    const req = httpMock.expectOne('/api/auth/google');
    expect(req.request.method).toBe('POST');
    req.flush(
      {
        error: 'EntityNotFoundError',
        message: 'Nenhuma conta Ribbit encontrada.',
        details: {
          entity_name: 'User',
          registration_required: true,
          email: 'gis.new@gmail.com',
          display_name: 'GIS New User',
        },
      },
      { status: 404, statusText: 'Not Found' },
    );

    expect(component['isSubmitting']()).toBe(false);
    expect(component['authView']()).toBe('register');
    expect(component['emailDraft']()).toBe('gis.new@gmail.com');
    expect(component['nameDraft']()).toBe('GIS New User');
    expect(component['errorMessage']()).toBe('');
    expect(component['infoMessage']()).toContain('Complete seu cadastro');
  });
});

describe('AuthComponent DOM', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    const html = readFileSync(resolve(__dirname, './auth.component.html'), 'utf8');
    const css = readFileSync(resolve(__dirname, './auth.component.css'), 'utf8');
    TestBed.overrideComponent(FrogComponent, {
      set: {
        template: '',
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [],
      },
    });
    TestBed.overrideComponent(IconComponent, {
      set: {
        template: '',
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [],
      },
    });
    TestBed.overrideComponent(AuthComponent, {
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
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    localStorage.clear();
    delete (globalThis as { google?: unknown }).google;
  });

  it('should omit simulated Google modal, render GIS fallback preemptively, and re-render after forgot-password round-trip', () => {
    let capturedCallback: ((response: { credential?: string }) => void) | undefined;
    const initialize = vi.fn(
      (config: { callback: (response: { credential?: string }) => void }) => {
        capturedCallback = config.callback;
      },
    );
    const renderButton = vi.fn((container: HTMLElement) => {
      const marker = document.createElement('span');
      marker.className = 'mock-gsi-button';
      container.appendChild(marker);
    });
    const prompt = vi.fn();
    (globalThis as Record<string, unknown>)['google'] = {
      accounts: { id: { initialize, prompt, renderButton } },
    };

    const fixture = TestBed.createComponent(AuthComponent);
    fixture.detectChanges();

    httpMock.expectOne('/api/plans').flush([]);
    httpMock.expectOne('/api/auth/google/client-id').flush({
      client_id: 'dom-client-id.apps.googleusercontent.com',
    });

    expect(fixture.nativeElement.querySelector('.google-modal-card')).toBeNull();

    const googleButton = fixture.nativeElement.querySelector(
      '.google-login-btn',
    ) as HTMLButtonElement | null;
    expect(googleButton).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.google-login-btn.hidden')).toBeNull();

    (fixture.nativeElement.querySelector('.google-login-btn') as HTMLElement).focus();
    googleButton?.click();
    httpMock
      .expectOne('/api/auth/google/authorize')
      .flush({ detail: 'unavailable' }, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.google-modal-card')).toBeNull();
    expect(initialize).toHaveBeenCalledWith(
      expect.objectContaining({
        client_id: 'dom-client-id.apps.googleusercontent.com',
      }),
    );
    expect(prompt).toHaveBeenCalledTimes(1);
    expect(renderButton).toHaveBeenCalledTimes(1);
    expect(fixture.componentInstance['showGoogleFallbackButton']()).toBe(true);
    expect(fixture.nativeElement.querySelector('.google-login-btn.hidden')).not.toBeNull();
    expect(document.activeElement).toBe(
      fixture.nativeElement.querySelector('.google-gsi-fallback'),
    );
    expect(
      fixture.nativeElement.querySelector('.google-gsi-fallback.visible .mock-gsi-button'),
    ).not.toBeNull();

    fixture.componentInstance['openForgotPassword']();
    fixture.detectChanges();
    expect(fixture.componentInstance['showGoogleFallbackButton']()).toBe(false);

    fixture.componentInstance['backToLogin']();
    fixture.detectChanges();
    expect(fixture.componentInstance['showGoogleFallbackButton']()).toBe(false);

    const remountedGoogleButton = fixture.nativeElement.querySelector(
      '.google-login-btn',
    ) as HTMLButtonElement | null;
    expect(remountedGoogleButton).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.google-login-btn.hidden')).toBeNull();

    prompt.mockImplementationOnce(
      (
        listener?: (notification?: {
          isNotDisplayed?: () => boolean;
          isSkippedMoment?: () => boolean;
          isDismissedMoment?: () => boolean;
          getDismissedReason?: () => string;
        }) => void,
      ) => {
        listener?.({
          isDismissedMoment: () => true,
          getDismissedReason: () => 'user_cancel',
        });
      },
    );

    remountedGoogleButton?.click();
    httpMock
      .expectOne('/api/auth/google/authorize')
      .flush({ detail: 'unavailable' }, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();

    expect(initialize).toHaveBeenCalledTimes(1);
    expect(renderButton).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance['showGoogleFallbackButton']()).toBe(true);
    expect(fixture.nativeElement.querySelector('.google-login-btn.hidden')).not.toBeNull();
    expect(fixture.componentInstance['errorMessage']()).toBe('');
    expect(
      fixture.nativeElement.querySelector('.google-gsi-fallback.visible .mock-gsi-button'),
    ).not.toBeNull();

    fixture.componentInstance['toggleView']();
    fixture.detectChanges();
    expect(fixture.componentInstance['showGoogleFallbackButton']()).toBe(false);
    expect(fixture.nativeElement.querySelector('.google-login-btn.hidden')).toBeNull();
    expect(fixture.nativeElement.querySelector('.google-gsi-fallback.visible')).toBeNull();

    prompt.mockImplementationOnce(
      (
        listener?: (notification?: {
          isNotDisplayed?: () => boolean;
          isSkippedMoment?: () => boolean;
        }) => void,
      ) => {
        listener?.({ isSkippedMoment: () => true });
      },
    );
    remountedGoogleButton?.click();
    httpMock
      .expectOne('/api/auth/google/authorize')
      .flush({ detail: 'unavailable' }, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();
    expect(renderButton).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance['showGoogleFallbackButton']()).toBe(true);
    expect(fixture.nativeElement.querySelector('.google-login-btn.hidden')).not.toBeNull();
    expect(fixture.componentInstance['errorMessage']()).toBe('');

    capturedCallback?.({ credential: 'dom-google-jwt' });
    fixture.detectChanges();
    expect(fixture.componentInstance['isSubmitting']()).toBe(true);
    expect(remountedGoogleButton?.disabled).toBe(true);

    const googleReq = httpMock.expectOne('/api/auth/google');
    googleReq.flush(
      { detail: 'Service unavailable.' },
      { status: 503, statusText: 'Service Unavailable' },
    );
    fixture.detectChanges();

    expect(fixture.componentInstance['isSubmitting']()).toBe(false);
    expect(remountedGoogleButton?.disabled).toBe(false);
    const alertEl = fixture.nativeElement.querySelector('.auth-alert.error') as HTMLElement | null;
    expect(alertEl?.textContent).toContain('Service unavailable.');

    fixture.destroy();
  });

  it('should cancel in-flight Google config request when destroyed before completion', () => {
    const initialize = vi.fn();
    const prompt = vi.fn();
    (globalThis as Record<string, unknown>)['google'] = {
      accounts: { id: { initialize, prompt } },
    };

    const fixture = TestBed.createComponent(AuthComponent);
    fixture.detectChanges();

    httpMock.expectOne('/api/plans').flush([]);
    httpMock.expectOne('/api/auth/google/client-id').flush({ client_id: null });

    const googleButton = fixture.nativeElement.querySelector(
      '.google-login-btn',
    ) as HTMLButtonElement | null;
    googleButton?.click();
    httpMock
      .expectOne('/api/auth/google/authorize')
      .flush({ detail: 'unavailable' }, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();
    expect(googleButton?.disabled).toBe(true);

    const pendingReq = httpMock.expectOne('/api/auth/google/client-id');
    fixture.destroy();
    expect(pendingReq.cancelled).toBe(true);
    expect(initialize).not.toHaveBeenCalled();
    expect(prompt).not.toHaveBeenCalled();
  });

  it('should ignore delayed GIS prompt moment callbacks when in forgot-password or while submitting', () => {
    type MomentNotification = {
      isNotDisplayed?: () => boolean;
      isSkippedMoment?: () => boolean;
      isDismissedMoment?: () => boolean;
      getDismissedReason?: () => string;
    };
    let capturedMomentListener: ((notification?: MomentNotification) => void) | undefined;
    const initialize = vi.fn();
    const prompt = vi.fn((listener?: (notification?: MomentNotification) => void) => {
      capturedMomentListener = listener;
    });
    (globalThis as Record<string, unknown>)['google'] = {
      accounts: { id: { initialize, prompt } },
    };

    const fixture = TestBed.createComponent(AuthComponent);
    fixture.detectChanges();

    httpMock.expectOne('/api/plans').flush([]);
    httpMock.expectOne('/api/auth/google/client-id').flush({
      client_id: 'moment-guard-client-id.apps.googleusercontent.com',
    });

    const googleButton = fixture.nativeElement.querySelector(
      '.google-login-btn',
    ) as HTMLButtonElement | null;
    googleButton?.click();
    httpMock
      .expectOne('/api/auth/google/authorize')
      .flush({ detail: 'unavailable' }, { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();
    expect(capturedMomentListener).toBeDefined();

    fixture.componentInstance['openForgotPassword']();
    fixture.detectChanges();

    capturedMomentListener?.({ isSkippedMoment: () => true });
    capturedMomentListener?.({
      isDismissedMoment: () => true,
      getDismissedReason: () => 'user_cancel',
    });
    fixture.detectChanges();

    expect(fixture.componentInstance['errorMessage']()).toBe('');
    expect(fixture.componentInstance['showGoogleFallbackButton']()).toBe(false);
    expect(fixture.nativeElement.querySelector('.auth-alert.error')).toBeNull();

    fixture.componentInstance['backToLogin']();
    fixture.detectChanges();
    fixture.componentInstance['isSubmitting'].set(true);

    capturedMomentListener?.({ isSkippedMoment: () => true });
    capturedMomentListener?.({
      isDismissedMoment: () => true,
      getDismissedReason: () => 'user_cancel',
    });
    fixture.detectChanges();

    expect(fixture.componentInstance['errorMessage']()).toBe('');
    expect(fixture.componentInstance['showGoogleFallbackButton']()).toBe(false);

    fixture.destroy();
  });
});
