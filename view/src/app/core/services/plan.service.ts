import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';
import type { PlanApiDto, SubscriptionPlan, UserApiDto } from '@ribbit/shared-types';
import { mapPlanDtoToSubscriptionPlan } from '../api-mappers';

const DEFAULT_PLAN_DTOS: readonly PlanApiDto[] = [
  { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
  { plan_id: 2, name: 'Individual', monthly_price: 14.9, max_profiles: 1 },
  { plan_id: 3, name: 'Família', monthly_price: 27.9, max_profiles: 6 },
];

/** Fetches subscription tiers and manages plan changes via /api/plans and /api/profile/plan. */
@Injectable({ providedIn: 'root' })
export class PlanService {
  private readonly http = inject(HttpClient);
  private readonly rawPlansSignal = signal<readonly PlanApiDto[]>(DEFAULT_PLAN_DTOS);

  readonly rawPlans = this.rawPlansSignal.asReadonly();

  /** Loads raw plan definitions from the backend and updates local cache. */
  loadPlanDtos(): Observable<readonly PlanApiDto[]> {
    return this.http.get<readonly PlanApiDto[]>('/api/plans').pipe(
      tap((plans) => {
        if (plans.length > 0) {
          this.rawPlansSignal.set(plans);
        }
      }),
    );
  }

  /** Returns formatted SubscriptionPlan view models for monthly or annual billing. */
  getPlans(annual = true): Observable<readonly SubscriptionPlan[]> {
    return this.loadPlanDtos().pipe(
      map((plans) => plans.map((dto) => mapPlanDtoToSubscriptionPlan(dto, annual))),
    );
  }

  /** Resolves a numeric plan_id by plan name using cached backend plans. */
  resolvePlanIdByName(name: string): number {
    const normalized = name.trim().toLowerCase();
    const match = this.rawPlansSignal().find(
      (plan) => plan.name.trim().toLowerCase() === normalized,
    );
    return match?.plan_id ?? 1;
  }

  /** Switches the authenticated user's active subscription plan. */
  changePlan(newPlanId: number): Observable<UserApiDto> {
    return this.http.put<UserApiDto>('/api/profile/plan', {
      new_plan_id: newPlanId,
    });
  }

  /** Cancels a paid subscription and downgrades the user back to Free. */
  cancelPlan(): Observable<UserApiDto> {
    return this.http.delete<UserApiDto>('/api/profile/plan');
  }
}
