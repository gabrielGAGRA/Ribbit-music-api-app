import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { Router } from '@angular/router';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { safeInject } from '../../core/safe-inject';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  private readonly router: Router | null = safeInject(Router, null);

  readonly isEditingName = signal<boolean>(false);
  readonly nameDraft = signal<string>('');
  readonly isSpotifyLinked = signal<boolean>(true);

  readonly userInitials = computed<string>(() => {
    const parts = this.state.userName().trim().split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return this.state.userName().slice(0, 2).toUpperCase();
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
  ) {
    this.nameDraft.set(this.state.userName());
  }

  startEditingName(): void {
    this.nameDraft.set(this.state.userName());
    this.isEditingName.set(true);
  }

  saveName(): void {
    const trimmed = this.nameDraft().trim();
    if (trimmed) {
      this.state.setUserName(trimmed);
      this.state.notify(`Nome atualizado para "${trimmed}".`);
    }
    this.isEditingName.set(false);
  }

  cancelEditingName(): void {
    this.nameDraft.set(this.state.userName());
    this.isEditingName.set(false);
  }

  onNameInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.nameDraft.set(input.value);
  }

  toggleSpotify(): void {
    const next = !this.isSpotifyLinked();
    this.isSpotifyLinked.set(next);
    if (next) {
      this.state.notify('Conta do Spotify vinculada com sucesso.');
    } else {
      this.state.notify('Conta do Spotify desvinculada.');
    }
  }

  goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']);
  }

  openBlockedGenresModal(): void {
    this.state.setModal('filters');
  }

  removeBlockedGenre(genre: string): void {
    const updated = this.state.blockedGenres().filter((g) => g !== genre);
    this.state.setBlockedGenres(updated);
    this.state.notify(`Gênero "${genre}" desbloqueado.`);
  }

  cancelSubscription(): void {
    this.state.setPlan('Free');
    this.state.notify('Assinatura cancelada. Seu plano agora é o Free.');
  }

  openDeleteModal(): void {
    this.state.setModal('delete');
  }

  logout(): void {
    this.state.setAuthView('login');
    this.state.notify('Você saiu da sua conta.');
  }
}
