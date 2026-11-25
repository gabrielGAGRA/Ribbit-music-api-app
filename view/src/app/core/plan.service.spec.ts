import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { PlanService } from './plan.service';

describe('PlanService', () => {
  let service: PlanService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PlanService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('loads plan DTOs, updates rawPlans cache, and maps subscription plans', () => {
    let resolvedNames: string[] = [];
    service.getPlans(false).subscribe((plans) => {
      resolvedNames = plans.map((p) => p.name);
    });

    const req = httpMock.expectOne('/api/plans');
    expect(req.request.method).toBe('GET');
    req.flush([
      { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
      { plan_id: 2, name: 'Pro', monthly_price: 19.9, max_profiles: 1 },
    ]);

    expect(resolvedNames).toEqual(['Free', 'Pro']);
    expect(service.rawPlans()).toHaveLength(2);
    expect(service.resolvePlanIdByName(' pro ')).toBe(2);
    expect(service.resolvePlanIdByName('Unknown')).toBe(1);
  });

  it('does not overwrite rawPlans cache when backend returns empty array', () => {
    const initialCount = service.rawPlans().length;
    service.loadPlanDtos().subscribe();

    const req = httpMock.expectOne('/api/plans');
    req.flush([]);
    expect(service.rawPlans()).toHaveLength(initialCount);
  });

  it('changes and cancels the user plan', () => {
    service.changePlan(3).subscribe();
    const putReq = httpMock.expectOne('/api/profile/plan');
    expect(putReq.request.method).toBe('PUT');
    expect(putReq.request.body).toEqual({ new_plan_id: 3 });
    putReq.flush({
      user_id: 1,
      email: 'u@ribbit.app',
      display_name: 'U',
      plan_id: 3,
      is_admin: false,
    });

    service.cancelPlan().subscribe();
    const delReq = httpMock.expectOne('/api/profile/plan');
    expect(delReq.request.method).toBe('DELETE');
    delReq.flush({
      user_id: 1,
      email: 'u@ribbit.app',
      display_name: 'U',
      plan_id: 1,
      is_admin: false,
    });
  });
});
