import type { OnDestroy, OnInit } from '@angular/core';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import type { Subscription } from 'rxjs';
import { readInputValue, readSelectValue } from '@shared/dom-event-values';
import { IconComponent } from '@shared/icon.component';
import type { AdminModerationReview } from '../admin-mappers';
import type {
  AdminTrackItem,
  AdminTrackSortOption,
  ExternalTrackCandidate,
} from '../admin-state.service';
import { AdminStateService } from '../admin-state.service';

type ModerationTab = 'catalog' | 'blocked' | 'reviews';

function toAdminTrackSortOption(value: string): AdminTrackSortOption {
  if (
    value === 'dislikes_desc' ||
    value === 'likes_desc' ||
    value === 'superlikes_desc' ||
    value === 'recent'
  ) {
    return value;
  }
  return 'id_asc';
}

function buildCandidateCreatePayload(candidate: ExternalTrackCandidate) {
  return {
    title: candidate.title,
    artist: candidate.artist,
    genre: candidate.genre || 'Unknown',
    duration_seconds: Math.max(1, candidate.durationSeconds || 180),
    ...(candidate.album ? { album: candidate.album } : {}),
    ...(candidate.country ? { country: candidate.country } : {}),
    ...(candidate.releaseYear !== null ? { release_year: candidate.releaseYear } : {}),
    ...(candidate.coverUrl ? { cover_url: candidate.coverUrl } : {}),
    ...(candidate.itunesPreviewUrl ? { itunes_preview_url: candidate.itunesPreviewUrl } : {}),
    ...(candidate.spotifyId ? { spotify_id: candidate.spotifyId } : {}),
    explicit: candidate.explicit,
  };
}

