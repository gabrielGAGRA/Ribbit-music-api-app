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

  protected starArray(rating: number): readonly number[] {
    const count = Math.max(1, Math.min(5, Math.round(rating)));
    return Array.from({ length: count }, (_, idx) => idx);
  }
}
