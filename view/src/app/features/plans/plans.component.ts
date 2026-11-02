import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { IconName, SubscriptionPlan } from '@ribbit/shared-types';
import { mapPlanDtoToSubscriptionPlan } from '../../core/api-mappers';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlanService } from '../../core/services/plan.service';
import { IconComponent } from '../../shared/icon.component';

/** Displays subscription tiers from /api/plans and opens simulated payment checkout for upgrades. */
@Component({
  selector: 'app-plans',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './plans.component.html',
  styleUrl: './plans.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlansComponent implements OnInit {
  protected readonly state = inject(RibbitStateService);
  private readonly planService = inject(PlanService);

  readonly annualPlans = signal<boolean>(true);
  readonly activeSlide = signal<number>(0);

  readonly computedPlans = computed<readonly SubscriptionPlan[]>(() => {
    const annual = this.annualPlans();
    return this.planService.rawPlans().map((dto) => mapPlanDtoToSubscriptionPlan(dto, annual));
  });

  ngOnInit(): void {
    this.planService.loadPlanDtos().subscribe({
      error: () => {
        // Fallback plans remain visible when endpoint is offline
      },
    });
  }

  setAnnual(annual: boolean): void {
    this.annualPlans.set(annual);
  }

  setSlide(slide: number): void {
    this.activeSlide.set(slide);
  }

  getPlanIcon(name: string): IconName {
    if (name === 'Free') return 'pond';
    if (name === 'Individual') return 'star';
    return 'users';
  }

  selectPlan(plan: SubscriptionPlan): void {
    this.state.initiatePlanSelection(plan);
  }
}
