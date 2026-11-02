import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AuthComponent } from './auth.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { RibbitStateService } from '../../core/ribbit-state.service';

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
  });

  it('should toggle between login and register views', () => {
    state.setAuthView('login');
    expect(component.isRegister()).toBe(false);

    component.toggleView();
    expect(component.isRegister()).toBe(true);

    component.toggleView();
    expect(component.isRegister()).toBe(false);
  });

  it('should calculate age correctly from birth date', () => {
    component.birthDateDraft.set('2000-01-15');
    const age = component.calculatedAge();
    expect(age).toBeGreaterThanOrEqual(24);
    expect(component.isUnderage()).toBe(false);
    expect(component.isFutureDate()).toBe(false);
  });

  it('should block registration for underage birth dates (< 18 years old)', () => {
    const today = new Date();
    const underageYear = today.getFullYear() - 14;
    const formatted = `${underageYear}-05-20`;
    component.birthDateDraft.set(formatted);

    expect(component.isUnderage()).toBe(true);
    expect(component.underageWarning()).toContain(
      'Cadastro direto permitido apenas para maiores de 18 anos',
    );
    expect(component.canSubmitRegister()).toBe(false);
  });

  it('should block registration for future birth dates', () => {
    const nextYear = new Date().getFullYear() + 2;
    component.birthDateDraft.set(`${nextYear}-01-01`);

    expect(component.isFutureDate()).toBe(true);
    expect(component.underageWarning()).toContain('futuro');
    expect(component.canSubmitRegister()).toBe(false);
  });

  it('should detect password mismatches and enforce minimum length', () => {
    component.passwordDraft.set('12345');
    component.confirmPasswordDraft.set('12345');
    expect(component.canSubmitRegister()).toBe(false);

    component.passwordDraft.set('senhaForte123');
    component.confirmPasswordDraft.set('outraSenha');
    expect(component.passwordMismatch()).toBe(true);
    expect(component.canSubmitRegister()).toBe(false);

    component.confirmPasswordDraft.set('senhaForte123');
    expect(component.passwordMismatch()).toBe(false);
  });

  it('should register via POST /api/auth/register and set authenticated state', () => {
    state.setAuthView('register');
    component.nameDraft.set('Carolina Santos');
    component.emailDraft.set('carolina@email.com');
    component.birthDateDraft.set('1998-03-25');
    component.passwordDraft.set('senhaSegura123');
    component.confirmPasswordDraft.set('senhaSegura123');
    component.selectedPlanId.set(2);

    expect(component.canSubmitRegister()).toBe(true);

    component.onSubmit(new Event('submit'));
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
    expect(state.authView()).toBe('app');
    expect(state.toast()).toContain('Carolina Santos');
  });

  it('should perform login via POST /api/auth/login and surface backend errors on 401', () => {
    state.setAuthView('login');
    component.emailDraft.set('user@ribbit.app');
    component.passwordDraft.set('wrongpass');

    component.onSubmit(new Event('submit'));
    const failedReq = httpMock.expectOne('/api/auth/login');
    failedReq.flush(
      { detail: 'Invalid email or password.' },
      { status: 401, statusText: 'Unauthorized' },
    );
    expect(component.errorMessage()).toContain('Invalid email or password.');
    expect(state.authView()).toBe('login');

    component.passwordDraft.set('correctpass');
    component.onSubmit(new Event('submit'));
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

    expect(state.authView()).toBe('app');
    expect(state.toast()).toContain('Login realizado com sucesso');
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
});
