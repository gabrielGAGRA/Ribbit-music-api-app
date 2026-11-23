import type { OnInit } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { IconName, SubscriptionPlan } from '@ribbit/shared-types';
import { mapPlanDtoToSubscriptionPlan } from '../../core/api-mappers';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlanService } from '../../core/plan.service';
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

  protected readonly annualPlans = signal<boolean>(true);
  protected readonly activeSlide = signal<number>(0);

  protected readonly computedPlans = computed<readonly SubscriptionPlan[]>(() => {
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

  protected setAnnual(annual: boolean): void {
    this.annualPlans.set(annual);
  }

  protected setSlide(slide: number): void {
    this.activeSlide.set(slide);
  }

  protected getPlanIcon(name: string): IconName {
    if (name === 'Free') return 'pond';
    if (name === 'Individual') return 'star';
    return 'users';
  }

  protected selectPlan(plan: SubscriptionPlan): void {
    this.state.initiatePlanSelection(plan);
  }
}
