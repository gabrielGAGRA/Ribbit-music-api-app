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
      users_by_plan: { Free: 2, Individual: 3, Família: 3 },
      revenue_by_plan: { Free: 0, Individual: 44.7, Família: 27.9 },
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

    expect(component['formattedNetRevenue']()).toContain('72,60');
    expect(component['adminCount']()).toBe(2);
    expect(component['blockedTrackCount']()).toBe(2);
    expect(component['catalogAvailabilityPercent']()).toBe(71);
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
    });

    expect(component['editingCosts']()).toBe(false);
    expect(component['isNetNegative']()).toBe(true);
    expect(state.executiveDashboard().totalCosts).toBe(103);
  });
});
