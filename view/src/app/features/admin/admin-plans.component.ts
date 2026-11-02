import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import type { PlanApiDto } from '@ribbit/shared-types';
import { safeInject } from '../../core/safe-inject';
import { IconComponent } from '../../shared/icon.component';
import { AdminStateService } from './admin-state.service';

const BRL_FORMATTER = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
});

/** Subscription tier management screen backing GET /api/admin/plans and PUT /api/admin/plans/{id}. */
@Component({
  selector: 'app-admin-plans',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './admin-plans.component.html',
  styleUrl: './admin-plans.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminPlansComponent {
  protected readonly adminState = safeInject(AdminStateService, new AdminStateService());

  protected readonly editingPlanId = signal<number | null>(null);
  protected readonly nameDraft = signal<string>('');
  protected readonly priceDraft = signal<string>('0');
  protected readonly maxProfilesDraft = signal<string>('1');
  protected readonly formError = signal<string>('');

  protected formatPrice(price: number): string {
    return BRL_FORMATTER.format(price);
  }

  protected subscriberCount(planName: string): number {
    return this.adminState.executiveDashboard().users_by_plan[planName] ?? 0;
  }

  protected occupiedProfiles(planId: number): number {
    return this.adminState.getOccupiedProfilesForPlan(planId);
  }

  protected startEditing(plan: PlanApiDto): void {
    this.formError.set('');
    this.editingPlanId.set(plan.plan_id);
    this.nameDraft.set(plan.name);
    this.priceDraft.set(String(plan.monthly_price));
    this.maxProfilesDraft.set(String(plan.max_profiles));
  }

  protected cancelEditing(): void {
    this.formError.set('');
    this.editingPlanId.set(null);
  }

  protected updateNameDraft(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.nameDraft.set(target.value);
  }

  protected updatePriceDraft(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.priceDraft.set(target.value);
  }

  protected updateMaxProfilesDraft(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.maxProfilesDraft.set(target.value);
  }

  protected savePlan(event: Event, planId: number): void {
    event.preventDefault();
    this.formError.set('');

    const parsedPrice = Number(this.priceDraft());
    const parsedMaxProfiles = Number(this.maxProfilesDraft());

    try {
      this.adminState.updatePlan(planId, {
        new_name: this.nameDraft(),
        new_price: parsedPrice,
        max_profiles: parsedMaxProfiles,
      });
      this.editingPlanId.set(null);
    } catch (error: unknown) {
      this.formError.set(
        error instanceof Error ? error.message : 'Erro ao atualizar plano de assinatura.',
      );
    }
  }
}
