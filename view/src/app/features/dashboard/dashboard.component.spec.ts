import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { DashboardComponent } from './dashboard.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('DashboardComponent', () => {
  let component: DashboardComponent;
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
    component = TestBed.runInInjectionContext(() => new DashboardComponent());
  });

  it('displays premium upgrade notice when GET /api/profile/stats returns 403', () => {
    writeAuthToken('jwt-free-user');
    component.ngOnInit();

    const req = httpMock.expectOne('/api/profile/stats');
    req.flush(
      { detail: 'Annual statistics require a paid subscription plan.' },
      { status: 403, statusText: 'Forbidden' },
    );

    expect(component.isPremiumLocked()).toBe(true);
    component.goToPlans();
    expect(state.activePage()).toBe('plans');
  });

  it('renders backend annual stats when user has a paid plan', () => {
    writeAuthToken('jwt-pro-user');
    component.ngOnInit();

    const req = httpMock.expectOne('/api/profile/stats');
    req.flush({
      total_likes: 42,
      estimated_listening_hours: 18.4,
      top_genres: ['Indie', 'MPB'],
      top_artists: ['Terno Rei', 'Liniker'],
    });

    expect(component.isPremiumLocked()).toBe(false);
    expect(component.hoursLabel()).toBe('18.4h');
    expect(component.favoriteGenres()[0]?.genre).toBe('Indie');
  });
});
