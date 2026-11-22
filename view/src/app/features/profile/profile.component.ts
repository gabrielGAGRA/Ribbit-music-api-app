import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { CommunityReview, Song } from '@ribbit/shared-types';
import { toApiError } from '../../core/api-error';
import { computeInitials } from '../../core/api-mappers';
import { AudioPlayerService } from '../../core/audio-player.service';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/song.service';
import { IconComponent } from '../../shared/icon.component';

/** Displays user account overview, categorized track collections, user reviews, and subscription shortcuts. */
@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileComponent implements OnInit {
  protected readonly state = inject(RibbitStateService);
  private readonly player = inject(AudioPlayerService);
  private readonly songService = inject(SongService);
  private readonly router = inject(Router, { optional: true });

  protected readonly selectedTab = signal<'like' | 'love' | 'reject' | 'history'>('like');
  protected readonly historyExpanded = signal<boolean>(false);
  private readonly playingSongKey = signal<string | null>(null);
  protected readonly starScale: readonly number[] = [1, 2, 3, 4, 5];

  protected readonly userInitials = computed<string>(() => computeInitials(this.state.userName()));

  protected readonly likeCount = computed<number>(() => this.state.likedSongs().length);
  protected readonly loveCount = computed<number>(() => this.state.lovedSongs().length);
  protected readonly rejectCount = computed<number>(() => this.state.rejectedSongs().length);

  protected readonly historySongs = computed<readonly Song[]>(() => {
    const accessEntries = this.state.accessHistory();
    const seen = new Set<number>();
    const items: Song[] = [];
    for (const entry of accessEntries) {
      if (seen.has(entry.track_id)) continue;
      seen.add(entry.track_id);
      items.push({
        trackId: entry.track_id,
        title: entry.track_title,
        artist: entry.track_artist,
        genre: entry.track_genre,
        album: entry.track_album ?? entry.track_title,
        durationSeconds: entry.track_duration_seconds,
        time: `${Math.floor(entry.track_duration_seconds / 60)}:${String(entry.track_duration_seconds % 60).padStart(2, '0')}`,
        image: entry.track_cover_url ?? '',
        year: '',
        match: 0,
        ...(entry.track_preview_url ? { previewUrl: entry.track_preview_url } : {}),
        explicit: entry.track_explicit,
      });
    }
    return items;
  });

  protected readonly historyCount = computed<number>(() => this.historySongs().length);

  private readonly displayedHistorySongs = computed<readonly Song[]>(() =>
    this.historyExpanded() ? this.historySongs() : this.historySongs().slice(0, 6),
  );

  protected readonly activeTabLabel = computed<string>(() => {
    const tab = this.selectedTab();
    if (tab === 'like') return 'Curtidas';
    if (tab === 'love') return 'Amadas';
    if (tab === 'reject') return 'Rejeitadas';
    return 'Histórico de acessos';
  });

  protected readonly activeTabItems = computed<readonly Song[]>(() => {
    const tab = this.selectedTab();
    if (tab === 'like') {
      return this.state.likedSongs().slice(0, 6);
    }
    if (tab === 'love') {
      return this.state.lovedSongs().slice(0, 6);
    }
    if (tab === 'history') {
      return this.displayedHistorySongs();
    }
    return this.state.rejectedSongs().slice(0, 6);
  });

  protected readonly userReviews = computed<readonly CommunityReview[]>(() => {
    const myReviews = this.songService.userReviews();
    if (myReviews.length > 0) {
      return myReviews;
    }
    const uid = this.state.userId();
    const userName = this.state.userName().trim().toLowerCase();
    return this.songService.reviews().filter((review) => {
      if (uid !== null && review.userId !== undefined) {
        return review.userId === uid;
      }
      return Boolean(userName) && review.author.trim().toLowerCase() === userName;
    });
  });

  ngOnInit(): void {
    if (!readAuthToken()) return;
    if (this.songService.reviews().length === 0) {
      this.state.refreshCatalogAndFeed();
    }
    this.state.refreshAccessHistory();
    this.songService
      .loadUserReviews({
        currentUserId: this.state.userId() ?? undefined,
        currentUserName: this.state.userName(),
      })
      .subscribe({ error: () => undefined });
  }

  protected selectTab(tab: 'like' | 'love' | 'reject' | 'history'): void {
    this.selectedTab.set(tab);
  }

  protected toggleHistory(): void {
    this.historyExpanded.update((v) => !v);
  }

  protected openSongDetails(song: Song): void {
    this.state.openTrackDetailsModal(song);
  }

  protected goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']).catch(() => false);
  }

  protected goToDashboard(): void {
    this.state.setPage('dashboard');
    void this.router?.navigate(['/dashboard']).catch(() => false);
  }

  protected goToSettings(): void {
    this.state.setPage('settings');
    void this.router?.navigate(['/settings']).catch(() => false);
  }

  protected goToFamily(): void {
    this.state.setPage('family');
    void this.router?.navigate(['/family']).catch(() => false);
  }

  protected openTutorial(): void {
    this.state.setModal('onboarding');
  }

  protected viewFullCollection(): void {
    const tab = this.selectedTab();
    const route = tab === 'like' ? 'likes' : tab === 'love' ? 'loved' : 'rejected';
    this.state.setPage(route);
    void this.router?.navigate([`/${route}`]).catch(() => false);
  }

  protected isSongPlaying(song: Song): boolean {
    return this.player.isPlaying() && this.playingSongKey() === `${song.title}::${song.artist}`;
  }

  protected playSong(song: Song): void {
    const key = `${song.title}::${song.artist}`;
    if (this.player.isPlaying() && this.playingSongKey() === key) {
      this.player.pause();
      return;
    }
    this.playingSongKey.set(key);
    this.state.discoverySong.set(song);
    this.state.recordTrackAccess(song, 'profile');
    this.player.loadTrack(song.previewUrl);
    this.player.play();
  }

  protected deleteReview(review: CommunityReview): void {
    if (!readAuthToken()) return;
    this.songService.deleteReview(review.id).subscribe({
      next: () => {
        this.songService
          .loadUserReviews({
            currentUserId: this.state.userId() ?? undefined,
            currentUserName: this.state.userName(),
          })
          .subscribe();
        this.state.refreshCatalogAndFeed();
        this.state.notify('Avaliação removida com sucesso.');
      },
      error: (err: unknown) => {
        this.state.notify(toApiError(err).message);
      },
    });
  }

  protected cancelSubscription(): void {
    this.state.cancelSubscription();
  }

  protected openDeleteModal(): void {
    this.state.setModal('delete');
  }

  protected logout(): void {
    this.state.logout();
  }
}
