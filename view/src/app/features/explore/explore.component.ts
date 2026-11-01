import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { Router } from '@angular/router';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/services/song.service';
import { safeInject } from '../../core/safe-inject';
import { IconComponent } from '../../shared/icon.component';
import { CommunityReview, Song } from '@ribbit/shared-types';

@Component({
  selector: 'app-explore',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './explore.component.html',
  styleUrl: './explore.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ExploreComponent {
  private readonly router: Router | null = safeInject(Router, null);
  protected readonly songService: SongService = safeInject(SongService, new SongService());

  readonly query = signal<string>('');
  readonly historyExpanded = signal<boolean>(false);
  readonly reviewSort = signal<string>('recent');
  readonly reviewLikes = signal<Record<number, boolean>>({});

  readonly filteredSongs = computed<readonly Song[]>(() => {
    const q = this.query().toLowerCase().trim();
    if (!q) return [];
    return this.state
      .songs()
      .filter((s) =>
        `${s.title} ${s.artist} ${s.genre} ${s.album}`.toLowerCase().includes(q),
      );
  });

  readonly recentSongs = computed<readonly Song[]>(() => {
    const reversed = [...this.state.songs()].reverse();
    return this.historyExpanded() ? reversed : reversed.slice(0, 3);
  });

  readonly sortedReviews = computed<readonly CommunityReview[]>(() => {
    const sort = this.reviewSort();
    const likes = this.reviewLikes();
    const reviews = this.songService.reviews();
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

  readonly displayedReviews = computed<readonly CommunityReview[]>(() => {
    return this.sortedReviews().slice(0, 3);
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
  ) {}

  onQueryInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.query.set(target.value);
  }

  clearQuery(): void {
    this.query.set('');
  }

  toggleHistory(): void {
    this.historyExpanded.update((v) => !v);
  }

  onSortChange(event: Event): void {
    const target = event.target as HTMLSelectElement;
    this.reviewSort.set(target.value);
  }

  toggleReviewLike(id: number): void {
    this.reviewLikes.update((cur) => ({
      ...cur,
      [id]: !cur[id],
    }));
  }

  selectSong(song: Song): void {
    const idx = this.state.songs().indexOf(song);
    if (idx >= 0) {
      this.state.currentIndex.set(idx);
      this.state.setPage('discover');
      void this.router?.navigate(['/discover']);
    }
  }

  openSongDetails(song: Song): void {
    const idx = this.state.songs().indexOf(song);
    if (idx >= 0) {
      this.state.currentIndex.set(idx);
      this.state.setModal('details');
    }
  }

  openSearchFilters(): void {
    this.state.setModal('search-filters');
  }
}
