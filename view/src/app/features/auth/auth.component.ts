import type { OnInit } from '@angular/core';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  ElementRef,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import type { AuthApiResponse, PlanApiDto } from '@ribbit/shared-types';
import { AuthApiService } from './auth-api.service';
import { toApiError } from '../../core/api-error';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlanService } from '../../core/services/plan.service';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';

export interface PlanOption {
  readonly id: number;
  readonly name: string;
  readonly label: string;
}

interface GoogleCredentialResponse {
  readonly credential?: string;
}

interface GooglePromptMomentNotification {
  readonly isNotDisplayed?: () => boolean;
  readonly isSkippedMoment?: () => boolean;
  readonly isDismissedMoment?: () => boolean;
  readonly getDismissedReason?: () => string;
}

interface GoogleAccountsId {
  readonly initialize: (config: {
    readonly client_id: string;
    readonly callback: (response: GoogleCredentialResponse) => void;
    readonly ux_mode?: 'popup' | 'redirect';
    readonly cancel_on_tap_outside?: boolean;
  }) => void;
  readonly prompt: (
    momentListener?: (notification?: GooglePromptMomentNotification) => void,
  ) => void;
  readonly renderButton?: (
    parent: HTMLElement,
    options: {
      readonly type?: 'standard' | 'icon';
      readonly theme?: 'outline' | 'filled_blue' | 'filled_black';
      readonly size?: 'large' | 'medium' | 'small';
      readonly text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
      readonly shape?: 'rectangular' | 'pill' | 'circle' | 'square';
    },
  ) => void;
}

interface GoogleGlobalScope {
  readonly google?: {
    readonly accounts?: {
      readonly id?: GoogleAccountsId;
    };
  };
}

export const PLAN_OPTIONS: readonly PlanOption[] = [
  { id: 1, name: 'Free', label: 'Plano Free (R$ 0,00/mês)' },
  { id: 2, name: 'Individual', label: 'Ribbit Pro — Individual (R$ 14,90/mês)' },
  { id: 3, name: 'Família', label: 'Ribbit Jam — Família (R$ 27,90/mês)' },
];

function getGoogleAccountsId(): GoogleAccountsId | null {
  const win = globalThis as GoogleGlobalScope;
  return win.google?.accounts?.id ?? null;
}

function formatPlanOption(dto: PlanApiDto): PlanOption {
  const formattedPrice = `R$ ${dto.monthly_price.toFixed(2).replace('.', ',')}/mês`;
  return {
    id: dto.plan_id,
    name: dto.name,
    label: `Plano ${dto.name} (${formattedPrice})`,
  };
}

function parseBirthDate(raw: string): Date | null {
  if (!raw) return null;
  const parts = raw.split('-');
  if (parts.length !== 3) return null;
  const birth = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  return Number.isNaN(birth.getTime()) ? null : birth;
}

function computeAge(birth: Date, today: Date): number {
  let age = today.getFullYear() - birth.getFullYear();
  const monthDiff = today.getMonth() - birth.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
    age--;
  }
  return age;
}

function isFutureBirthDate(birth: Date, today: Date): boolean {
  const endOfToday = new Date(today.getTime());
  endOfToday.setHours(23, 59, 59, 999);
  return birth.getTime() > endOfToday.getTime();
}

