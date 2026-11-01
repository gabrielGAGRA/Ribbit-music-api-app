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
import { AudioPlayerService } from '../../core/audio-player.service';
import { IconComponent } from '../../shared/icon.component';
import { Song } from '@ribbit/shared-types';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileComponent {
  private readonly router: Router | null = safeInject(Router, null);
  protected readonly songService: SongService = safeInject(SongService, new SongService());

  readonly selectedTab = signal<'like' | 'love' | 'reject'>('like');

  readonly likeCount = computed<number>(() => {
    return 128 + this.state.history().filter((item) => item.kind !== 'reject').length;
  });

  readonly loveCount = computed<number>(() => {
    return 32 + this.state.history().filter((item) => item.kind === 'love').length;
  });

  readonly rejectCount = computed<number>(() => {
    return 18 + this.state.history().filter((item) => item.kind === 'reject').length;
  });

  readonly activeTabLabel = computed<string>(() => {
    const tab = this.selectedTab();
    return tab === 'like' ? 'Curtidas' : tab === 'love' ? 'Amadas' : 'Rejeitadas';
  });

  readonly activeTabItems = computed<readonly Song[]>(() => {
    const tab = this.selectedTab();
    const songs = this.state.songs();
    if (tab === 'like') {
      return [songs[0], songs[1], songs[2], songs[3]];
    }
    if (tab === 'love') {
      return [songs[3], songs[1], songs[4]];
    }
    return [songs[5], songs[4], songs[2]];
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
    protected readonly player: AudioPlayerService = inject(AudioPlayerService),
  ) {}

  selectTab(tab: 'like' | 'love' | 'reject'): void {
    this.selectedTab.set(tab);
  }

  goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']);
  }

  goToSettings(): void {
    this.state.setPage('settings');
    void this.router?.navigate(['/settings']);
  }

  openFilters(): void {
    this.state.setModal('filters');
  }

  viewFullCollection(): void {
    const tab = this.selectedTab();
    const route = tab === 'like' ? 'likes' : tab === 'love' ? 'loved' : 'rejected';
    this.state.setPage(route);
    void this.router?.navigate([`/${route}`]);
  }

  playSong(song: Song): void {
    const idx = this.state.songs().indexOf(song);
    if (idx >= 0) {
      this.state.currentIndex.set(idx);
      this.player.play();
    }
  }

  cancelSubscription(): void {
    this.state.setPlan('Free');
    this.state.notify('Assinatura cancelada. Seu plano agora é o Free.');
  }

  openDeleteModal(): void {
    this.state.setModal('delete');
  }

  logout(): void {
    this.state.setAuthView('login');
  }
}
