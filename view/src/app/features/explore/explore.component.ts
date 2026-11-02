import type { OnInit } from '@angular/core';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';
import type { CommunityReview, Song } from '@ribbit/shared-types';
import { mapTrackDtoToSong } from '../../core/api-mappers';
import { readAuthToken } from '../../core/auth-token.storage';
import { MOCK_REVIEWS } from '../../core/mocks/reviews.mock';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/services/song.service';
import { IconComponent } from '../../shared/icon.component';

/** Provides catalog search, recent interacted tracks history, and community review feed. */
@Component({
  selector: 'app-explore',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './explore.component.html',
  styleUrl: './explore.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ExploreComponent implements OnInit {
  protected readonly state = inject(RibbitStateService);
  protected readonly songService = inject(SongService);
  private readonly router = inject(Router, { optional: true });

  readonly query = this.state.searchQuery;
  readonly historyExpanded = signal<boolean>(false);
  readonly reviewSort = signal<string>('recent');
  readonly reviewLikes = signal<Record<number, boolean>>({});
  private readonly serverSearchResults = signal<readonly Song[] | null>(null);
  private readonly recentHistoryApiSongs = signal<readonly Song[]>([]);

  readonly hasActiveSearch = computed<boolean>(() => {
    const q = this.query().trim();
    const genre = this.state.searchFilterGenre();
    const year = this.state.searchFilterYear();
    return q.length > 0 || genre !== 'Todos' || year !== undefined;
  });

  readonly filteredSongs = computed<readonly Song[]>(() => {
    if (!this.hasActiveSearch()) return [];
    const serverResults = this.serverSearchResults();
    if (serverResults !== null) {
      return serverResults;
    }
    const q = this.query().toLowerCase().trim();
    return this.state
      .songs()
      .filter((s) => `${s.title} ${s.artist} ${s.genre} ${s.album}`.toLowerCase().includes(q));
  });

  readonly recentSongs = computed<readonly Song[]>(() => {
    const fromApi = this.recentHistoryApiSongs();
    const source = fromApi.length > 0 ? fromApi : [...this.state.songs()].reverse();
    return this.historyExpanded() ? source : source.slice(0, 3);
  });

  readonly sortedReviews = computed<readonly CommunityReview[]>(() => {
    const sort = this.reviewSort();
    const likes = this.reviewLikes();
    const apiReviews = this.songService.reviews();
    const reviews = apiReviews.length > 0 || readAuthToken() ? apiReviews : MOCK_REVIEWS;

    return [...reviews].sort((a, b) => {
      if (sort === 'likes') {
        const aLikes = a.likes + (likes[a.id] ? 1 : 0);
        const bLikes = b.likes + (likes[b.id] ? 1 : 0);
        return bLikes - aLikes;
      }
      if (sort === 'oldest') {
        return a.date - b.date;
      }
      return b.date - a.date;
    });
  });

  readonly displayedReviews = computed<readonly CommunityReview[]>(() =>
    this.sortedReviews().slice(0, 6),
  );

  constructor() {
    effect(() => {
      const q = this.query().trim();
      const genre = this.state.searchFilterGenre();
      const year = this.state.searchFilterYear();

      if (!readAuthToken()) {
        this.serverSearchResults.set(null);
        return;
      }
      if (!q && genre === 'Todos' && year === undefined) {
        this.serverSearchResults.set(null);
        return;
      }

      this.songService
        .searchSongs({
          ...(q ? { query: q } : {}),
          ...(genre !== 'Todos' ? { genre } : {}),
          ...(year !== undefined ? { year } : {}),
          limit: 30,
        })
        .subscribe({
          next: (items) => {
            this.serverSearchResults.set(items);
          },
          error: () => {
            this.serverSearchResults.set(null);
          },
        });
    });
  }

  ngOnInit(): void {
    if (!readAuthToken()) return;

    this.songService.getRecentInteractedTracks(30).subscribe({
      next: (items) => {
        this.recentHistoryApiSongs.set(items.map((entry) => mapTrackDtoToSong(entry.track)));
      },
      error: () => {
        // Fallback to catalog order if endpoint fails
      },
    });

    if (this.songService.reviews().length === 0) {
      this.state.refreshCatalogAndFeed();
    }
  }

  onQueryInput(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  clearQuery(): void {
    this.query.set('');
    this.state.searchFilterGenre.set('Todos');
    this.state.searchFilterYear.set(undefined);
  }

  toggleHistory(): void {
    this.historyExpanded.update((v) => !v);
  }

  onSortChange(event: Event): void {
    this.reviewSort.set((event.target as HTMLSelectElement).value);
  }

  toggleReviewLike(id: number): void {
    const alreadyLiked = Boolean(this.reviewLikes()[id]);
    this.reviewLikes.update((cur) => ({
      ...cur,
      [id]: !alreadyLiked,
    }));

    if (!alreadyLiked && readAuthToken()) {
      this.songService.likeReview(id).subscribe({
        error: () => {
          // Keep optimistic UI state on transient error
        },
      });
    }
  }

  fallbackReviewSong(idx: number): Song {
    const list = this.state.songs();
    return list[idx % list.length] ?? list[0]!;
  }

  selectSong(song: Song): void {
    this.state.discoverySong.set(song);
    this.state.setPage('discover');
    void this.router?.navigate(['/discover']).catch(() => false);
  }

  openSongDetails(song: Song): void {
    this.state.openTrackDetailsModal(song);
  }

  openSearchFilters(): void {
    this.state.setModal('search-filters');
  }
}
