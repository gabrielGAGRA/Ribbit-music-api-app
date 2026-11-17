import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AdminPlansComponent } from './admin-plans.component';
import { AdminStateService } from './admin-state.service';

describe('AdminPlansComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('edits plan parameters via PUT /api/admin/plans/{id} and surfaces backend validation errors', () => {
    const state = TestBed.inject(AdminStateService);
    state.hydrateFromBackend();
    httpMock.expectOne('/api/admin/plans').flush([
      { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
      { plan_id: 2, name: 'Individual', monthly_price: 14.9, max_profiles: 1 },
      { plan_id: 3, name: 'Família', monthly_price: 27.9, max_profiles: 6 },
    ]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 10,
      estimated_net_revenue: 100,
      users_by_plan: { Free: 5, Individual: 3, Família: 2 },
      revenue_by_plan: { Free: 0, Individual: 44.7, Família: 55.8 },
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 10,
      total_tracks: 0,
      active_tracks: 0,
      blocked_genres: {},
    });
    httpMock.expectOne('/api/admin/users').flush([]);
    httpMock.expectOne('/api/admin/administrators').flush([]);
    httpMock.expectOne('/api/tracks/search?limit=100').flush([]);
    httpMock.expectOne('/api/admin/blocked-tracks').flush([]);
    httpMock.expectOne('/api/admin/reviews').flush([]);

    const component = TestBed.runInInjectionContext(() => new AdminPlansComponent());
    const familyPlan = state.plans().find((plan) => plan.plan_id === 3)!;

    component['startEditing'](familyPlan);
    expect(component['editingPlanId']()).toBe(3);

    component['maxProfilesDraft'].set('2');
    component['savePlan'](new Event('submit'), 3);
    const failedReq = httpMock.expectOne('/api/admin/plans/3');
    failedReq.flush(
      {
        error: 'BusinessRuleViolationError',
        message: 'Plan profile limit cannot be less than currently linked member profiles.',
      },
      { status: 400, statusText: 'Bad Request' },
    );
    expect(component['formError']()).toContain('linked member profiles');
    expect(component['editingPlanId']()).toBe(3);

    component['nameDraft'].set('Família Plus');
    component['priceDraft'].set('31.9');
    component['maxProfilesDraft'].set('6');
    component['savePlan'](new Event('submit'), 3);

    const updateReq = httpMock.expectOne('/api/admin/plans/3');
    expect(updateReq.request.method).toBe('PUT');
    expect(updateReq.request.body).toEqual({
      new_name: 'Família Plus',
      new_price: 31.9,
      max_profiles: 6,
    });
    updateReq.flush({ plan_id: 3, name: 'Família Plus', monthly_price: 31.9, max_profiles: 6 });

    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 10,
      estimated_net_revenue: 108.5,
      users_by_plan: { Free: 5, Individual: 3, 'Família Plus': 2 },
      revenue_by_plan: { Free: 0, Individual: 44.7, 'Família Plus': 63.8 },
    });
    httpMock.expectOne('/api/admin/users').flush([]);

    expect(component['formError']()).toBe('');
    expect(component['editingPlanId']()).toBeNull();
    expect(state.plans().find((plan) => plan.plan_id === 3)?.name).toBe('Família Plus');
  });
});
