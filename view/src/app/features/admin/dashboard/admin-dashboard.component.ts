import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { readInputValue } from '@shared/dom-event-values';
import { WidthPercentDirective } from '@shared/width-percent.directive';
import { IconComponent } from '@shared/icon.component';
import { AdminDomainError } from '../admin-domain-error';
import { AdminStateService } from '../admin-state.service';

const USD_FORMATTER = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
});

export interface FirestoreQuotaRow {
  readonly id: string;
  readonly label: string;
  readonly usedLabel: string;
  readonly limitLabel: string;
  readonly rateHint: string;
  readonly percent: number;
  readonly percentLabel: string;
}

const KIB = 1024;
const MIB = 1024 ** 2;
const GIB = 1024 ** 3;

function formatBinaryBytes(bytes: number, fallbackGib: number): string {
  const effectiveBytes = bytes > 0 ? bytes : Math.round(fallbackGib * GIB);
  if (effectiveBytes <= 0) return '0 B';
  if (effectiveBytes < KIB) return `${effectiveBytes} B`;
  if (effectiveBytes < MIB) return `${(effectiveBytes / KIB).toFixed(2)} KiB`;
  if (effectiveBytes < GIB) return `${(effectiveBytes / MIB).toFixed(2)} MiB`;
  return `${(effectiveBytes / GIB).toFixed(2)} GiB`;
}

function formatQuotaPercent(usedValue: number, percent: number): string {
  if (usedValue > 0 && percent === 0) return '< 0.01%';
  return `${percent}%`;
}

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
    USD_FORMATTER.format(this.adminState.executiveDashboard().estimatedNetRevenue),
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

  protected readonly costToRevenuePercent = computed<number>(
    () => this.adminState.executiveDashboard().costToRevenuePercent,
  );

  protected readonly costTrackerBarPercent = computed<number>(() =>
    Math.min(100, Math.max(0, this.costToRevenuePercent())),
  );

  protected readonly paidPlansRevenue = computed<number>(
    () => this.adminState.executiveDashboard().paidPlansRevenue,
  );

  protected readonly paidPlansProfit = computed<number>(
    () => this.adminState.executiveDashboard().paidPlansProfit,
  );

  protected readonly isPaidPlansProfitNegative = computed<boolean>(
    () => this.paidPlansProfit() < 0,
  );

  protected readonly firestoreQuotaRows = computed<readonly FirestoreQuotaRow[]>(() => {
    const q = this.adminState.executiveDashboard().firestoreUsage;
    return [
      {
        id: 'reads',
        label: 'Document reads',
        usedLabel: q.readsToday.toLocaleString('en-US'),
        limitLabel: `${q.readsFreeLimit.toLocaleString('en-US')} / dia`,
        rateHint: `~$${q.readsRatePer100k.toFixed(2)} / 100k`,
        percent: q.readsPercent,
        percentLabel: formatQuotaPercent(q.readsToday, q.readsPercent),
      },
      {
        id: 'writes',
        label: 'Document writes',
        usedLabel: q.writesToday.toLocaleString('en-US'),
        limitLabel: `${q.writesFreeLimit.toLocaleString('en-US')} / dia`,
        rateHint: `~$${q.writesRatePer100k.toFixed(2)} / 100k`,
        percent: q.writesPercent,
        percentLabel: formatQuotaPercent(q.writesToday, q.writesPercent),
      },
      {
        id: 'deletes',
        label: 'Document deletes',
        usedLabel: q.deletesToday.toLocaleString('en-US'),
        limitLabel: `${q.deletesFreeLimit.toLocaleString('en-US')} / dia`,
        rateHint: `~$${q.deletesRatePer100k.toFixed(2)} / 100k`,
        percent: q.deletesPercent,
        percentLabel: formatQuotaPercent(q.deletesToday, q.deletesPercent),
      },
      {
        id: 'storage',
        label: 'Stored data',
        usedLabel: formatBinaryBytes(q.storedBytes, q.storedGib),
        limitLabel: `${q.storedFreeLimitGib} GiB`,
        rateHint: 'Free tier',
        percent: q.storedPercent,
        percentLabel: formatQuotaPercent(q.storedBytes + q.storedGib, q.storedPercent),
      },
      {
        id: 'egress',
        label: 'Outbound data transfer',
        usedLabel: formatBinaryBytes(q.egressBytesMonth, q.egressGibMonth),
        limitLabel: `${q.egressFreeLimitGib} GiB / mês`,
        rateHint: 'Free tier',
        percent: q.egressPercent,
        percentLabel: formatQuotaPercent(q.egressBytesMonth + q.egressGibMonth, q.egressPercent),
      },
    ];
  });

  protected readonly financialBarItems = computed<
    readonly {
      readonly label: string;
      readonly amount: number;
      readonly percent: number;
      readonly variant: 'revenue' | 'content' | 'infra' | 'net' | 'net-negative';
    }[]
  >(() => {
    const dash = this.adminState.executiveDashboard();
    const maxVal = Math.max(
      dash.grossRevenue,
      dash.contentCost,
      dash.infrastructureCost,
      Math.abs(dash.estimatedNetRevenue),
      1,
    );
    const toPercent = (value: number): number =>
      Math.min(100, Math.round((Math.abs(value) / maxVal) * 100));

    return [
      {
        label: 'Receita Bruta',
        amount: dash.grossRevenue,
        percent: toPercent(dash.grossRevenue),
        variant: 'revenue',
      },
      {
        label: 'Custo de Conteúdos',
        amount: dash.contentCost,
        percent: toPercent(dash.contentCost),
        variant: 'content',
      },
      {
        label: 'Custo de Infraestrutura',
        amount: dash.infrastructureCost,
        percent: toPercent(dash.infrastructureCost),
        variant: 'infra',
      },
      {
        label: 'Receita Líquida',
        amount: dash.estimatedNetRevenue,
        percent: toPercent(dash.estimatedNetRevenue),
        variant: dash.estimatedNetRevenue < 0 ? 'net-negative' : 'net',
      },
    ];
  });

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
    return USD_FORMATTER.format(amount);
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
