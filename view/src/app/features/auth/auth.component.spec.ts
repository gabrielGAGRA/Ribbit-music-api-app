import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect, beforeEach } from 'vitest';
import { AuthComponent } from './auth.component';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('AuthComponent', () => {
  let component: AuthComponent;
  let state: RibbitStateService;

  beforeEach(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.clear();
    }
    state = new RibbitStateService();
    component = new AuthComponent(state);
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
    expect(component.underageWarning()).toContain('Cadastro direto permitido apenas para maiores de 18 anos');
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
    expect(component.canSubmitRegister()).toBe(false); // password length < 6

    component.passwordDraft.set('senhaForte123');
    component.confirmPasswordDraft.set('outraSenha');
    expect(component.passwordMismatch()).toBe(true);
    expect(component.canSubmitRegister()).toBe(false);

    component.confirmPasswordDraft.set('senhaForte123');
    expect(component.passwordMismatch()).toBe(false);
  });

  it('should allow valid registration with all Swagger required fields and set plan', () => {
    state.setAuthView('register');
    component.nameDraft.set('Carolina Santos');
    component.emailDraft.set('carolina@email.com');
    component.birthDateDraft.set('1998-03-25');
    component.passwordDraft.set('senhaSegura123');
    component.confirmPasswordDraft.set('senhaSegura123');
    component.selectedPlanId.set(2); // Plus

    expect(component.canSubmitRegister()).toBe(true);

    const fakeEvent = { preventDefault: () => {} } as unknown as Event;
    component.onSubmit(fakeEvent);

    expect(state.userName()).toBe('Carolina Santos');
    expect(state.currentPlan()).toBe('Plus');
    expect(state.authView()).toBe('app');
    expect(state.toast()).toContain('Carolina Santos');
  });

  it('should perform login when in login view', () => {
    state.setAuthView('login');
    const fakeEvent = { preventDefault: () => {} } as unknown as Event;
    component.onSubmit(fakeEvent);

    expect(state.authView()).toBe('app');
    expect(state.toast()).toContain('Login realizado com sucesso');
  });

  it('should configure mobile auth branding, 16px inputs, and bottom-sheet modals', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');
    const modalsTemplate = readFileSync(resolve(__dirname, '../../shared/modals.component.html'), 'utf8');

    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*900px\)[\s\S]*\.auth-mobile-logo\s*\{[^}]*display:\s*inline-flex/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.modal\s*\{[^}]*border-radius:\s*20px 20px 0 0/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*font-size:\s*16px/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.event-builder-row\s+select\s*\{[^}]*font-size:\s*16px\s*!important/);
    expect(modalsTemplate.indexOf('bottom-sheet-handle')).toBeLessThan(modalsTemplate.indexOf("@if (state.activeModal() === 'save-queue')"));
  });
});
