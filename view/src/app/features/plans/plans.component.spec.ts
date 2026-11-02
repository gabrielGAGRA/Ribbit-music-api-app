import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { PlansComponent } from './plans.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { ModalsComponent } from '../../shared/modals.component';

describe('PlansComponent & Mock Checkout Flow', () => {
  let plansComponent: PlansComponent;
  let modalsComponent: ModalsComponent;
  let state: RibbitStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    httpMock = TestBed.inject(HttpTestingController);
    plansComponent = TestBed.runInInjectionContext(() => new PlansComponent());
    modalsComponent = TestBed.runInInjectionContext(() => new ModalsComponent());
  });

  it('loads /api/plans and opens mock payment checkout modal before calling PUT /api/profile/plan', () => {
    writeAuthToken('jwt-token');
    plansComponent.ngOnInit();

    const plansReq = httpMock.expectOne('/api/plans');
    plansReq.flush([
      { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
      { plan_id: 2, name: 'Individual', monthly_price: 14.9, max_profiles: 1 },
      { plan_id: 3, name: 'Família', monthly_price: 27.9, max_profiles: 6 },
    ]);

    const familyPlan = plansComponent.computedPlans().find((item) => item.name === 'Família')!;
    expect(familyPlan).toBeDefined();

    plansComponent.selectPlan(familyPlan);
    expect(state.activeModal()).toBe('checkout');
    expect(modalsComponent.checkoutPlan()?.name).toBe('Família');

    modalsComponent.selectPaymentMethod('card');
    modalsComponent.onCheckoutSubmit(new Event('submit'));

    const putReq = httpMock.expectOne('/api/profile/plan');
    expect(putReq.request.method).toBe('PUT');
    expect(putReq.request.body).toEqual({ new_plan_id: 3 });
    putReq.flush({
      user_id: 1,
      email: 'user@ribbit.app',
      display_name: 'Ouvinte',
      spotify_id: null,
      plan_id: 3,
      blocked_genres: [],
    });

    expect(state.currentPlan()).toBe('Família');
    expect(state.activeModal()).toBeNull();
  });
});
