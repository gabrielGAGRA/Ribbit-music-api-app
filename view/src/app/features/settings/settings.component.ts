import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { toApiError } from '../../core/api-error';
import { computeInitials } from '../../core/api-mappers';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { IconComponent } from '../../shared/icon.component';
import { ProfileApiService } from '../profile/profile-api.service';

/** Manages user account display name, credentials, Spotify connection, blocked genres, subscription status, and parental control navigation. */
@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent implements OnInit {
  protected readonly state = inject(RibbitStateService);
  private readonly profileApi = inject(ProfileApiService);
  private readonly router = inject(Router, { optional: true });

  protected readonly isEditingName = signal<boolean>(false);
  protected readonly nameDraft = signal<string>(this.state.userName());
  protected readonly isSpotifyLinked = computed<boolean>(() => this.state.isSpotifyLinked());
  protected readonly spotifyFeedback = signal<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);
  protected readonly isLinkingSpotify = signal<boolean>(false);
  private processedCallbackSearch: string | null = null;

  // Password change form state
  protected readonly currentPassword = signal<string>('');
  protected readonly newPassword = signal<string>('');
  protected readonly passwordError = signal<string>('');
  protected readonly passwordSuccess = signal<string>('');
  protected readonly isChangingPassword = signal<boolean>(false);

  ngOnInit(): void {
    this.handleSpotifyOAuthCallback();
  }

  protected readonly userInitials = computed<string>(() => computeInitials(this.state.userName()));

  protected startEditingName(): void {
    this.nameDraft.set(this.state.userName());
    this.isEditingName.set(true);
  }

  protected saveName(): void {
    const trimmed = this.nameDraft().trim();
    if (trimmed) {
      this.state.setUserName(trimmed);
    }
    this.isEditingName.set(false);
  }

  protected cancelEditingName(): void {
    this.nameDraft.set(this.state.userName());
    this.isEditingName.set(false);
  }

  protected updateNameDraft(event: Event): void {
    const value = event.target instanceof HTMLInputElement ? event.target.value : '';
    this.nameDraft.set(value);
  }

  protected connectSpotify(): void {
    if (this.isLinkingSpotify()) return;
    this.isLinkingSpotify.set(true);
    this.spotifyFeedback.set(null);
    this.profileApi.getSpotifyAuthorizeUrl().subscribe({
      next: (res: unknown) => {
        const rawUrl =
          typeof res === 'object' && res !== null && 'authorization_url' in res
            ? res.authorization_url
            : undefined;
        if (!this.isValidSpotifyAuthorizeUrl(rawUrl)) {
          this.isLinkingSpotify.set(false);
          this.reportSpotifyClientError('URL de autorização do Spotify inválida.');
          return;
        }
        this.navigateToExternalUrl(rawUrl.trim());
      },
      error: (err: unknown) => {
        this.handleSpotifyError(err);
      },
    });
  }

  private isValidSpotifyAuthorizeUrl(rawUrl: unknown): rawUrl is string {
    if (typeof rawUrl !== 'string' || !rawUrl.trim()) {
      return false;
    }
    try {
      const parsed = new URL(rawUrl.trim());
      return parsed.protocol === 'https:' && parsed.hostname === 'accounts.spotify.com';
    } catch {
      return false;
    }
  }

  private navigateToExternalUrl(url: string): void {
    if (typeof window !== 'undefined') {
      window.location.assign(url);
    }
  }

  protected disconnectSpotify(): void {
    if (this.isLinkingSpotify()) return;
    this.isLinkingSpotify.set(true);
    this.spotifyFeedback.set(null);
    this.profileApi.unlinkSpotify().subscribe({
      next: (updatedUser) => {
        this.isLinkingSpotify.set(false);
        this.state.applyUserDto(updatedUser);
        this.spotifyFeedback.set({
          type: 'success',
          message: 'Conta do Spotify desvinculada com sucesso.',
        });
        this.state.notify('Conta do Spotify desvinculada.');
      },
      error: (err: unknown) => {
        this.handleSpotifyError(err);
      },
    });
  }

  private readCallbackQueryParams(): URLSearchParams | null {
    if (typeof window === 'undefined' || !window.location.search) {
      return null;
    }
    return new URLSearchParams(window.location.search);
  }

  private clearSpotifyCallbackUrl(): void {
    this.state.setPage('settings');
    if (typeof window !== 'undefined') {
      window.history.replaceState({}, '', '/settings');
    }
  }

  private reportSpotifyClientError(message: string): void {
    this.spotifyFeedback.set({ type: 'error', message });
    this.state.notify(message);
  }

  private handleSpotifyOAuthCallback(): void {
    const params = this.readCallbackQueryParams();
    if (!params) return;

    if (params.get('error')) {
      this.clearSpotifyCallbackUrl();
      this.reportSpotifyClientError('Autorização com o Spotify foi cancelada ou recusada.');
      return;
    }

    if (!params.has('code') && !params.has('state')) return;
    if (!readAuthToken()) return;

    const rawSearch = window.location.search;
    if (this.processedCallbackSearch === rawSearch) return;
    this.processedCallbackSearch = rawSearch;

    const code = (params.get('code') ?? '').trim();
    const state = (params.get('state') ?? '').trim();
    this.exchangeSpotifyCode(code, state);
  }

  private exchangeSpotifyCode(code: string, state: string): void {
    if (!code || !state) {
      this.clearSpotifyCallbackUrl();
      this.reportSpotifyClientError('Parâmetros de retorno do Spotify ausentes ou inválidos.');
      return;
    }
    this.isLinkingSpotify.set(true);
    this.spotifyFeedback.set(null);
    this.profileApi.connectSpotifyCallback({ code, state }).subscribe({
      next: (updatedUser) => {
        this.clearSpotifyCallbackUrl();
        this.isLinkingSpotify.set(false);
        this.state.applyUserDto(updatedUser);
        const linkedId = updatedUser.spotify_id ?? 'Spotify';
        this.spotifyFeedback.set({
          type: 'success',
          message: `Conta do Spotify (${linkedId}) conectada com sucesso!`,
        });
        this.state.notify(`Conta do Spotify (${linkedId}) vinculada com sucesso.`);
      },
      error: (err: unknown) => {
        if (readAuthToken()) {
          this.clearSpotifyCallbackUrl();
        }
        this.handleSpotifyError(err);
      },
    });
  }

  private extractDetail(err: unknown): string | null {
    if (typeof err !== 'object' || err === null || !('error' in err)) return null;
    const inner = err.error;
    if (typeof inner !== 'object' || inner === null || !('detail' in inner)) return null;
    return typeof inner.detail === 'string' ? inner.detail : null;
  }

  private handleSpotifyError(err: unknown): void {
    this.isLinkingSpotify.set(false);
    const detail = this.extractDetail(err);
    this.reportSpotifyClientError(detail ?? toApiError(err).message);
  }

  protected goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']).catch(() => false);
  }

  protected goToFamily(): void {
    this.state.setPage('family');
    void this.router?.navigate(['/family']).catch(() => false);
  }

  protected openBlockedGenresModal(): void {
    this.state.setModal('filters');
  }

  protected removeBlockedGenre(genre: string): void {
    const updated = this.state.blockedGenres().filter((g) => g !== genre);
    this.state.setBlockedGenres(updated);
  }

  protected setTheme(theme: 'light' | 'dark'): void {
    this.state.setTheme(theme);
  }

  protected openOnboardingModal(): void {
    this.state.setModal('onboarding');
  }

  protected cancelSubscription(): void {
    this.state.cancelSubscription();
  }

  protected openDeleteModal(): void {
    this.state.setModal('delete');
  }

  protected logout(): void {
    this.state.logout();
  }

  // --- Password Management ---

  protected updateCurrentPasswordDraft(event: Event): void {
    const value = event.target instanceof HTMLInputElement ? event.target.value : '';
    this.currentPassword.set(value);
  }

  protected updateNewPasswordDraft(event: Event): void {
    const value = event.target instanceof HTMLInputElement ? event.target.value : '';
    this.newPassword.set(value);
  }

  protected updatePassword(): void {
    const current = this.currentPassword().trim();
    const next = this.newPassword().trim();

    if (!current || !next) {
      this.passwordError.set('Informe a senha atual e a nova senha.');
      return;
    }
    if (next.length < 6) {
      this.passwordError.set('A nova senha deve ter no mínimo 6 caracteres.');
      return;
    }

    this.passwordError.set('');
    this.passwordSuccess.set('');
    this.isChangingPassword.set(true);

    this.profileApi.updateProfile({ currentPassword: current, newPassword: next }).subscribe({
      next: () => {
        this.currentPassword.set('');
        this.newPassword.set('');
        this.passwordSuccess.set('Senha alterada com sucesso!');
        this.isChangingPassword.set(false);
        this.state.notify('Senha alterada com sucesso.');
      },
      error: (err: unknown) => {
        this.isChangingPassword.set(false);
        const message = this.extractDetail(err) ?? toApiError(err).message;
        this.passwordError.set(message);
      },
    });
  }

  protected openAdminConsole(): void {
    this.router?.navigate(['/admin']).catch(() => {});
  }
}
