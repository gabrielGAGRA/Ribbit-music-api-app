import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';
import { AdminDashboardComponent } from './admin-dashboard.component';
import { AdminStateService } from './admin-state.service';

describe('AdminDashboardComponent', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([])],
    });
  });

  it('formats net revenue, counts admins and blocked tracks, and updates catalog availability', () => {
    const state = TestBed.inject(AdminStateService);
    const component = TestBed.runInInjectionContext(() => new AdminDashboardComponent());

    expect(component['formattedNetRevenue']()).toContain('72,60');
    expect(component['adminCount']()).toBe(2);
    expect(component['blockedTrackCount']()).toBe(2);
    expect(component['catalogAvailabilityPercent']()).toBe(71);

    state.setTrackBlocked(101, true);
    expect(component['blockedTrackCount']()).toBe(3);
    expect(component['catalogAvailabilityPercent']()).toBe(57);
  });
});
