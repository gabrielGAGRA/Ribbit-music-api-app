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
import { Subject, merge, of } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, switchMap } from 'rxjs/operators';
import type { AdminModerationReview, TrackApiDto } from '@ribbit/shared-types';
import { IconComponent } from '../../shared/icon.component';
import { AdminStateService } from './admin-state.service';

type ModerationTab = 'catalog' | 'blocked' | 'reviews';

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
  protected readonly isSearchingTracks = signal<boolean>(false);
  protected readonly isCompacting = signal<boolean>(false);
  protected readonly isSyncing = signal<boolean>(false);
  protected readonly catalogActionStatus = signal<string>('');
  protected readonly editingTrackId = signal<number | null>(null);
  protected readonly editGenreDraft = signal<string>('');

  private readonly immediateSearch$ = new Subject<string>();
  private readonly debouncedSearch$ = new Subject<string>();
  private statusTimer: ReturnType<typeof setTimeout> | null = null;
  private searchPipelineInitialized = false;

  protected readonly searchedActiveTracks = computed<readonly TrackApiDto[]>(() =>
    this.adminState.activeTracks(),
  );

  protected readonly blockedTracks = computed<readonly TrackApiDto[]>(() =>
    this.adminState.blockedTracks(),
  );

  protected readonly topReviews = computed<readonly AdminModerationReview[]>(() =>
    this.adminState.topModerationReviews(),
  );

  ngOnInit(): void {
    this.ensureSearchPipeline();
    if (this.adminState.hasHydrated() && this.adminState.lastCatalogQuery() !== '') {
      this.searchTracks('');
    }
  }

  ngOnDestroy(): void {
    if (this.statusTimer !== null) {
      clearTimeout(this.statusTimer);
      this.statusTimer = null;
    }
  }

  protected selectTab(tab: ModerationTab): void {
    this.moderationError.set('');
    this.activeTab.set(tab);
  }

  protected updateTrackQuery(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.trackQuery.set(target.value);
    this.ensureSearchPipeline();
    this.debouncedSearch$.next(target.value);
  }

  protected searchTracks(query = this.trackQuery()): void {
    this.trackQuery.set(query);
    this.ensureSearchPipeline();
    this.immediateSearch$.next(query);
  }

  protected formatDuration(durationSeconds: number): string {
    const mins = Math.floor(durationSeconds / 60);
    const secs = String(durationSeconds % 60).padStart(2, '0');
    return `${mins}:${secs}`;
  }

  protected toggleExplicit(track: TrackApiDto): void {
    this.moderationError.set('');
    this.adminState.setTrackExplicit(track.track_id, !track.explicit).subscribe({
      error: (error: unknown) => {
        this.moderationError.set(
          error instanceof Error ? error.message : 'Erro ao alterar classificação indicativa.',
        );
      },
    });
  }

  protected blockTrack(trackId: number): void {
    this.moderationError.set('');
    this.adminState.setTrackBlocked(trackId, true).subscribe({
      error: (error: unknown) => {
        this.moderationError.set(
          error instanceof Error ? error.message : 'Erro ao bloquear faixa.',
        );
      },
    });
  }

  protected restoreTrack(trackId: number): void {
    this.moderationError.set('');
    this.adminState.setTrackBlocked(trackId, false).subscribe({
      error: (error: unknown) => {
        this.moderationError.set(
          error instanceof Error ? error.message : 'Erro ao restaurar faixa.',
        );
      },
    });
  }

  protected removeReview(reviewId: number): void {
    this.moderationError.set('');
    this.adminState.deleteReview(reviewId).subscribe({
      error: (error: unknown) => {
        this.moderationError.set(
          error instanceof Error ? error.message : 'Erro ao remover avaliação.',
        );
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
      error: (err: unknown) => {
        this.isCompacting.set(false);
        this.catalogActionStatus.set('');
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
        this.setTransientCatalogStatus(res.message);
      },
      error: (err: unknown) => {
        this.isSyncing.set(false);
        this.catalogActionStatus.set('');
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

  private ensureSearchPipeline(): void {
    if (this.searchPipelineInitialized) return;
    this.searchPipelineInitialized = true;

    merge(
      this.immediateSearch$,
      this.debouncedSearch$.pipe(debounceTime(300), distinctUntilChanged()),
    )
      .pipe(
        switchMap((query) => {
          this.moderationError.set('');
          this.isSearchingTracks.set(true);
          return this.adminState.fetchCatalogTracksFromBackend(query).pipe(
            catchError((err: unknown) => {
              this.moderationError.set(
                err instanceof Error ? err.message : 'Erro ao pesquisar faixas no catálogo.',
              );
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => {
        this.isSearchingTracks.set(false);
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