/** Catalog block/explicit/genre controls, Delta sync/compaction, and review moderation screen. */
@Component({
  selector: 'app-admin-moderation',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './admin-moderation.component.html',
  styleUrl: './admin-moderation.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminModerationComponent implements OnInit, OnDestroy {
  protected readonly adminState = inject(AdminStateService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly activeTab = signal<ModerationTab>('catalog');
  protected readonly trackQuery = signal<string>('');
  protected readonly moderationError = signal<string>('');
  private readonly isSearchingTracks = signal<boolean>(false);
  protected readonly isCompacting = signal<boolean>(false);
  protected readonly isSyncing = signal<boolean>(false);
  protected readonly catalogActionStatus = signal<string>('');
  protected readonly editingTrackId = signal<number | null>(null);
  protected readonly editGenreDraft = signal<string>('');
  protected readonly catalogSort = signal<AdminTrackSortOption>('id_asc');
  protected readonly onlyDisliked = signal<boolean>(false);
  protected readonly showCreateTrackForm = signal<boolean>(false);
  protected readonly isSearchingExternal = signal<boolean>(false);
  protected readonly hasSearchedExternal = signal<boolean>(false);
  protected readonly addingCandidateKey = signal<string | null>(null);
  protected readonly newTrackTitle = signal<string>('');
  protected readonly newTrackArtist = signal<string>('');
  protected readonly externalCandidates = signal<readonly ExternalTrackCandidate[]>([]);

  private statusTimer: ReturnType<typeof setTimeout> | null = null;
  private searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  private activeSearchSubscription: Subscription | null = null;
  private lastDebouncedQuery = '';

  protected readonly searchedActiveTracks = computed<readonly AdminTrackItem[]>(() =>
    this.adminState.activeTracks(),
  );

  protected readonly blockedTracks = computed<readonly AdminTrackItem[]>(() =>
    this.adminState.blockedTracks(),
  );

  protected readonly topReviews = computed<readonly AdminModerationReview[]>(() =>
    this.adminState.topModerationReviews(),
  );

  ngOnInit(): void {
    if (this.adminState.hasHydrated() && this.adminState.lastCatalogQuery() !== '') {
      this.searchTracks('');
    }
  }

  ngOnDestroy(): void {
    if (this.statusTimer !== null) {
      clearTimeout(this.statusTimer);
      this.statusTimer = null;
    }
    if (this.searchDebounceTimer !== null) {
      clearTimeout(this.searchDebounceTimer);
      this.searchDebounceTimer = null;
    }
    this.activeSearchSubscription?.unsubscribe();
    this.activeSearchSubscription = null;
  }

  protected selectTab(tab: ModerationTab): void {
    this.moderationError.set('');
    this.activeTab.set(tab);
  }

  protected updateTrackQuery(event: Event): void {
    const query = readInputValue(event);
    this.trackQuery.set(query);
    if (query === this.lastDebouncedQuery) return;
    if (this.searchDebounceTimer !== null) {
      clearTimeout(this.searchDebounceTimer);
    }
    this.searchDebounceTimer = setTimeout(() => {
      this.searchDebounceTimer = null;
      this.lastDebouncedQuery = query;
      this.executeCatalogSearch(query);
    }, 300);
  }

  protected searchTracks(query = this.trackQuery()): void {
    this.trackQuery.set(query);
    this.lastDebouncedQuery = query;
    if (this.searchDebounceTimer !== null) {
      clearTimeout(this.searchDebounceTimer);
      this.searchDebounceTimer = null;
    }
    this.executeCatalogSearch(query);
  }

  protected formatDuration(durationSeconds: number): string {
    const mins = Math.floor(durationSeconds / 60);
    const secs = String(durationSeconds % 60).padStart(2, '0');
    return `${mins}:${secs}`;
  }

  protected toggleExplicit(track: AdminTrackItem): void {
    this.moderationError.set('');
    this.adminState.setTrackExplicit(track.trackId, !track.explicit).subscribe({
      error: (error: Error) => {
        this.moderationError.set(error.message);
      },
    });
  }

  protected blockTrack(trackId: number): void {
    this.moderationError.set('');
    this.adminState.setTrackBlocked(trackId, true).subscribe({
      error: (error: Error) => {
        this.moderationError.set(error.message);
      },
    });
  }

  protected restoreTrack(trackId: number): void {
    this.moderationError.set('');
    this.adminState.setTrackBlocked(trackId, false).subscribe({
      error: (error: Error) => {
        this.moderationError.set(error.message);
      },
    });
  }

  protected removeReview(reviewId: number): void {
    this.moderationError.set('');
    this.adminState.deleteReview(reviewId).subscribe({
      error: (error: Error) => {
        this.moderationError.set(error.message);
      },
    });
  }

  protected compactCatalog(): void {
    this.moderationError.set('');
    this.isCompacting.set(true);
    this.catalogActionStatus.set('Compactando catálogo (Delta Tables)...');
    this.adminState.compactCatalog().subscribe({
      next: (res) => {
        this.isCompacting.set(false);
        this.setTransientCatalogStatus(res.message);
      },
      error: (err: Error) => {
        this.isCompacting.set(false);
        this.catalogActionStatus.set('');
        this.moderationError.set(err.message);
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
        this.setTransientCatalogStatus(res.message);
      },
      error: (err: Error) => {
        this.isSyncing.set(false);
        this.catalogActionStatus.set('');
        this.moderationError.set(err.message);
      },
    });
  }

  protected startEditingGenre(track: AdminTrackItem): void {
    this.editingTrackId.set(track.trackId);
    this.editGenreDraft.set(track.genre);
    this.moderationError.set('');
  }

  protected cancelEditingGenre(): void {
    this.editingTrackId.set(null);
    this.editGenreDraft.set('');
  }

  protected updateGenreDraft(event: Event): void {
    this.editGenreDraft.set(readInputValue(event));
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
      error: (err: Error) => {
        this.moderationError.set(err.message);
      },
    });
  }

  protected updateCatalogSort(event: Event): void {
    const sortBy = toAdminTrackSortOption(readSelectValue(event));
    this.catalogSort.set(sortBy);
    this.searchTracks(this.trackQuery());
  }

  protected toggleOnlyDisliked(): void {
    this.onlyDisliked.update((v) => !v);
    this.searchTracks(this.trackQuery());
  }

  protected toggleCreateTrackForm(): void {
    this.moderationError.set('');
    this.showCreateTrackForm.update((v) => !v);
    if (!this.showCreateTrackForm()) {
      this.newTrackTitle.set('');
      this.newTrackArtist.set('');
      this.externalCandidates.set([]);
      this.hasSearchedExternal.set(false);
    }
  }

  protected updateTextSignal(targetSignal: { set: (value: string) => void }, event: Event): void {
    targetSignal.set(readInputValue(event));
  }

  protected candidateKey(candidate: ExternalTrackCandidate): string {
    return (
      candidate.spotifyId ?? `${candidate.title.toLowerCase()}::${candidate.artist.toLowerCase()}`
    );
  }

  protected searchExternalTracks(event: Event): void {
    event.preventDefault();
    const title = this.newTrackTitle().trim();
    const artist = this.newTrackArtist().trim();
    if (!title && !artist) {
      this.moderationError.set('Informe o título ou o artista para buscar a faixa.');
      return;
    }
    this.moderationError.set('');
    this.isSearchingExternal.set(true);
    this.hasSearchedExternal.set(false);
    this.adminState.searchExternalTracks(title, artist).subscribe({
      next: (items) => {
        this.isSearchingExternal.set(false);
        this.hasSearchedExternal.set(true);
        this.externalCandidates.set(items);
      },
      error: (err: Error) => {
        this.isSearchingExternal.set(false);
        this.moderationError.set(err.message);
      },
    });
  }

  protected addCandidateToDelta(candidate: ExternalTrackCandidate): void {
    if (candidate.alreadyInCatalog || this.addingCandidateKey() !== null) return;
    const key = this.candidateKey(candidate);
    this.moderationError.set('');
    this.addingCandidateKey.set(key);
    this.adminState
      .createTrack(buildCandidateCreatePayload(candidate))
      .subscribe({
        next: () => {
          this.addingCandidateKey.set(null);
          this.externalCandidates.update((list) =>
            list.map((item) =>
              this.candidateKey(item) === key ? { ...item, alreadyInCatalog: true } : item,
            ),
          );
          this.setTransientCatalogStatus(
            `Faixa "${candidate.title}" adicionada ao catálogo e à Delta Table.`,
          );
        },
        error: (err: Error) => {
          this.addingCandidateKey.set(null);
          this.moderationError.set(err.message);
        },
      });
  }

  protected starArray(rating: number): readonly number[] {
    const count = Math.max(1, Math.min(5, Math.round(rating)));
    return Array.from({ length: count }, (_, idx) => idx);
  }

  private executeCatalogSearch(query: string): void {
    this.activeSearchSubscription?.unsubscribe();
    this.moderationError.set('');
    this.isSearchingTracks.set(true);
    this.activeSearchSubscription = this.adminState
      .loadAdminCatalog({
        query,
        sortBy: this.catalogSort(),
        minDislikes: this.onlyDisliked() ? 1 : null,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.isSearchingTracks.set(false);
        },
        error: (err: Error) => {
          this.moderationError.set(err.message);
          this.isSearchingTracks.set(false);
        },
      });
  }

  private setTransientCatalogStatus(message: string): void {
    this.catalogActionStatus.set(message);
    if (this.statusTimer !== null) {
      clearTimeout(this.statusTimer);
    }
    this.statusTimer = setTimeout(() => {
      this.catalogActionStatus.set('');
      this.statusTimer = null;
    }, 4000);
  }
}
