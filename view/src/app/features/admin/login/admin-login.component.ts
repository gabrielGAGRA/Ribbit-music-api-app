import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { readInputValue } from '@shared/dom-event-values';
import { FrogComponent } from '@shared/frog.component';
import { IconComponent } from '@shared/icon.component';
import { AdminStateService } from '../admin-state.service';

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
  private readonly adminState = inject(AdminStateService);
  private readonly router = inject(Router, { optional: true });

  protected readonly emailDraft = signal<string>('');
  protected readonly passwordDraft = signal<string>('');
  protected readonly errorMessage = signal<string>('');
  protected readonly isSubmitting = signal<boolean>(false);
  private readonly emailBlurred = signal<boolean>(false);
  private readonly passwordBlurred = signal<boolean>(false);

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
    this.emailDraft.set(readInputValue(event));
  }

  protected updatePassword(event: Event): void {
    this.passwordDraft.set(readInputValue(event));
  }

  protected markEmailBlurred(): void {
    this.emailBlurred.set(true);
  }

  protected markPasswordBlurred(): void {
    this.passwordBlurred.set(true);
  }

  protected authenticateAdmin(event: Event): void {
    event.preventDefault();
    if (this.isSubmitting()) return;

    this.errorMessage.set('');
    this.emailBlurred.set(true);
    this.passwordBlurred.set(true);

    const email = this.emailDraft().trim();
    const password = this.passwordDraft();
    if (!email || !password) {
      this.errorMessage.set('Informe e-mail e senha de administrador.');
      return;
    }

    this.isSubmitting.set(true);
    this.adminState.loginAdmin(email, password).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        if (this.router) {
          this.router.navigate(['/admin/dashboard']).catch(() => {});
        }
      },
      error: (error: Error) => {
        this.isSubmitting.set(false);
        this.errorMessage.set(error.message);
      },
    });
  }

  protected returnToListenerApp(): void {
    if (this.router) {
      this.router.navigate(['/discover']).catch(() => {});
    }
  }
}
