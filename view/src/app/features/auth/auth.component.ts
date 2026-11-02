import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { PlanApiDto } from '@ribbit/shared-types';
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

export const PLAN_OPTIONS: readonly PlanOption[] = [
  { id: 1, name: 'Free', label: 'Plano Free (R$ 0,00/mês)' },
  { id: 2, name: 'Individual', label: 'Ribbit Pro — Individual (R$ 14,90/mês)' },
  { id: 3, name: 'Família', label: 'Ribbit Jam — Família (R$ 27,90/mês)' },
];

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
  protected readonly state = inject(RibbitStateService);

  readonly planOptions = signal<readonly PlanOption[]>(PLAN_OPTIONS);
  readonly nameDraft = signal<string>('');
  readonly emailDraft = signal<string>('');
  readonly birthDateDraft = signal<string>('');
  readonly passwordDraft = signal<string>('');
  readonly confirmPasswordDraft = signal<string>('');
  readonly selectedPlanId = signal<number>(1);
  readonly errorMessage = signal<string>('');
  readonly isSubmitting = signal<boolean>(false);

  readonly calculatedAge = computed<number | null>(() => {
    const birth = parseBirthDate(this.birthDateDraft());
    if (!birth) return null;
    const today = new Date();
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--;
    }
    return age;
  });

  readonly isFutureDate = computed<boolean>(() => {
    const birth = parseBirthDate(this.birthDateDraft());
    if (!birth) return false;
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    return birth.getTime() > today.getTime();
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
    this.planService.loadPlanDtos().subscribe({
      next: (dtos) => {
        if (dtos.length > 0) {
          this.planOptions.set(dtos.map((dto) => formatPlanOption(dto)));
        }
      },
      error: () => {
        // Fallback PLAN_OPTIONS remains available when /api/plans is offline
      },
    });
  }

  isRegister(): boolean {
    return this.state.authView() === 'register';
  }

  toggleView(): void {
    this.errorMessage.set('');
    this.state.setAuthView(this.isRegister() ? 'login' : 'register');
  }

  onForgot(): void {
    this.state.notify('Entre em contato com o suporte para redefinir sua senha.');
  }

  onGoogleLogin(): void {
    this.state.notify('Use seu e-mail e senha para autenticar no Ribbit.');
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
    this.authApi.login({ email, password }).subscribe({
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
