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
import type { AdminTrackItem, AdminTrackSortOption } from '../admin-state.service';
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
  protected readonly isCreatingTrack = signal<boolean>(false);
  protected readonly newTrackTitle = signal<string>('');
  protected readonly newTrackArtist = signal<string>('');
  protected readonly newTrackGenre = signal<string>('');
  protected readonly newTrackDuration = signal<string>('180');
  protected readonly newTrackAlbum = signal<string>('');
  protected readonly newTrackYear = signal<string>('');
  protected readonly newTrackExplicit = signal<boolean>(false);

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
  }

  protected updateTextSignal(targetSignal: { set: (value: string) => void }, event: Event): void {
    targetSignal.set(readInputValue(event));
  }

  protected toggleNewTrackExplicit(): void {
    this.newTrackExplicit.update((v) => !v);
  }

  private parseOptionalReleaseYear(): number | null | 'invalid' {
    const rawYear = this.newTrackYear().trim();
    if (!rawYear) return null;
    const parsed = Number(rawYear);
    return Number.isFinite(parsed) && parsed >= 1900 ? Math.round(parsed) : 'invalid';
  }

  private buildCreateTrackPayload(): ReturnType<AdminStateService['createTrack']> | null {
    const title = this.newTrackTitle().trim();
    const artist = this.newTrackArtist().trim();
    const genre = this.newTrackGenre().trim();
    const duration = Number(this.newTrackDuration().trim());
    if (!title || !artist || !genre) {
      this.moderationError.set('Preencha título, artista e gênero da faixa.');
      return null;
    }
    if (!Number.isFinite(duration) || duration <= 0) {
      this.moderationError.set('Informe uma duração válida em segundos (> 0).');
      return null;
    }
    const parsedYear = this.parseOptionalReleaseYear();
    if (parsedYear === 'invalid') {
      this.moderationError.set('Informe um ano de lançamento válido.');
      return null;
    }
    const album = this.newTrackAlbum().trim();
    return this.adminState.createTrack({
      title,
      artist,
      genre,
      duration_seconds: Math.round(duration),
      ...(album ? { album } : {}),
      ...(parsedYear !== null ? { release_year: parsedYear } : {}),
      explicit: this.newTrackExplicit(),
    });
  }

  private resetCreateTrackForm(): void {
    this.showCreateTrackForm.set(false);
    this.newTrackTitle.set('');
    this.newTrackArtist.set('');
    this.newTrackGenre.set('');
    this.newTrackDuration.set('180');
    this.newTrackAlbum.set('');
    this.newTrackYear.set('');
    this.newTrackExplicit.set(false);
  }

  protected submitCreateTrack(event: Event): void {
    event.preventDefault();
    const request$ = this.buildCreateTrackPayload();
    if (!request$) return;

    this.moderationError.set('');
    this.isCreatingTrack.set(true);
    request$.subscribe({
      next: () => {
        this.isCreatingTrack.set(false);
        this.resetCreateTrackForm();
      },
      error: (err: Error) => {
        this.isCreatingTrack.set(false);
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
