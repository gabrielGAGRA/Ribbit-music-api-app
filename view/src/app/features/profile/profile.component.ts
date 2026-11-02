import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { Song } from '@ribbit/shared-types';
import { AudioPlayerService } from '../../core/audio-player.service';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { IconComponent } from '../../shared/icon.component';

/** Displays user account overview, categorized track collections, and subscription shortcuts. */
@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileComponent {
  protected readonly state = inject(RibbitStateService);
  protected readonly player = inject(AudioPlayerService);
  private readonly router = inject(Router, { optional: true });

  readonly selectedTab = signal<'like' | 'love' | 'reject'>('like');

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

  viewFullCollection(): void {
    const tab = this.selectedTab();
    const route = tab === 'like' ? 'likes' : tab === 'love' ? 'loved' : 'rejected';
    this.state.setPage(route);
    void this.router?.navigate([`/${route}`]).catch(() => false);
  }

  playSong(song: Song): void {
    this.state.discoverySong.set(song);
    this.player.loadTrack(song.previewUrl);
    this.player.play();
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
