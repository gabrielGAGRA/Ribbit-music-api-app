import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { MetricItem, RankedArtist, RankedGenre } from '@ribbit/shared-types';
import { isPremiumRequiredError, toApiError } from '../../core/api-error';
import { readAuthToken } from '../../core/auth-token.storage';
import { MOCK_FAVORITE_GENRES, MOCK_METRICS } from '../../core/mocks/dashboard.mock';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { DashboardService } from '../../core/services/dashboard.service';
import { WidthPercentDirective } from '../../shared/dynamic-style.directive';
import { IconComponent } from '../../shared/icon.component';

/** Renders annual retrospective listening stats from /api/profile/stats, or an upgrade CTA when Free (403). */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [IconComponent, WidthPercentDirective],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent implements OnInit {
  protected readonly state = inject(RibbitStateService);
  private readonly dashboardService = inject(DashboardService);
  private readonly router = inject(Router, { optional: true });

  readonly hoursLabel = signal<string>('0h');
  readonly metrics = signal<readonly MetricItem[]>(MOCK_METRICS);
  readonly favoriteGenres = signal<readonly RankedGenre[]>(MOCK_FAVORITE_GENRES);
  readonly loadedArtists = signal<readonly RankedArtist[] | null>(null);
  readonly isPremiumLocked = signal<boolean>(false);

  readonly userFirstName = computed<string>(() => this.state.userName().split(' ')[0] || 'Ouvinte');

  readonly favoriteArtists = computed<readonly RankedArtist[]>(() => {
    const apiArtists = this.loadedArtists();
    if (apiArtists !== null) {
      return apiArtists;
    }
    const songs = this.state.songs();
    return songs.slice(0, 3).map((song, idx) => ({
      song,
      rank: String(idx + 1),
      time: `${3 - idx}h ${45 - idx * 12}min`,
    }));
  });

  ngOnInit(): void {
    if (!readAuthToken()) return;

    this.dashboardService.getDashboardData(this.state.songs()).subscribe({
      next: (data) => {
        this.isPremiumLocked.set(false);
        this.hoursLabel.set(data.hoursLabel);
        this.metrics.set(data.metrics);
        this.favoriteGenres.set(data.genres);
        this.loadedArtists.set(data.artists);
      },
      error: (err: unknown) => {
        if (isPremiumRequiredError(err)) {
          this.isPremiumLocked.set(true);
          return;
        }
        this.state.notify(toApiError(err).message);
      },
    });
  }

  goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']).catch(() => false);
  }

  searchArtist(artist: string): void {
    this.state.searchQuery.set(artist);
    this.state.setPage('explore');
    void this.router?.navigate(['/explore']).catch(() => false);
  }
}
