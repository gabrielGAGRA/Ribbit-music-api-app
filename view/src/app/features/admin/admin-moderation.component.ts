import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import type { AdminModerationReview, TrackApiDto } from '@ribbit/shared-types';
import { safeInject } from '../../core/safe-inject';
import { IconComponent } from '../../shared/icon.component';
import { AdminStateService } from './admin-state.service';

type ModerationTab = 'catalog' | 'blocked' | 'reviews';

/** Catalog block/explicit controls and top-liked review moderation screen. */
@Component({
  selector: 'app-admin-moderation',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './admin-moderation.component.html',
  styleUrl: './admin-moderation.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminModerationComponent {
  protected readonly adminState = safeInject(AdminStateService, new AdminStateService());

  protected readonly activeTab = signal<ModerationTab>('catalog');
  protected readonly trackQuery = signal<string>('');
  protected readonly moderationError = signal<string>('');
  protected readonly isCompacting = signal<boolean>(false);
  protected readonly isSyncing = signal<boolean>(false);
  protected readonly catalogActionStatus = signal<string>('');
  protected readonly editingTrackId = signal<number | null>(null);
  protected readonly editGenreDraft = signal<string>('');

  protected readonly searchedActiveTracks = computed<readonly TrackApiDto[]>(() =>
    this.adminState.searchCatalogTracks(this.trackQuery()),
  );

  protected readonly blockedTracks = computed<readonly TrackApiDto[]>(() =>
    this.adminState.blockedTracks(),
  );

  protected readonly topReviews = computed<readonly AdminModerationReview[]>(() =>
    this.adminState.topModerationReviews(),
  );

  protected selectTab(tab: ModerationTab): void {
    this.moderationError.set('');
    this.activeTab.set(tab);
  }

  protected updateTrackQuery(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.trackQuery.set(target.value);
    if (this.adminState.hasHttpClient()) {
      this.adminState.fetchCatalogTracksFromBackend(target.value).subscribe();
    }
  }

  protected formatDuration(durationSeconds: number): string {
    const mins = Math.floor(durationSeconds / 60);
    const secs = String(durationSeconds % 60).padStart(2, '0');
    return `${mins}:${secs}`;
  }

  protected toggleExplicit(track: TrackApiDto): void {
    this.moderationError.set('');
    try {
      this.adminState.setTrackExplicit(track.track_id, !track.explicit);
    } catch (error: unknown) {
      this.moderationError.set(
        error instanceof Error ? error.message : 'Erro ao alterar classificação indicativa.',
      );
    }
  }

  protected blockTrack(trackId: number): void {
    this.moderationError.set('');
    try {
      this.adminState.setTrackBlocked(trackId, true);
    } catch (error: unknown) {
      this.moderationError.set(error instanceof Error ? error.message : 'Erro ao bloquear faixa.');
    }
  }

  protected restoreTrack(trackId: number): void {
    this.moderationError.set('');
    try {
      this.adminState.setTrackBlocked(trackId, false);
    } catch (error: unknown) {
      this.moderationError.set(error instanceof Error ? error.message : 'Erro ao restaurar faixa.');
    }
  }

  protected removeReview(reviewId: number): void {
    this.moderationError.set('');
    try {
      this.adminState.deleteReview(reviewId);
    } catch (error: unknown) {
      this.moderationError.set(
        error instanceof Error ? error.message : 'Erro ao remover avaliação.',
      );
    }
  }

  protected compactCatalog(): void {
    this.moderationError.set('');
    this.isCompacting.set(true);
    this.catalogActionStatus.set('Compactando catálogo (Delta Tables)...');
    this.adminState.compactCatalog().subscribe({
      next: (res) => {
        this.isCompacting.set(false);
        this.catalogActionStatus.set(res.message);
        setTimeout(() => {
          this.catalogActionStatus.set('');
        }, 4000);
      },
      error: (err: unknown) => {
        this.isCompacting.set(false);
        this.moderationError.set(
          err instanceof Error ? err.message : 'Erro ao compactar catálogo.',
        );
      },
    });
  }

  protected syncCatalog(): void {
    this.moderationError.set('');
    this.isSyncing.set(true);
    this.catalogActionStatus.set('Sincronizando catálogo...');
    this.adminState.syncCatalog().subscribe({
      next: (res) => {
        this.isSyncing.set(false);
        this.catalogActionStatus.set(res.message);
        setTimeout(() => {
          this.catalogActionStatus.set('');
        }, 4000);
      },
      error: (err: unknown) => {
        this.isSyncing.set(false);
        this.moderationError.set(
          err instanceof Error ? err.message : 'Erro ao sincronizar catálogo.',
        );
      },
    });
  }

  protected startEditingGenre(track: TrackApiDto): void {
    this.editingTrackId.set(track.track_id);
    this.editGenreDraft.set(track.genre);
    this.moderationError.set('');
  }

  protected cancelEditingGenre(): void {
    this.editingTrackId.set(null);
    this.editGenreDraft.set('');
  }

  protected updateGenreDraft(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.editGenreDraft.set(target.value);
  }

  protected saveGenre(trackId: number): void {
    const newGenre = this.editGenreDraft().trim();
    if (!newGenre) {
      this.moderationError.set('O gênero não pode ficar vazio.');
      return;
    }
    this.moderationError.set('');
    this.adminState.updateTrackGenre(trackId, newGenre).subscribe({
      next: () => {
        this.editingTrackId.set(null);
        this.editGenreDraft.set('');
      },
      error: (err: unknown) => {
        this.moderationError.set(err instanceof Error ? err.message : 'Erro ao atualizar gênero.');
      },
    });
  }

  protected starArray(rating: number): readonly number[] {
    const count = Math.max(1, Math.min(5, Math.round(rating)));
    return Array.from({ length: count }, (_, idx) => idx);
  }
}
