import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { CommunityReview, Song } from '@ribbit/shared-types';
import { toApiError } from '../../core/api-error';
import { AudioPlayerService } from '../../core/audio-player.service';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/services/song.service';
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
  protected readonly player = inject(AudioPlayerService);
  private readonly songService = inject(SongService);
  private readonly router = inject(Router, { optional: true });

  readonly selectedTab = signal<'like' | 'love' | 'reject'>('like');
  readonly playingSongKey = signal<string | null>(null);
  protected readonly starScale: readonly number[] = [1, 2, 3, 4, 5];

  readonly userInitials = computed<string>(() => {
    const parts = this.state
      .userName()
      .trim()
      .split(/\s+/)
      .filter((part) => part.length > 0);
    if (parts.length >= 2) {
      return `${parts[0]![0] ?? ''}${parts[1]![0] ?? ''}`.toUpperCase();
    }
    return this.state.userName().slice(0, 2).toUpperCase() || 'RB';
  });

  readonly likeCount = computed<number>(() => this.state.likedSongs().length);
  readonly loveCount = computed<number>(() => this.state.lovedSongs().length);
  readonly rejectCount = computed<number>(() => this.state.rejectedSongs().length);

  readonly activeTabLabel = computed<string>(() => {
    const tab = this.selectedTab();
    return tab === 'like' ? 'Curtidas' : tab === 'love' ? 'Amadas' : 'Rejeitadas';
  });

  readonly activeTabItems = computed<readonly Song[]>(() => {
    const tab = this.selectedTab();
    if (tab === 'like') {
      return this.state.likedSongs().slice(0, 6);
    }
    if (tab === 'love') {
      return this.state.lovedSongs().slice(0, 6);
    }
    return this.state.rejectedSongs().slice(0, 6);
  });

  readonly userReviews = computed<readonly CommunityReview[]>(() => {
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
    this.songService
      .loadUserReviews({
        currentUserId: this.state.userId() ?? undefined,
        currentUserName: this.state.userName(),
      })
      .subscribe({ error: () => undefined });
  }

  selectTab(tab: 'like' | 'love' | 'reject'): void {
    this.selectedTab.set(tab);
  }

  goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']).catch(() => false);
  }

  goToDashboard(): void {
    this.state.setPage('dashboard');
    void this.router?.navigate(['/dashboard']).catch(() => false);
  }

  goToSettings(): void {
    this.state.setPage('settings');
    void this.router?.navigate(['/settings']).catch(() => false);
  }

  goToFamily(): void {
    this.state.setPage('family');
    void this.router?.navigate(['/family']).catch(() => false);
  }

  openTutorial(): void {
    this.state.setModal('onboarding');
  }

  viewFullCollection(): void {
    const tab = this.selectedTab();
    const route = tab === 'like' ? 'likes' : tab === 'love' ? 'loved' : 'rejected';
    this.state.setPage(route);
    void this.router?.navigate([`/${route}`]).catch(() => false);
  }

  isSongPlaying(song: Song): boolean {
    return this.player.isPlaying() && this.playingSongKey() === `${song.title}::${song.artist}`;
  }

  playSong(song: Song): void {
    const key = `${song.title}::${song.artist}`;
    if (this.player.isPlaying() && this.playingSongKey() === key) {
      this.player.pause();
      return;
    }
    this.playingSongKey.set(key);
    this.state.discoverySong.set(song);
    this.player.loadTrack(song.previewUrl);
    this.player.play();
  }

  deleteReview(review: CommunityReview): void {
    if (!readAuthToken()) return;
    this.songService.deleteReview(review.id).subscribe({
      next: () => {
        this.state.refreshCatalogAndFeed();
        this.state.notify('Avaliação removida com sucesso.');
      },
      error: (err: unknown) => {
        this.state.notify(toApiError(err).message);
      },
    });
  }

  cancelSubscription(): void {
    this.state.cancelSubscription();
  }

  openDeleteModal(): void {
    this.state.setModal('delete');
  }

  logout(): void {
    this.state.logout();
  }
}