/** Handles real user authentication and registration against /api/auth. */
@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [FrogComponent, IconComponent],
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuthComponent implements OnInit {
  private readonly authApi = inject(AuthApiService);
  private readonly planService = inject(PlanService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly hostRef = inject<ElementRef<HTMLElement>>(ElementRef, { optional: true });
  private readonly router = inject(Router, { optional: true });
  protected readonly state = inject(RibbitStateService);

  private initializedGoogleClientId: string | null = null;

  readonly planOptions = signal<readonly PlanOption[]>(PLAN_OPTIONS);
  readonly googleClientId = signal<string | null>(null);
  readonly isLoadingGoogleConfig = signal<boolean>(false);
  readonly showGoogleFallbackButton = signal<boolean>(false);
  readonly authMode = signal<'login' | 'register' | 'forgot-password'>('login');
  readonly forgotSubmitted = signal<boolean>(false);
  readonly nameDraft = signal<string>('');
  readonly emailDraft = signal<string>('');
  readonly birthDateDraft = signal<string>('');
  readonly passwordDraft = signal<string>('');
  readonly confirmPasswordDraft = signal<string>('');
  readonly selectedPlanId = signal<number>(1);
  readonly errorMessage = signal<string>('');
  readonly infoMessage = signal<string>('');
  readonly isSubmitting = signal<boolean>(false);

  readonly authView = computed<'login' | 'register' | 'forgot-password'>(() => {
    const mode = this.authMode();
    if (mode === 'forgot-password' || this.state.authView() === 'forgot-password') {
      return 'forgot-password';
    }
    if (mode === 'register' || this.state.authView() === 'register') {
      return 'register';
    }
    return 'login';
  });

  readonly calculatedAge = computed<number | null>(() => {
    const birth = parseBirthDate(this.birthDateDraft());
    return birth ? computeAge(birth, new Date()) : null;
  });

  readonly isFutureDate = computed<boolean>(() => {
    const birth = parseBirthDate(this.birthDateDraft());
    return birth ? isFutureBirthDate(birth, new Date()) : false;
  });

  readonly isUnderage = computed<boolean>(() => {
    const age = this.calculatedAge();
    if (age === null || this.isFutureDate()) return false;
    return age < 18;
  });

  readonly underageWarning = computed<string>(() => {
    if (this.isFutureDate()) {
      return 'A data de nascimento não pode estar no futuro.';
    }
    if (this.isUnderage()) {
      return 'Cadastro direto permitido apenas para maiores de 18 anos.';
    }
    return '';
  });

  readonly passwordTooShort = computed<boolean>(() => {
    const len = this.passwordDraft().length;
    return len > 0 && len < 6;
  });

  readonly passwordRequirementHint = computed<string>(() => {
    const len = this.passwordDraft().length;
    if (len === 0) {
      return 'A senha deve ter no mínimo 6 caracteres.';
    }
    if (len < 6) {
      return `A senha precisa ter pelo menos 6 caracteres (${len}/6).`;
    }
    return 'Tamanho mínimo atingido (6+ caracteres).';
  });

  readonly passwordMismatch = computed<boolean>(() => {
    const p1 = this.passwordDraft();
    const p2 = this.confirmPasswordDraft();
    return Boolean(p1 && p2 && p1 !== p2);
  });

  readonly maxBirthDate = computed<string>(() => new Date().toISOString().split('T')[0] ?? '');

  readonly canSubmitRegister = computed<boolean>(() => {
    const nameValid = this.nameDraft().trim().length >= 2;
    const emailValid = this.emailDraft().trim().includes('@');
    const birthValid = this.calculatedAge() !== null && !this.isUnderage() && !this.isFutureDate();
    const passwordValid = this.passwordDraft().length >= 6;
    const passwordsMatch = this.passwordDraft() === this.confirmPasswordDraft();
    return Boolean(nameValid && emailValid && birthValid && passwordValid && passwordsMatch);
  });

  ngOnInit(): void {
    this.planService
      .loadPlanDtos()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (dtos) => {
          if (dtos.length > 0) {
            this.planOptions.set(dtos.map((dto) => formatPlanOption(dto)));
          }
        },
        error: () => {
          // Fallback PLAN_OPTIONS remains available when /api/plans is offline
        },
      });
    this.authApi
      .getGoogleClientId()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          const trimmed = response.client_id?.trim();
          if (trimmed) {
            this.googleClientId.set(trimmed);
          }
        },
        error: () => {
          // Defer error surfacing until user triggers Google sign-in
        },
      });
    this.handleGoogleOAuthReturn();
  }

  isRegister(): boolean {
    return this.authView() === 'register';
  }

  isForgot(): boolean {
    return this.authView() === 'forgot-password';
  }

  toggleView(): void {
    this.errorMessage.set('');
    this.infoMessage.set('');
    this.forgotSubmitted.set(false);
    this.showGoogleFallbackButton.set(false);
    this.selectedPlanId.set(1);
    const next = this.isRegister() ? 'login' : 'register';
    this.authMode.set(next);
    this.state.setAuthView(next);
  }

  onForgot(): void {
    this.errorMessage.set('');
    this.infoMessage.set('');
    this.forgotSubmitted.set(false);
    this.showGoogleFallbackButton.set(false);
    this.authMode.set('forgot-password');
    this.state.setAuthView('forgot-password');
  }

  backToLogin(): void {
    this.errorMessage.set('');
    this.infoMessage.set('');
    this.forgotSubmitted.set(false);
    this.showGoogleFallbackButton.set(false);
    this.authMode.set('login');
    this.state.setAuthView('login');
  }

  /**
   * Dispatches a password recovery request.
   * Note: The FastAPI backend currently lacks a POST /api/auth/forgot-password route.
   */
  requestPasswordReset(email?: string): void {
    if (email !== undefined) {
      this.emailDraft.set(email);
    }
    const targetEmail = (email ?? this.emailDraft()).trim();
    if (!targetEmail.includes('@')) {
      this.errorMessage.set('Informe um e-mail válido para recuperação.');
      return;
    }
    this.isSubmitting.set(true);
    this.errorMessage.set('');
    // Simula disparo de recuperação de conta (pendente de endpoint no backend: POST /api/auth/forgot-password)
    setTimeout(() => {
      this.isSubmitting.set(false);
      this.forgotSubmitted.set(true);
      this.state.notify(
        'Se este e-mail estiver cadastrado, enviamos as instruções de recuperação.',
      );
    }, 400);
  }

  submitForgotPassword(): void {
    this.requestPasswordReset(this.emailDraft());
  }

  onGoogleLogin(): void {
    if (this.isSubmitting() || this.isLoadingGoogleConfig() || this.isForgot()) return;
    this.errorMessage.set('');
    this.infoMessage.set('');
    this.isLoadingGoogleConfig.set(true);

    this.authApi
      .getGoogleAuthorizeUrl()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isLoadingGoogleConfig.set(false);
          if (this.isSubmitting() || this.isForgot()) return;
          const rawUrl = res.authorization_url?.trim();
          if (this.isValidGoogleAuthorizeUrl(rawUrl)) {
            this.navigateToExternalUrl(rawUrl);
            return;
          }
          this.triggerGoogleIdentityServicesPrompt();
        },
        error: () => {
          this.isLoadingGoogleConfig.set(false);
          this.triggerGoogleIdentityServicesPrompt();
        },
      });
  }

  triggerGoogleIdentityServicesPrompt(): void {
    if (this.isSubmitting() || this.isLoadingGoogleConfig() || this.isForgot()) return;
    const clientId = this.googleClientId();
    if (clientId) {
      this.promptGoogleIdentity(clientId);
      return;
    }
    this.fetchGoogleClientIdAndPrompt();
  }

  private handleGoogleOAuthReturn(): void {
    if (typeof window === 'undefined' || !window.location.search) {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const googleAuthStatus = params.get('google_auth');
    if (googleAuthStatus === 'complete' || googleAuthStatus === 'register') {
      window.history.replaceState({}, '', window.location.pathname);
      this.isSubmitting.set(true);
      this.errorMessage.set('');
      this.infoMessage.set('');
      this.authApi
        .completeGoogleOAuthSession()
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (response) => {
            this.finishGoogleAuthSuccess(response);
          },
          error: (err: unknown) => {
            this.handleGoogleAuthError(err);
          },
        });
      return;
    }

    if (params.has('google_auth_error')) {
      window.history.replaceState({}, '', window.location.pathname);
      const rawError = params.get('google_auth_error');
      const msg =
        rawError === 'access_denied'
          ? 'Autorização com o Google cancelada pelo usuário.'
          : 'Não foi possível autenticar com o Google. Tente novamente.';
      this.errorMessage.set(msg);
    }
  }

  private isValidGoogleAuthorizeUrl(rawUrl: unknown): rawUrl is string {
    if (typeof rawUrl !== 'string' || !rawUrl.trim()) {
      return false;
    }
    try {
      const parsed = new URL(rawUrl.trim());
      return parsed.protocol === 'https:' && parsed.hostname === 'accounts.google.com';
    } catch {
      return false;
    }
  }

  navigateToExternalUrl(url: string): void {
    if (typeof window !== 'undefined') {
      window.location.assign(url);
    }
  }

  /** Authenticates directly against POST /api/auth/google using a Google Identity ID token. */
  authenticateWithGoogleIdToken(idToken: string): void {
    if (this.isSubmitting()) return;
    const trimmedToken = idToken.trim();
    if (!trimmedToken) {
      this.errorMessage.set('Token do Google inválido.');
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set('');
    this.infoMessage.set('');

    this.authApi
      .loginWithGoogle({ id_token: trimmedToken })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.finishGoogleAuthSuccess(response);
        },
        error: (err: unknown) => {
          this.handleGoogleAuthError(err);
        },
      });
  }

  private handleGoogleAuthError(err: unknown): void {
    this.isSubmitting.set(false);
    const apiErr = toApiError(err);
    const details =
      typeof apiErr.details === 'object' && apiErr.details !== null
        ? (apiErr.details as Record<string, unknown>)
        : null;
    if (apiErr.status === 404 && details?.['registration_required'] === true) {
      const email = typeof details['email'] === 'string' ? details['email'].trim() : '';
      const displayName =
        typeof details['display_name'] === 'string' ? details['display_name'].trim() : '';
      this.forwardToGoogleRegistration(email, displayName);
      return;
    }
    this.errorMessage.set(apiErr.message);
  }

  private forwardToGoogleRegistration(email: string, displayName: string): void {
    this.errorMessage.set('');
    this.forgotSubmitted.set(false);
    this.showGoogleFallbackButton.set(false);
    this.selectedPlanId.set(1);
    if (displayName) {
      this.nameDraft.set(displayName);
    }
    if (email) {
      this.emailDraft.set(email);
    }
    this.passwordDraft.set('');
    this.confirmPasswordDraft.set('');
    this.authMode.set('register');
    this.state.setAuthView('register');
    this.infoMessage.set(
      'Nenhuma conta Ribbit encontrada para este e-mail Google. Complete seu cadastro abaixo.',
    );
  }

  private fetchGoogleClientIdAndPrompt(): void {
    this.isLoadingGoogleConfig.set(true);
    this.authApi
      .getGoogleClientId()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.isLoadingGoogleConfig.set(false);
          if (this.isSubmitting() || this.isForgot()) return;
          const clientId = response.client_id?.trim();
          if (!clientId) {
            this.errorMessage.set(
              'Login com Google indisponível: GOOGLE_CLIENT_ID não configurado no servidor.',
            );
            return;
          }
          this.googleClientId.set(clientId);
          this.promptGoogleIdentity(clientId);
        },
        error: (err: unknown) => {
          this.isLoadingGoogleConfig.set(false);
          if (this.isSubmitting() || this.isForgot()) return;
          this.errorMessage.set(toApiError(err).message);
        },
      });
  }

  private ensureGoogleInitialized(googleId: GoogleAccountsId, clientId: string): void {
    if (this.initializedGoogleClientId === clientId) {
      return;
    }
    googleId.initialize({
      client_id: clientId,
      callback: (response) => {
        this.authenticateWithGoogleIdToken(response.credential ?? '');
      },
      ux_mode: 'popup',
      cancel_on_tap_outside: true,
    });
    this.initializedGoogleClientId = clientId;
  }

  private renderGoogleFallbackButton(googleId: GoogleAccountsId): boolean {
    if (!googleId.renderButton) {
      return false;
    }
    const container =
      this.hostRef?.nativeElement.querySelector<HTMLElement>('.google-gsi-fallback');
    if (!container) {
      return false;
    }
    if (container.dataset['gsiRendered'] !== 'true') {
      googleId.renderButton(container, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'pill',
      });
      container.dataset['gsiRendered'] = 'true';
    }
    this.showGoogleFallbackButton.set(true);
    container.classList.add('visible');
    container.focus();
    return true;
  }

  private isGooglePromptDismissed(notification: GooglePromptMomentNotification): boolean {
    return Boolean(
      notification.isDismissedMoment?.() &&
      notification.getDismissedReason?.() !== 'credential_returned',
    );
  }

  private isGooglePromptSuppressed(notification: GooglePromptMomentNotification): boolean {
    return Boolean(notification.isNotDisplayed?.() || notification.isSkippedMoment?.());
  }

  private handleGooglePromptMoment(
    googleId: GoogleAccountsId,
    notification?: GooglePromptMomentNotification,
  ): void {
    if (!notification || this.isForgot() || this.isSubmitting()) {
      return;
    }
    if (this.isGooglePromptDismissed(notification)) {
      this.renderGoogleFallbackButton(googleId);
      return;
    }
    if (this.isGooglePromptSuppressed(notification) && !this.renderGoogleFallbackButton(googleId)) {
      this.errorMessage.set(
        'Não foi possível exibir o modal do Google. Verifique as permissões do navegador.',
      );
    }
  }

  private promptGoogleIdentity(clientId: string): void {
    if (this.isSubmitting() || this.isForgot()) return;
    const googleId = getGoogleAccountsId();
    if (!googleId) {
      this.errorMessage.set('Serviço de autenticação do Google indisponível no navegador.');
      return;
    }
    this.ensureGoogleInitialized(googleId, clientId);
    this.renderGoogleFallbackButton(googleId);
    googleId.prompt((notification) => {
      this.handleGooglePromptMoment(googleId, notification);
    });
  }

  private finishGoogleAuthSuccess(response: AuthApiResponse): void {
    this.isSubmitting.set(false);
    this.errorMessage.set('');
    this.showGoogleFallbackButton.set(false);
    this.state.completeAuthentication(response);
    this.state.notify(`Conectado com Google como ${response.user.display_name}.`);
  }

  openAdminConsole(): void {
    this.router?.navigate(['/admin']).catch(() => {});
  }

  onNameChange(event: Event): void {
    this.nameDraft.set((event.target as HTMLInputElement).value);
  }

  onEmailChange(event: Event): void {
    this.emailDraft.set((event.target as HTMLInputElement).value);
  }

  onBirthDateChange(event: Event): void {
    this.birthDateDraft.set((event.target as HTMLInputElement).value);
  }

  onPasswordChange(event: Event): void {
    this.passwordDraft.set((event.target as HTMLInputElement).value);
  }

  onConfirmPasswordChange(event: Event): void {
    this.confirmPasswordDraft.set((event.target as HTMLInputElement).value);
  }

  onPlanChange(event: Event): void {
    this.selectedPlanId.set(Number((event.target as HTMLSelectElement).value));
  }

  onSubmit(event: Event): void {
    event.preventDefault();
    if (this.isSubmitting()) return;
    this.errorMessage.set('');
    this.infoMessage.set('');

    if (this.isForgot()) {
      this.submitForgotPassword();
      return;
    }

    if (this.isRegister()) {
      this.submitRegister();
      return;
    }
    this.submitLogin();
  }

  private validateRegisterForm(): string | null {
    if (this.nameDraft().trim().length < 2) {
      return 'O nome de exibição deve ter pelo menos 2 caracteres.';
    }
    if (!this.emailDraft().trim().includes('@')) {
      return 'Informe um e-mail válido.';
    }
    if (this.isFutureDate()) {
      return 'Data de nascimento não pode estar no futuro.';
    }
    const age = this.calculatedAge();
    if (age === null || age < 18) {
      return 'Cadastro direto permitido apenas para maiores de 18 anos.';
    }
    if (this.passwordDraft().length < 6) {
      return 'A senha deve ter pelo menos 6 caracteres.';
    }
    if (this.passwordDraft() !== this.confirmPasswordDraft()) {
      return 'As senhas não coincidem.';
    }
    return null;
  }

  private submitRegister(): void {
    const validationError = this.validateRegisterForm();
    if (validationError) {
      this.errorMessage.set(validationError);
      return;
    }

    const options = this.planOptions();
    const selectedPlan = options.find((item) => item.id === this.selectedPlanId()) ?? options[0]!;
    const displayName = this.nameDraft().trim();

    this.isSubmitting.set(true);
    this.authApi
      .register({
        email: this.emailDraft().trim(),
        password: this.passwordDraft(),
        display_name: displayName,
        birth_date: this.birthDateDraft(),
        plan_id: selectedPlan.id,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.isSubmitting.set(false);
          this.state.completeAuthentication(response, selectedPlan.name);
          this.state.notify(
            `Conta criada com sucesso no Plano ${selectedPlan.name}. Bem-vindo ao Ribbit, ${displayName}!`,
          );
        },
        error: (err: unknown) => {
          this.isSubmitting.set(false);
          this.errorMessage.set(toApiError(err).message);
        },
      });
  }

  private submitLogin(): void {
    const email = this.emailDraft().trim();
    const password = this.passwordDraft();
    if (!email.includes('@') || password.length < 1) {
      this.errorMessage.set('Informe seu e-mail e sua senha para entrar.');
      return;
    }

    this.isSubmitting.set(true);
    this.authApi
      .login({ email, password })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.isSubmitting.set(false);
          this.state.completeAuthentication(response);
          this.state.notify('Login realizado com sucesso.');
        },
        error: (err: unknown) => {
          this.isSubmitting.set(false);
          this.errorMessage.set(toApiError(err).message);
        },
      });
  }
}
