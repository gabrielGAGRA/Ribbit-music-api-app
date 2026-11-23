import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { readInputValue } from '@shared/dom-event-values';
import { IconComponent } from '@shared/icon.component';
import type { AdminPlanItem } from '../admin-mappers';
import { AdminStateService } from '../admin-state.service';

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
  protected readonly adminState = inject(AdminStateService);

  protected readonly editingPlanId = signal<number | null>(null);
  protected readonly nameDraft = signal<string>('');
  protected readonly priceDraft = signal<string>('0');
  protected readonly maxProfilesDraft = signal<string>('1');
  protected readonly formError = signal<string>('');
  protected readonly isSaving = signal<boolean>(false);

  protected formatPrice(price: number): string {
    return BRL_FORMATTER.format(price);
  }

  protected subscriberCount(planName: string): number {
    return this.adminState.executiveDashboard().usersByPlan[planName] ?? 0;
  }

  protected startEditing(plan: AdminPlanItem): void {
    this.formError.set('');
    this.editingPlanId.set(plan.planId);
    this.nameDraft.set(plan.name);
    this.priceDraft.set(String(plan.monthlyPrice));
    this.maxProfilesDraft.set(String(plan.maxProfiles));
  }

  protected cancelEditing(): void {
    this.formError.set('');
    this.editingPlanId.set(null);
  }

  protected updateNameDraft(event: Event): void {
    this.nameDraft.set(readInputValue(event));
  }

  protected updatePriceDraft(event: Event): void {
    this.priceDraft.set(readInputValue(event));
  }

  protected updateMaxProfilesDraft(event: Event): void {
    this.maxProfilesDraft.set(readInputValue(event));
  }

  protected savePlan(event: Event, planId: number): void {
    event.preventDefault();
    if (this.isSaving()) return;
    this.formError.set('');

    const parsedPrice = Number(this.priceDraft());
    const parsedMaxProfiles = Number(this.maxProfilesDraft());

    this.isSaving.set(true);
    this.adminState
      .updatePlan(planId, {
        new_name: this.nameDraft(),
        new_price: parsedPrice,
        max_profiles: parsedMaxProfiles,
      })
      .subscribe({
        next: () => {
          this.isSaving.set(false);
          this.editingPlanId.set(null);
        },
        error: (error: Error) => {
          this.isSaving.set(false);
          this.formError.set(error.message);
        },
      });
  }
}
