import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { safeInject } from '../../core/safe-inject';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';
import { AdminStateService } from './admin-state.service';

/** Dedicated administrative sign-in screen backing POST /api/admin/login. */
@Component({
  selector: 'app-admin-login',
  standalone: true,
  imports: [FrogComponent, IconComponent],
  templateUrl: './admin-login.component.html',
  styleUrl: './admin-login.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminLoginComponent {
  protected readonly adminState = safeInject(AdminStateService, new AdminStateService());
  private readonly router = safeInject<Router | null>(Router, null);

  protected readonly emailDraft = signal<string>('');
  protected readonly passwordDraft = signal<string>('');
  protected readonly errorMessage = signal<string>('');
  protected readonly emailBlurred = signal<boolean>(false);
  protected readonly passwordBlurred = signal<boolean>(false);

  protected readonly isEmailFallbackInvalid = computed<boolean>(() => {
    if (!this.emailBlurred()) return false;
    const value = this.emailDraft().trim();
    return value.length > 0 && !value.includes('@');
  });

  protected readonly isPasswordFallbackInvalid = computed<boolean>(() => {
    if (!this.passwordBlurred()) return false;
    const value = this.passwordDraft();
    return value.length > 0 && value.length < 6;
  });

  protected updateEmail(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.emailDraft.set(target.value);
  }

  protected updatePassword(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.passwordDraft.set(target.value);
  }

  protected markEmailBlurred(): void {
    this.emailBlurred.set(true);
  }

  protected markPasswordBlurred(): void {
    this.passwordBlurred.set(true);
  }

  protected fillDemoCredentials(): void {
    this.errorMessage.set('');
    this.emailDraft.set(this.adminState.defaultAdminEmail);
    this.passwordDraft.set(this.adminState.defaultAdminPassword);
  }

  protected authenticateAdmin(event: Event): void {
    event.preventDefault();
    this.errorMessage.set('');
    this.emailBlurred.set(true);
    this.passwordBlurred.set(true);

    try {
      this.adminState.loginAdmin(this.emailDraft(), this.passwordDraft());
      if (this.router) {
        this.router.navigate(['/admin/dashboard']).catch(() => {});
      }
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Não foi possível autenticar no console.';
      this.errorMessage.set(message);
    }
  }

  protected returnToListenerApp(): void {
    if (this.router) {
      this.router.navigate(['/discover']).catch(() => {});
    }
  }
}
