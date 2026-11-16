import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { toApiError } from '../../core/api-error';
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
  protected readonly profileApi = inject(ProfileApiService);
  private readonly router = inject(Router, { optional: true });

  readonly isEditingName = signal<boolean>(false);
  readonly nameDraft = signal<string>(this.state.userName());
  readonly isSpotifyLinked = computed<boolean>(() => this.state.isSpotifyLinked());
  readonly spotifyFeedback = signal<{ type: 'success' | 'error'; message: string } | null>(null);
  readonly isLinkingSpotify = signal<boolean>(false);
  private processedCallbackSearch: string | null = null;

  // Password change form state
  readonly currentPassword = signal<string>('');
  readonly newPassword = signal<string>('');
  readonly passwordError = signal<string>('');
  readonly passwordSuccess = signal<string>('');
  readonly isChangingPassword = signal<boolean>(false);

  ngOnInit(): void {
    this.handleSpotifyOAuthCallback();
  }

  readonly userInitials = computed<string>(() => {
    const parts = this.state
      .userName()
      .trim()
      .split(/\s+/)
      .filter((part) => part.length > 0);
    if (parts.length >= 2) {
      return `${parts[0]![0] ?? ''}${parts[1]![0] ?? ''}`.toUpperCase();
    }
    return this.state.userName().slice(0, 2).toUpperCase() || 'RB';
  });

  startEditingName(): void {
    this.nameDraft.set(this.state.userName());
    this.isEditingName.set(true);
  }

  saveName(): void {
    const trimmed = this.nameDraft().trim();
    if (trimmed) {
      this.state.setUserName(trimmed);
    }
    this.isEditingName.set(false);
  }

  cancelEditingName(): void {
    this.nameDraft.set(this.state.userName());
    this.isEditingName.set(false);
  }

  onNameInput(event: Event): void {
    this.nameDraft.set((event.target as HTMLInputElement).value);
  }

  connectSpotify(): void {
    if (this.isLinkingSpotify()) return;
    this.isLinkingSpotify.set(true);
    this.spotifyFeedback.set(null);
    this.profileApi.getSpotifyAuthorizeUrl().subscribe({
      next: (res) => {
        const rawUrl = (res as { authorization_url?: unknown } | null)?.authorization_url;
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

  navigateToExternalUrl(url: string): void {
    if (typeof window !== 'undefined') {
      window.location.assign(url);
    }
  }

  disconnectSpotify(): void {
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

  toggleSpotify(): void {
    if (this.isSpotifyLinked()) {
      this.disconnectSpotify();
    } else {
      this.connectSpotify();
    }
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

  private handleSpotifyError(err: unknown): void {
    this.isLinkingSpotify.set(false);
    const detail = (err as { error?: { detail?: string } }).error?.detail;
    this.reportSpotifyClientError(detail ?? toApiError(err).message);
  }

  goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']).catch(() => false);
  }

  goToFamily(): void {
    this.state.setPage('family');
    void this.router?.navigate(['/family']).catch(() => false);
  }

  openBlockedGenresModal(): void {
    this.state.setModal('filters');
  }

  removeBlockedGenre(genre: string): void {
    const updated = this.state.blockedGenres().filter((g) => g !== genre);
    this.state.setBlockedGenres(updated);
  }

  setTheme(theme: 'light' | 'dark'): void {
    this.state.setTheme(theme);
  }

  openOnboardingModal(): void {
    this.state.setModal('onboarding');
  }

  cancelSubscription(): void {
    this.state.cancelSubscription();
  }

  openDeleteModal(): void {
    this.state.setModal('delete');
  }

  logout(): void {
    this.state.logout();
  }

  // --- Password Management ---

  onCurrentPasswordInput(event: Event): void {
    this.currentPassword.set((event.target as HTMLInputElement).value);
  }

  onNewPasswordInput(event: Event): void {
    this.newPassword.set((event.target as HTMLInputElement).value);
  }

  updatePassword(): void {
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
        const message =
          (err as { error?: { detail?: string } })?.error?.detail ??
          (err instanceof Error ? err.message : 'Erro ao atualizar senha.');
        this.passwordError.set(message);
      },
    });
  }

  openAdminConsole(): void {
    this.router?.navigate(['/admin']).catch(() => {});
  }
}
