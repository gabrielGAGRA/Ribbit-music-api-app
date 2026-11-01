import {
  Component,
  ChangeDetectionStrategy,
  inject,
  computed,
} from '@angular/core';
import { Router } from '@angular/router';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { DashboardService } from '../../core/services/dashboard.service';
import { SongService } from '../../core/services/song.service';
import { safeInject } from '../../core/safe-inject';
import { IconComponent } from '../../shared/icon.component';
import { MetricItem, RankedArtist, RankedGenre } from '@ribbit/shared-types';
import { MOCK_METRICS, MOCK_FAVORITE_GENRES } from '../../core/mocks/dashboard.mock';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent {
  private readonly router: Router | null = safeInject(Router, null);
  protected readonly dashboardService: DashboardService = safeInject(DashboardService, new DashboardService());
  protected readonly songService: SongService = safeInject(SongService, new SongService());

  protected readonly metrics: readonly MetricItem[] = MOCK_METRICS;
  protected readonly favoriteGenres: readonly RankedGenre[] = MOCK_FAVORITE_GENRES;

  readonly userFirstName = computed<string>(() => {
    return this.state.userName().split(' ')[0];
  });

  readonly favoriteArtists = computed<readonly RankedArtist[]>(() => {
    const songs = this.state.songs();
    return [
      { song: songs[0], rank: '1', time: '4h 12min' },
      { song: songs[3], rank: '2', time: '3h 46min' },
      { song: songs[2], rank: '3', time: '2h 58min' },
    ];
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
  ) {}

  searchArtist(artist: string): void {
    this.state.setPage('explore');
    void this.router?.navigate(['/explore']);
  }
}
