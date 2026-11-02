import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { AdminPlansComponent } from './admin-plans.component';
import { AdminStateService } from './admin-state.service';

describe('AdminPlansComponent', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
  });

  it('edits plan parameters and surfaces capacity validation errors', () => {
    const state = TestBed.inject(AdminStateService);
    const component = TestBed.runInInjectionContext(() => new AdminPlansComponent());
    const familyPlan = state.plans().find((plan) => plan.plan_id === 3)!;

    component['startEditing'](familyPlan);
    expect(component['editingPlanId']()).toBe(3);

    component['maxProfilesDraft'].set('2');
    component['savePlan'](new Event('submit'), 3);
    expect(component['formError']()).toContain('perfis já vinculados');
    expect(component['editingPlanId']()).toBe(3);

    component['nameDraft'].set('Família Plus');
    component['priceDraft'].set('31.9');
    component['maxProfilesDraft'].set('6');
    component['savePlan'](new Event('submit'), 3);

    expect(component['formError']()).toBe('');
    expect(component['editingPlanId']()).toBeNull();
    expect(state.plans().find((plan) => plan.plan_id === 3)?.name).toBe('Família Plus');
  });
});
