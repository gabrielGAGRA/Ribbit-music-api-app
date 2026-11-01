import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';

export interface PlanOption {
  readonly id: number;
  readonly name: string;
  readonly label: string;
}

export const PLAN_OPTIONS: readonly PlanOption[] = [
  { id: 1, name: 'Free', label: 'Plano Free (R$ 0,00/mês)' },
  { id: 2, name: 'Plus', label: 'Ribbit Plus (R$ 14,90/mês)' },
  { id: 3, name: 'Duo', label: 'Ribbit Duo (R$ 21,90/mês)' },
  { id: 4, name: 'Família', label: 'Ribbit Família (R$ 34,90/mês)' },
];

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [FrogComponent, IconComponent],
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuthComponent {
  readonly planOptions = PLAN_OPTIONS;

  readonly nameDraft = signal<string>('');
  readonly emailDraft = signal<string>('');
  readonly birthDateDraft = signal<string>('');
  readonly passwordDraft = signal<string>('');
  readonly confirmPasswordDraft = signal<string>('');
  readonly selectedPlanId = signal<number>(1);
  readonly errorMessage = signal<string>('');

  readonly calculatedAge = computed<number | null>(() => {
    const raw = this.birthDateDraft();
    if (!raw) return null;
    const parts = raw.split('-');
    if (parts.length !== 3) return null;
    const birthYear = Number(parts[0]);
    const birthMonth = Number(parts[1]) - 1;
    const birthDay = Number(parts[2]);
    const birth = new Date(birthYear, birthMonth, birthDay);
    if (isNaN(birth.getTime())) return null;

    const today = new Date();
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--;
    }
    return age;
  });

  readonly isFutureDate = computed<boolean>(() => {
    const raw = this.birthDateDraft();
    if (!raw) return false;
    const parts = raw.split('-');
    if (parts.length !== 3) return false;
    const birth = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
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

  readonly maxBirthDate = computed<string>(() => {
    return new Date().toISOString().split('T')[0];
  });

  readonly canSubmitRegister = computed<boolean>(() => {
    const nameValid = this.nameDraft().trim().length >= 2;
    const emailValid = this.emailDraft().trim().includes('@');
    const birthValid = this.calculatedAge() !== null && !this.isUnderage() && !this.isFutureDate();
    const passwordValid = this.passwordDraft().length >= 6;
    const passwordsMatch = this.passwordDraft() === this.confirmPasswordDraft();
    return Boolean(nameValid && emailValid && birthValid && passwordValid && passwordsMatch);
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
  ) {}

  isRegister(): boolean {
    return this.state.authView() === 'register';
  }

  toggleView(): void {
    this.errorMessage.set('');
    this.state.setAuthView(this.isRegister() ? 'login' : 'register');
  }

  returnToApp(): void {
    this.state.setAuthView('app');
  }

  onForgot(): void {
    this.state.notify('Instruções de recuperação enviadas para o seu e-mail.');
  }

  onGoogleLogin(): void {
    this.state.notify('Login social disponível apenas na versão integrada.');
  }

  onNameChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.nameDraft.set(target.value);
  }

  onEmailChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.emailDraft.set(target.value);
  }

  onBirthDateChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.birthDateDraft.set(target.value);
  }

  onPasswordChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.passwordDraft.set(target.value);
  }

  onConfirmPasswordChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.confirmPasswordDraft.set(target.value);
  }

  onPlanChange(event: Event): void {
    const target = event.target as HTMLSelectElement;
    this.selectedPlanId.set(Number(target.value));
  }

  onSubmit(event: Event): void {
    event.preventDefault();
    this.errorMessage.set('');

    if (this.isRegister()) {
      const name = this.nameDraft().trim();
      if (name.length < 2) {
        this.errorMessage.set('O nome de exibição deve ter pelo menos 2 caracteres.');
        return;
      }

      const email = this.emailDraft().trim();
      if (!email.includes('@')) {
        this.errorMessage.set('Informe um e-mail válido.');
        return;
      }

      if (this.isFutureDate()) {
        this.errorMessage.set('Data de nascimento não pode estar no futuro.');
        return;
      }

      const age = this.calculatedAge();
      if (age === null || age < 18) {
        this.errorMessage.set('Cadastro direto permitido apenas para maiores de 18 anos.');
        return;
      }

      const password = this.passwordDraft();
      if (password.length < 6) {
        this.errorMessage.set('A senha deve ter pelo menos 6 caracteres.');
        return;
      }

      if (password !== this.confirmPasswordDraft()) {
        this.errorMessage.set('As senhas não coincidem.');
        return;
      }

      const selectedPlan =
        this.planOptions.find((p) => p.id === this.selectedPlanId()) ?? this.planOptions[0];

      this.state.setUserName(name);
      this.state.setPlan(selectedPlan.name);
      this.state.setAuthView('app');
      this.state.notify(
        `Conta criada com sucesso no Plano ${selectedPlan.name}. Bem-vindo ao Ribbit, ${name}!`,
      );
    } else {
      this.state.setAuthView('app');
      this.state.notify('Login realizado com sucesso.');
    }
  }
}
