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
import { finalize } from 'rxjs/operators';
import type { CommunityReview, Song } from '@ribbit/shared-types';
import { toApiError } from '../../core/api-error';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { matchesGenreFilter } from '../../core/genre-catalog';
import { SongService } from '../../core/song.service';
import type { ReviewSortOption } from '../../core/song.service';
import { readInputValue, readSelectValue } from '../../shared/dom-event-values';
import { IconComponent } from '../../shared/icon.component';

function toSearchSortOption(value: string): 'default' | 'rating_desc' | 'rating_asc' {
  if (value === 'rating_desc' || value === 'rating_asc') {
    return value;
  }
  return 'default';
}

function toReviewSortOption(value: string): ReviewSortOption {
  if (value === 'rating_desc' || value === 'rating_asc' || value === 'recent') {
    return value;
  }
  return 'likes';
}

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
  private readonly songService = inject(SongService);
  private readonly router = inject(Router, { optional: true });

  readonly query = this.state.searchQuery;
  protected readonly historyExpanded = signal<boolean>(false);
  protected readonly isSearching = signal<boolean>(false);
  protected readonly reviewSort = signal<string>('likes');
  protected readonly reviewLikes = signal<Record<number, boolean>>({});
  protected readonly starScale: readonly number[] = [1, 2, 3, 4, 5];
  private readonly serverSearchResults = signal<readonly Song[] | null>(null);
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private activeSearchSub: Subscription | null = null;

  protected getVisibleRating(item: Song): string | null {
    const rating = item.averageRating;
    return (item.reviewCount ?? 0) > 0 && rating !== null && rating !== undefined
      ? rating.toFixed(1)
      : null;
  }

  protected readonly hasActiveSearch = computed<boolean>(() => {
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

  protected readonly filteredSongs = computed<readonly Song[]>(() => {
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
    if (genre !== 'Todos' && !matchesGenreFilter(song.genre, genre)) {
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

  private readonly sortedReviews = computed<readonly CommunityReview[]>(() => {
    const sort = this.reviewSort();
    const likes = this.reviewLikes();
    const reviews = this.songService.reviews();

    return [...reviews].sort((a, b) => compareReviews(a, b, sort, likes));
  });

  protected readonly displayedReviews = computed<readonly CommunityReview[]>(() =>
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
    this.isSearching.set(false);
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

    this.isSearching.set(true);
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
        includeDeleted: true,
        limit: 30,
      })
      .pipe(
        finalize(() => {
          this.isSearching.set(false);
        }),
      )
      .subscribe({
        next: (items) => {
          this.serverSearchResults.set(items);
        },
        error: () => {
          this.serverSearchResults.set(null);
        },
      });
  }

  protected submitSearch(event: Event): void {
    event.preventDefault();
    this.triggerSearch();
  }

  private triggerSearch(): void {
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

    if (this.songService.reviews().length === 0) {
      this.state.refreshCatalogAndFeed();
    }
  }

  protected hasTrackRating(song: Song): boolean {
    return (song.reviewCount ?? 0) > 0 && song.averageRating != null;
  }

  protected updateSearchQuery(event: Event): void {
    this.query.set(readInputValue(event));
  }

  private parseDateYear(dateValue: string): number | undefined {
    const trimmed = dateValue.trim();
    if (!trimmed) return undefined;
    const parsed = Number(trimmed.split('-')[0]);
    return Number.isFinite(parsed) && parsed >= 1900 ? parsed : undefined;
  }

  protected clearQuery(): void {
    this.state.clearSearchFilters();
  }

  protected clearMinRatingFilter(): void {
    this.state.searchFilterMinRating.set(null);
  }

  protected updateSearchSort(event: Event): void {
    this.state.searchSortBy.set(toSearchSortOption(readSelectValue(event)));
  }

  protected updateReviewSort(event: Event): void {
    const sort = toReviewSortOption(readSelectValue(event));
    this.reviewSort.set(sort);
    if (readAuthToken()) {
      this.state.loadCommunityFeed(sort);
    }
  }

  protected toggleReviewLike(id: number): void {
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

  protected fallbackReviewSong(idx: number): Song | undefined {
    const list = this.state.songs();
    if (list.length === 0) return undefined;
    return list[idx % list.length] ?? list[0];
  }

  protected selectSong(song: Song): void {
    if (song.isDeleted) {
      this.state.openUnavailableTrackModal(song);
      return;
    }
    if (this.state.isSongRestrictedForMinor(song)) {
      this.state.notifyMinorSongRestriction(song);
      return;
    }
    this.state.recordTrackAccess(song, 'search');
    this.state.openTrackForCommunitySwipe(song);
    void this.router?.navigate(['/discover']).catch(() => false);
  }

  protected likeAndSaveTrack(song: Song): void {
    if (song.isDeleted) {
      this.state.openUnavailableTrackModal(song);
      return;
    }
    if (this.state.isSongRestrictedForMinor(song)) {
      this.state.notifyMinorSongRestriction(song);
      return;
    }
    if (song.trackId === undefined) return;
    this.songService.likeAndSaveSearchTrack(song.trackId).subscribe({
      next: () => {
        this.state.refreshInteractedCollections();
        this.state.refreshAccessHistory();
        this.state.notify(`"${song.title}" adicionada às suas curtidas!`);
      },
      error: (err: unknown) => {
        const apiErr = toApiError(err);
        if (apiErr.rawMessage === 'Track is restricted for minor users.') {
          this.state.notifyMinorSongRestriction(song);
        }
        this.state.notify(apiErr.message);
      },
    });
  }

  protected openSongDetails(song: Song): void {
    if (song.isDeleted) {
      this.state.openUnavailableTrackModal(song);
      return;
    }
    if (this.state.isSongRestrictedForMinor(song)) {
      this.state.notifyMinorSongRestriction(song);
      return;
    }
    this.state.openTrackDetailsModal(song);
  }

  protected openSearchFilters(): void {
    this.state.setModal('search-filters');
  }
}
