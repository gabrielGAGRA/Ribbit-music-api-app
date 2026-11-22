import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { readInputValue } from '@shared/dom-event-values';
import { WidthPercentDirective } from '@shared/width-percent.directive';
import { IconComponent } from '@shared/icon.component';
import { AdminDomainError } from '../admin-domain-error';
import { AdminStateService } from '../admin-state.service';

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
    BRL_FORMATTER.format(this.adminState.executiveDashboard().estimatedNetRevenue),
  );

  protected readonly isNetNegative = computed<boolean>(
    () => this.adminState.executiveDashboard().estimatedNetRevenue < 0,
  );

  protected readonly grossRevenue = computed<number>(
    () => this.adminState.executiveDashboard().grossRevenue,
  );

  protected readonly contentCost = computed<number>(
    () => this.adminState.executiveDashboard().contentCost,
  );

  protected readonly infrastructureCost = computed<number>(
    () => this.adminState.executiveDashboard().infrastructureCost,
  );

  protected readonly totalCosts = computed<number>(
    () => this.adminState.executiveDashboard().totalCosts,
  );

  protected readonly totalAccesses = computed<number>(
    () => this.adminState.audienceReport().totalAccesses,
  );

  protected readonly editingCosts = signal<boolean>(false);
  protected readonly costPerTrackInput = signal<string>('');
  protected readonly infraFixedInput = signal<string>('');
  protected readonly infraPerUserInput = signal<string>('');
  protected readonly costFormError = signal<string>('');
  protected readonly isSavingCosts = signal<boolean>(false);

  protected readonly adminCount = computed<number>(() => this.adminState.administrators().length);

  protected readonly blockedTrackCount = computed<number>(
    () => this.adminState.blockedTracks().length,
  );

  protected readonly catalogAvailabilityPercent = computed<number>(() => {
    const report = this.adminState.audienceReport();
    if (report.totalTracks === 0) return 0;
    return Math.round((report.activeTracks / report.totalTracks) * 100);
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

  protected openCostEditor(): void {
    const dash = this.adminState.executiveDashboard();
    this.costPerTrackInput.set(String(dash.contentCostPerTrack));
    this.infraFixedInput.set(String(dash.infrastructureFixedCost));
    this.infraPerUserInput.set(String(dash.infrastructureCostPerUser));
    this.costFormError.set('');
    this.editingCosts.set(true);
  }

  protected cancelCostEditor(): void {
    this.editingCosts.set(false);
    this.costFormError.set('');
  }

  protected updateCostPerTrack(event: Event): void {
    this.costPerTrackInput.set(readInputValue(event));
  }

  protected updateInfraFixed(event: Event): void {
    this.infraFixedInput.set(readInputValue(event));
  }

  protected updateInfraPerUser(event: Event): void {
    this.infraPerUserInput.set(readInputValue(event));
  }

  protected savePlatformCosts(event: Event): void {
    event.preventDefault();
    if (this.isSavingCosts()) return;

    const perTrack = Number(this.costPerTrackInput());
    const infraFixed = Number(this.infraFixedInput());
    const infraUser = Number(this.infraPerUserInput());

    if (
      !Number.isFinite(perTrack) ||
      perTrack < 0 ||
      !Number.isFinite(infraFixed) ||
      infraFixed < 0 ||
      !Number.isFinite(infraUser) ||
      infraUser < 0
    ) {
      this.costFormError.set('Informe valores numéricos maiores ou iguais a zero.');
      return;
    }

    this.costFormError.set('');
    this.isSavingCosts.set(true);
    this.adminState
      .updatePlatformCosts({
        content_cost_per_track: perTrack,
        infrastructure_fixed_cost: infraFixed,
        infrastructure_cost_per_user: infraUser,
      })
      .subscribe({
        next: () => {
          this.isSavingCosts.set(false);
          this.editingCosts.set(false);
        },
        error: (err: unknown) => {
          this.isSavingCosts.set(false);
          this.costFormError.set(
            err instanceof AdminDomainError
              ? err.message
              : 'Não foi possível atualizar os custos operacionais.',
          );
        },
      });
  }
}
