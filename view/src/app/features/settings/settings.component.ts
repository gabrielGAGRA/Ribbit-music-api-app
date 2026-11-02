import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { IconComponent } from '../../shared/icon.component';

/** Manages user account display name, Spotify connection, blocked genres, and subscription status. */
@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  protected readonly state = inject(RibbitStateService);
  private readonly router = inject(Router, { optional: true });

  readonly isEditingName = signal<boolean>(false);
  readonly nameDraft = signal<string>(this.state.userName());
  readonly isSpotifyLinked = computed<boolean>(() => this.state.isSpotifyLinked());

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

  toggleSpotify(): void {
    this.state.toggleSpotifyLink();
  }

  goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']).catch(() => false);
  }

  openBlockedGenresModal(): void {
    this.state.setModal('filters');
  }

  removeBlockedGenre(genre: string): void {
    const updated = this.state.blockedGenres().filter((g) => g !== genre);
    this.state.setBlockedGenres(updated);
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
}
