import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AdminDashboardComponent } from './admin-dashboard.component';
import { AdminStateService } from '../admin-state.service';

describe('AdminDashboardComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('formats net revenue, counts admins and blocked tracks, and computes catalog availability from backend data', () => {
    const state = TestBed.inject(AdminStateService);
    state.hydrateFromBackend();

    httpMock.expectOne('/api/admin/plans').flush([
      { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
      { plan_id: 2, name: 'Individual', monthly_price: 14.9, max_profiles: 1 },
      { plan_id: 3, name: 'Família', monthly_price: 27.9, max_profiles: 6 },
    ]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 8,
      estimated_net_revenue: 72.6,
      gross_revenue: 100.0,
      total_costs: 27.4,
      cost_to_revenue_percent: 27.4,
      paid_plans_revenue: 100.0,
      paid_plans_profit: 79.45,
      users_by_plan: { Free: 2, Individual: 3, Família: 3 },
      revenue_by_plan: { Free: 0, Individual: 44.7, Família: 55.3 },
      profit_by_plan: { Free: 0, Individual: 34.43, Família: 45.02 },
      firestore_usage: {
        reads_today: 25000,
        reads_free_limit: 50000,
        reads_percent: 50,
        reads_rate_per_100k: 0.06,
        writes_today: 5000,
        writes_free_limit: 20000,
        writes_percent: 25,
        writes_rate_per_100k: 0.18,
        deletes_today: 1000,
        deletes_free_limit: 20000,
        deletes_percent: 5,
        deletes_rate_per_100k: 0.02,
        stored_gib: 0.25,
        stored_free_limit_gib: 1.0,
        stored_percent: 25,
        egress_gib_month: 1.0,
        egress_free_limit_gib: 10.0,
        egress_percent: 10,
        monthly_estimated_cost: 0,
      },
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 8,
      total_tracks: 7,
      active_tracks: 5,
      blocked_genres: { sertanejo: 4 },
    });
    httpMock.expectOne('/api/admin/users').flush([]);
    httpMock.expectOne('/api/admin/administrators').flush([
      { user_id: 1, email: 'a@ribbit.app', display_name: 'Admin 1', plan_id: 1, is_admin: true },
      { user_id: 2, email: 'b@ribbit.app', display_name: 'Admin 2', plan_id: 1, is_admin: true },
    ]);
    httpMock.expectOne('/api/admin/tracks?limit=100').flush([]);
    httpMock.expectOne('/api/admin/blocked-tracks').flush([
      {
        track_id: 10,
        title: 'Blocked 1',
        artist: 'Artist',
        duration_seconds: 180,
        genre: 'Pop',
        explicit: false,
        is_deleted: true,
      },
      {
        track_id: 11,
        title: 'Blocked 2',
        artist: 'Artist',
        duration_seconds: 180,
        genre: 'Rock',
        explicit: false,
        is_deleted: true,
      },
    ]);
    httpMock.expectOne('/api/admin/reviews').flush([]);

    const component = TestBed.runInInjectionContext(() => new AdminDashboardComponent());

    expect(component['formattedNetRevenue']()).toContain('72.60');
    expect(component['adminCount']()).toBe(2);
    expect(component['blockedTrackCount']()).toBe(2);
    expect(component['catalogAvailabilityPercent']()).toBe(71);
    expect(component['costToRevenuePercent']()).toBe(27.4);
    expect(component['paidPlansProfit']()).toBe(79.45);
    expect(component['firestoreQuotaRows']()).toHaveLength(5);
    expect(component['firestoreQuotaRows']()[0].percent).toBe(50);
    expect(component['firestoreQuotaRows']()[3].usedLabel).toBe('256.00 MiB');
    expect(state.planBreakdown().find((p) => p.planName === 'Individual')?.profit).toBe(34.43);
    expect(state.planBreakdown().find((p) => p.planName === 'Free')?.isPaid).toBe(false);
  });

  it('edits and saves platform operational costs and flags negative net revenue', () => {
    const state = TestBed.inject(AdminStateService);
    const component = TestBed.runInInjectionContext(() => new AdminDashboardComponent());

    component['openCostEditor']();
    expect(component['editingCosts']()).toBe(true);

    component['costPerTrackInput'].set('0.10');
    component['infraFixedInput'].set('100');
    component['infraPerUserInput'].set('1.5');
    component['savePlatformCosts'](new Event('submit'));

    const putReq = httpMock.expectOne('/api/admin/costs');
    expect(putReq.request.method).toBe('PUT');
    expect(putReq.request.body).toEqual({
      content_cost_per_track: 0.1,
      infrastructure_fixed_cost: 100,
      infrastructure_cost_per_user: 1.5,
    });
    putReq.flush({
      content_cost_per_track: 0.1,
      infrastructure_fixed_cost: 100,
      infrastructure_cost_per_user: 1.5,
    });

    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 2,
      estimated_net_revenue: -80,
      gross_revenue: 23,
      content_cost: 10,
      infrastructure_cost: 93,
      total_costs: 103,
      users_by_plan: {},
      revenue_by_plan: {},
      firestore_usage: {
        reads_today: 1,
        reads_free_limit: 50000,
        reads_percent: 0,
        reads_rate_per_100k: 0.06,
        writes_today: 0,
        writes_free_limit: 20000,
        writes_percent: 0,
        writes_rate_per_100k: 0.18,
        deletes_today: 0,
        deletes_free_limit: 20000,
        deletes_percent: 0,
        deletes_rate_per_100k: 0.02,
        stored_bytes: 512 * 1024,
        stored_gib: 0.000488,
        stored_free_limit_gib: 1.0,
        stored_percent: 0.05,
        egress_bytes_month: 2048,
        egress_gib_month: 0.000002,
        egress_free_limit_gib: 10.0,
        egress_percent: 0,
        monthly_estimated_cost: 0,
      },
    });

    expect(component['editingCosts']()).toBe(false);
    expect(component['isNetNegative']()).toBe(true);
    expect(state.executiveDashboard().totalCosts).toBe(103);
    const refreshedRows = component['firestoreQuotaRows']();
    expect(refreshedRows[0].percentLabel).toBe('< 0.01%');
    expect(refreshedRows[3].usedLabel).toBe('512.00 KiB');
    expect(refreshedRows[4].usedLabel).toBe('2.00 KiB');
    expect(refreshedRows[4].percentLabel).toBe('< 0.01%');
    expect(component['financialBarItems']().map((i) => i.variant)).toEqual([
      'revenue',
      'content',
      'infra',
      'net-negative',
    ]);
  });

  it('validates cost inputs, updates signals, cancels editor, and navigates to sections', () => {
    const component = TestBed.runInInjectionContext(() => new AdminDashboardComponent());

    component['openCostEditor']();
    const inputEl = document.createElement('input');
    inputEl.value = '-5';
    component['updateCostPerTrack']({ target: inputEl } as unknown as Event);
    inputEl.value = '10';
    component['updateInfraFixed']({ target: inputEl } as unknown as Event);
    inputEl.value = '1';
    component['updateInfraPerUser']({ target: inputEl } as unknown as Event);

    component['savePlatformCosts'](new Event('submit'));
    expect(component['costFormError']()).toContain('maiores ou iguais a zero');

    component['cancelCostEditor']();
    expect(component['editingCosts']()).toBe(false);
    expect(component['costFormError']()).toBe('');

    component['goToPlans']();
    component['goToModeration']();
    component['goToUsers']();

    component['openCostEditor']();
    component['costPerTrackInput'].set('0.2');
    component['infraFixedInput'].set('10');
    component['infraPerUserInput'].set('1');
    component['savePlatformCosts'](new Event('submit'));
    httpMock
      .expectOne('/api/admin/costs')
      .flush({ detail: 'Error' }, { status: 400, statusText: 'Bad Request' });
    expect(component['isSavingCosts']()).toBe(false);
    expect(component['costFormError']()).toBeTruthy();
    expect(component['formatCurrency'](100)).toContain('100');
    expect(component['grossRevenue']()).toBeTypeOf('number');
    expect(component['contentCost']()).toBeTypeOf('number');
    expect(component['infrastructureCost']()).toBeTypeOf('number');
    expect(component['totalCosts']()).toBeTypeOf('number');
  });
});
