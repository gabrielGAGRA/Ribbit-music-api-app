import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type {
  DashboardViewData,
  InteractionSourcePoint,
  MetricItem,
  MonthlyActivityBar,
  RankedArtist,
  RankedGenre,
  ReleaseEraPoint,
} from '@ribbit/shared-types';
import { isPremiumRequiredError, toApiError } from '../../core/api-error';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { DashboardService } from './dashboard.service';
import { WidthPercentDirective } from '../../shared/width-percent.directive';
import { IconComponent } from '../../shared/icon.component';

/** Renders annual retrospective listening stats and graphs from /api/profile/stats, or a blocked screen when Free (403). */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [IconComponent, WidthPercentDirective],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent implements OnInit {
  private readonly state = inject(RibbitStateService);
  private readonly dashboardService = inject(DashboardService);
  private readonly router = inject(Router, { optional: true });

  protected readonly ringCircumference = Math.round(2 * Math.PI * 48 * 100) / 100;

  protected readonly selectedYear = signal<number | null>(null);
  protected readonly availableYears = signal<readonly number[]>([]);
  protected readonly totalInteractions = signal<number>(0);
  protected readonly positiveRatePercent = signal<number>(0);
  protected readonly totalLikes = signal<number>(0);
  protected readonly totalSuperlikes = signal<number>(0);
  protected readonly totalDislikes = signal<number>(0);
  protected readonly metrics = signal<readonly MetricItem[]>([]);
  protected readonly favoriteGenres = signal<readonly RankedGenre[]>([]);
  protected readonly favoriteArtists = signal<readonly RankedArtist[]>([]);
  protected readonly monthlyBars = signal<readonly MonthlyActivityBar[]>([]);
  protected readonly maxMonthlyTotal = signal<number>(0);
  protected readonly releaseEras = signal<readonly ReleaseEraPoint[]>([]);
  protected readonly sources = signal<readonly InteractionSourcePoint[]>([]);
  protected readonly isPremiumLocked = signal<boolean>(false);
  protected readonly isLoading = signal<boolean>(false);

  protected readonly ringDashOffset = computed<number>(
    () => this.ringCircumference * (1 - this.positiveRatePercent() / 100),
  );

  protected readonly userFirstName = computed<string>(
    () => this.state.userName().split(' ')[0] || 'Ouvinte',
  );

  ngOnInit(): void {
    this.loadStats(null);
  }

  protected selectYear(year: number | null): void {
    if (year === this.selectedYear() && !this.isLoading()) return;
    this.selectedYear.set(year);
    this.loadStats(year);
  }

  private loadStats(year: number | null): void {
    if (!readAuthToken()) {
      if (!this.state.hasPaidAccess()) {
        this.isPremiumLocked.set(true);
      }
      return;
    }

    this.isLoading.set(true);
    this.dashboardService.getDashboardData(this.state.songs(), year).subscribe({
      next: (data) => {
        this.isLoading.set(false);
        this.isPremiumLocked.set(false);
        this.applyDashboardData(data);
      },
      error: (err: unknown) => {
        this.isLoading.set(false);
        if (isPremiumRequiredError(err)) {
          this.isPremiumLocked.set(true);
          this.state.showRibbyAlert({
            title: 'Dashboard anual exclusivo',
            message:
              'Assine o plano Individual ou Família para desbloquear suas estatísticas anuais.',
            tone: 'plan',
            mood: 'wave',
          });
          return;
        }
        this.state.notify(toApiError(err).message);
      },
    });
  }

  private applyDashboardData(data: DashboardViewData): void {
    this.availableYears.set(data.availableYears);
    this.totalInteractions.set(data.totalInteractions);
    this.positiveRatePercent.set(data.positiveRatePercent);
    this.totalLikes.set(data.totalLikes);
    this.totalSuperlikes.set(data.totalSuperlikes);
    this.totalDislikes.set(data.totalDislikes);
    this.metrics.set(data.metrics);
    this.favoriteGenres.set(data.genres);
    this.favoriteArtists.set(data.artists);
    this.monthlyBars.set(data.monthlyBars);
    this.maxMonthlyTotal.set(data.maxMonthlyTotal);
    this.releaseEras.set(data.releaseEras);
    this.sources.set(data.sources);
  }

  protected goToPlans(): void {
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']).catch(() => false);
  }

  protected searchArtist(artist: string): void {
    this.state.searchQuery.set(artist);
    this.state.setPage('explore');
    void this.router?.navigate(['/explore']).catch(() => false);
  }
}
