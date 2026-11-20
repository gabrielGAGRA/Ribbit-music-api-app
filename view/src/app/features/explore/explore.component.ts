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
import type { Subscription } from 'rxjs';
import type { CommunityReview, Song } from '@ribbit/shared-types';
import { toApiError } from '../../core/api-error';
import { mapTrackDtoToSong } from '../../core/api-mappers';
import { readAuthToken } from '../../core/auth-token.storage';
import { MOCK_REVIEWS } from '../../core/mocks/reviews.mock';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/services/song.service';
import type { ReviewSortOption } from '../../core/services/song.service';
import { IconComponent } from '../../shared/icon.component';

function compareByRating(a: CommunityReview, b: CommunityReview, asc: boolean): number {
  const diff = asc ? (a.rating ?? 0) - (b.rating ?? 0) : (b.rating ?? 0) - (a.rating ?? 0);
  return diff || b.likes - a.likes;
}

function compareReviews(
  a: CommunityReview,
  b: CommunityReview,
  sort: string,
  likes: Readonly<Record<number, boolean>>,
): number {
  if (sort === 'rating_desc' || sort === 'rating_asc') {
    return compareByRating(a, b, sort === 'rating_asc');
  }
  if (sort === 'likes') {
    const aLikes = a.likes + (likes[a.id] ? 1 : 0);
    const bLikes = b.likes + (likes[b.id] ? 1 : 0);
    return bLikes - aLikes;
  }
  return sort === 'oldest' ? a.date - b.date : b.date - a.date;
}

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
  readonly reviewSort = signal<string>('likes');
  readonly reviewLikes = signal<Record<number, boolean>>({});
  protected readonly starScale: readonly number[] = [1, 2, 3, 4, 5];
  private readonly serverSearchResults = signal<readonly Song[] | null>(null);
  private readonly recentHistoryApiSongs = signal<readonly Song[]>([]);
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private activeSearchSub: Subscription | null = null;

  readonly hasActiveSearch = computed<boolean>(() => {
    const q = this.query().trim();
    const genre = this.state.searchFilterGenre();
    const artist = this.state.searchFilterArtist().trim();
    const year = this.state.searchFilterYear();
    const startDate = this.state.searchFilterStartDate().trim();
    const endDate = this.state.searchFilterEndDate().trim();
    const minRating = this.state.searchFilterMinRating();
    const sortBy = this.state.searchSortBy();
    return (
      q.length > 0 ||
      genre !== 'Todos' ||
      artist.length > 0 ||
      year !== undefined ||
      startDate.length > 0 ||
      endDate.length > 0 ||
      minRating !== null ||
      sortBy !== 'default'
    );
  });

  readonly filteredSongs = computed<readonly Song[]>(() => {
    if (!this.hasActiveSearch()) return [];
    const serverResults = this.serverSearchResults();
    if (serverResults !== null) {
      return serverResults;
    }
    const minRating = this.state.searchFilterMinRating();
    const sortBy = this.state.searchSortBy();
    const filtered = this.state
      .songs()
      .filter(
        (s) =>
          this.matchesLocalTextFilters(s) &&
          this.matchesLocalDateRange(s) &&
          (minRating === null || (s.averageRating ?? 0) >= minRating),
      );
    if (sortBy === 'rating_desc') {
      return [...filtered].sort((a, b) => (b.averageRating ?? -1) - (a.averageRating ?? -1));
    }
    if (sortBy === 'rating_asc') {
      return [...filtered].sort((a, b) => (a.averageRating ?? 6) - (b.averageRating ?? 6));
    }
    return filtered;
  });

  private matchesLocalTextFilters(song: Song): boolean {
    const query = this.query().toLowerCase().trim();
    if (
      query &&
      !`${song.title} ${song.artist} ${song.genre} ${song.album}`.toLowerCase().includes(query)
    ) {
      return false;
    }
    const genre = this.state.searchFilterGenre();
    if (genre !== 'Todos' && !song.genre.toLowerCase().includes(genre.toLowerCase())) {
      return false;
    }
    const artist = this.state.searchFilterArtist().toLowerCase().trim();
    return !artist || song.artist.toLowerCase().includes(artist);
  }

  private matchesLocalDateRange(song: Song): boolean {
    const startYear = this.parseDateYear(this.state.searchFilterStartDate());
    const endYear = this.parseDateYear(this.state.searchFilterEndDate());
    if (startYear === undefined && endYear === undefined) {
      return true;
    }
    const trackYear = Number(song.year);
    if (Number.isNaN(trackYear)) {
      return false;
    }
    if (startYear !== undefined && trackYear < startYear) {
      return false;
    }
    return endYear === undefined || trackYear <= endYear;
  }

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

    return [...reviews].sort((a, b) => compareReviews(a, b, sort, likes));
  });

  readonly displayedReviews = computed<readonly CommunityReview[]>(() =>
    this.sortedReviews().slice(0, 6),
  );

  constructor() {
    effect((onCleanup) => {
      this.query();
      this.state.searchFilterGenre();
      this.state.searchFilterArtist();
      this.state.searchFilterYear();
      this.state.searchFilterStartDate();
      this.state.searchFilterEndDate();
      this.state.searchFilterMinRating();
      this.state.searchSortBy();

      if (!readAuthToken() || !this.hasActiveSearch()) {
        this.serverSearchResults.set(null);
        return;
      }

      this.clearPendingSearch();
      this.debounceTimer = setTimeout(() => {
        this.runServerSearch();
      }, 500);

      onCleanup(() => {
        this.clearPendingSearch();
      });
    });
  }

  private clearPendingSearch(): void {
    if (this.debounceTimer !== null) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    if (this.activeSearchSub) {
      this.activeSearchSub.unsubscribe();
      this.activeSearchSub = null;
    }
  }

  private runServerSearch(): void {
    const q = this.query().trim();
    const genre = this.state.searchFilterGenre();
    const artist = this.state.searchFilterArtist().trim();
    const year = this.state.searchFilterYear();
    const startYear = this.parseDateYear(this.state.searchFilterStartDate());
    const endYear = this.parseDateYear(this.state.searchFilterEndDate());
    const minRating = this.state.searchFilterMinRating();
    const sortBy = this.state.searchSortBy();

    this.activeSearchSub = this.songService
      .searchSongs({
        ...(q ? { query: q } : {}),
        ...(genre !== 'Todos' ? { genre } : {}),
        ...(artist ? { artist } : {}),
        ...(year !== undefined ? { year } : {}),
        ...(startYear !== undefined ? { startYear } : {}),
        ...(endYear !== undefined ? { endYear } : {}),
        ...(minRating !== null ? { minRating } : {}),
        ...(sortBy !== 'default' ? { sortBy } : {}),
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
  }

  onSearchSubmit(event: Event): void {
    event.preventDefault();
    this.triggerSearch();
  }

  triggerSearch(): void {
    this.clearPendingSearch();
    if (!this.hasActiveSearch()) {
      this.serverSearchResults.set(null);
      return;
    }
    if (readAuthToken()) {
      this.runServerSearch();
    }
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

  private parseDateYear(dateValue: string): number | undefined {
    const trimmed = dateValue.trim();
    if (!trimmed) return undefined;
    const parsed = Number(trimmed.split('-')[0]);
    return Number.isFinite(parsed) && parsed >= 1900 ? parsed : undefined;
  }

  clearQuery(): void {
    this.state.clearSearchFilters();
  }

  clearMinRatingFilter(): void {
    this.state.searchFilterMinRating.set(null);
  }

  onSearchSortChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value as
      | 'default'
      | 'rating_desc'
      | 'rating_asc';
    this.state.searchSortBy.set(value);
  }

  toggleHistory(): void {
    this.historyExpanded.update((v) => !v);
  }

  onSortChange(event: Event): void {
    const sort = (event.target as HTMLSelectElement).value as ReviewSortOption;
    this.reviewSort.set(sort);
    if (readAuthToken()) {
      this.state.loadCommunityFeed(sort);
    }
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

  likeAndSaveTrack(song: Song): void {
    if (song.trackId === undefined) return;
    this.songService.likeAndSaveSearchTrack(song.trackId).subscribe({
      next: () => {
        this.state.refreshInteractedCollections();
        this.state.notify(`"${song.title}" adicionada às suas curtidas!`);
      },
      error: (err: unknown) => {
        this.state.notify(toApiError(err).message);
      },
    });
  }

  openSongDetails(song: Song): void {
    this.state.openTrackDetailsModal(song);
  }

  openSearchFilters(): void {
    this.state.setModal('search-filters');
  }
}
