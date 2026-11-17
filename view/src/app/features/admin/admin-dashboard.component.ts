import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router } from '@angular/router';
import { WidthPercentDirective } from '../../shared/dynamic-style.directive';
import { IconComponent } from '../../shared/icon.component';
import { AdminStateService } from './admin-state.service';

const BRL_FORMATTER = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
});

/** Executive KPIs and audience report screen backing GET /api/admin/dashboard and GET /api/admin/audience. */
@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [IconComponent, WidthPercentDirective],
  templateUrl: './admin-dashboard.component.html',
  styleUrl: './admin-dashboard.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminDashboardComponent {
  protected readonly adminState = inject(AdminStateService);
  private readonly router = inject(Router, { optional: true });

  protected readonly formattedNetRevenue = computed<string>(() =>
    BRL_FORMATTER.format(this.adminState.executiveDashboard().estimated_net_revenue),
  );

  protected readonly adminCount = computed<number>(() => this.adminState.administrators().length);

  protected readonly blockedTrackCount = computed<number>(
    () => this.adminState.blockedTracks().length,
  );

  protected readonly catalogAvailabilityPercent = computed<number>(() => {
    const report = this.adminState.audienceReport();
    if (report.total_tracks === 0) return 0;
    return Math.round((report.active_tracks / report.total_tracks) * 100);
  });

  protected formatCurrency(amount: number): string {
    return BRL_FORMATTER.format(amount);
  }

  protected goToPlans(): void {
    if (this.router) {
      this.router.navigate(['/admin/plans']).catch(() => {});
    }
  }

  protected goToModeration(): void {
    if (this.router) {
      this.router.navigate(['/admin/moderation']).catch(() => {});
    }
  }

  protected goToUsers(): void {
    if (this.router) {
      this.router.navigate(['/admin/users']).catch(() => {});
    }
  }
}
