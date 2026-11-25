import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
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

    expect(component['isPremiumLocked']()).toBe(true);
    component['goToPlans']();
    expect(state.activePage()).toBe('plans');
  });

  it('renders backend annual stats when user has a paid plan', () => {
    writeAuthToken('jwt-pro-user');
    component.ngOnInit();

    const req = httpMock.expectOne('/api/profile/stats');
    req.flush({
      user_id: 1,
      available_years: [2026],
      total_interactions: 20,
      total_likes: 10,
      total_superlikes: 5,
      total_dislikes: 5,
      positive_rate: 0.75,
      top_genres: [
        { genre: 'indie', likes: 8, superlikes: 2, dislikes: 1, total_positive: 10 },
        { genre: 'mpb', likes: 2, superlikes: 3, dislikes: 0, total_positive: 5 },
      ],
      top_artists: [
        { artist: 'Terno Rei', likes: 6, superlikes: 2, dislikes: 0, total_positive: 8 },
        { artist: 'Liniker', likes: 4, superlikes: 1, dislikes: 0, total_positive: 5 },
      ],
      by_month: [{ month: 11, likes: 10, superlikes: 5, dislikes: 5, total: 20 }],
      by_release_year: [{ release_year: 2022, likes: 5, superlikes: 3, total_positive: 8 }],
      by_source: [{ source: 'discovery', likes: 10, superlikes: 5, dislikes: 5, total: 20 }],
      total_reviews: 2,
      average_rating: 4.5,
      total_playlists: 3,
      total_jams_participated: 1,
    });

    expect(component['isPremiumLocked']()).toBe(false);
    expect(component['positiveRatePercent']()).toBe(75);
    expect(component['favoriteGenres']()[0]?.genre).toBe('Indie');
    expect(component['favoriteGenres']()[0]?.percentage).toBe(67);
    expect(component['favoriteArtists']()[0]?.summary).toBe('6 curtidas · 2 amadas');
    expect(component['monthlyBars']()).toHaveLength(12);
    expect(component['releaseEras']()[0]?.label).toBe('2020s');
    expect(component['sources']()[0]?.label).toBe('Descoberta');

    component['selectYear'](2026);
    const yearReq = httpMock.expectOne('/api/profile/stats?year=2026');
    expect(yearReq.request.method).toBe('GET');
    yearReq.flush({
      user_id: 1,
      year: 2026,
      available_years: [2026],
      total_interactions: 5,
      total_likes: 5,
      total_superlikes: 0,
      total_dislikes: 0,
      positive_rate: 1,
      top_genres: [],
      top_artists: [],
    });
    expect(component['selectedYear']()).toBe(2026);
    expect(component['positiveRatePercent']()).toBe(100);
  });
});

describe('DashboardComponent DOM', () => {
  let state: RibbitStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    const html = readFileSync(resolve(__dirname, './dashboard.component.html'), 'utf8');
    TestBed.overrideComponent(DashboardComponent, {
      set: {
        template: html,
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [],
        imports: [],
        schemas: [NO_ERRORS_SCHEMA],
      },
    });
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('renders only the dedicated blocked screen when GET /api/profile/stats returns 403 and routes CTA to plans', () => {
    writeAuthToken('jwt-free-user');
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();

    httpMock
      .expectOne('/api/profile/stats')
      .flush(
        { detail: 'Feature exclusive to Premium subscribers.' },
        { status: 403, statusText: 'Forbidden' },
      );
    fixture.detectChanges();

    const root = fixture.nativeElement;
    if (!(root instanceof HTMLElement)) {
      throw new TypeError('Expected root HTMLElement');
    }
    const blockedScreen = root.querySelector('.dashboard-blocked-screen');
    const ctaButton = root.querySelector('.blocked-cta');
    expect(blockedScreen).not.toBeNull();
    expect(root.querySelector('.dashboard-hero')).toBeNull();
    expect(root.querySelector('.metric-grid')).toBeNull();
    expect(root.querySelector('.favorite-artists')).toBeNull();
    if (!(ctaButton instanceof HTMLButtonElement)) {
      throw new TypeError('Expected blocked CTA button');
    }

    ctaButton.click();
    expect(state.activePage()).toBe('plans');
  });

  it('renders annual dashboard graphs and year filter without static mood card when GET /api/profile/stats succeeds', () => {
    writeAuthToken('jwt-admin-or-paid');
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();

    httpMock.expectOne('/api/profile/stats').flush({
      user_id: 1,
      available_years: [2026],
      total_interactions: 12,
      total_likes: 7,
      total_superlikes: 2,
      total_dislikes: 3,
      positive_rate: 0.75,
      top_genres: [{ genre: 'rock', likes: 7, superlikes: 2, dislikes: 1, total_positive: 9 }],
      top_artists: [{ artist: 'Queen', likes: 7, superlikes: 2, dislikes: 0, total_positive: 9 }],
      by_month: [{ month: 11, likes: 7, superlikes: 2, dislikes: 3, total: 12 }],
      by_release_year: [{ release_year: 1975, likes: 7, superlikes: 2, total_positive: 9 }],
      by_source: [{ source: 'discovery', likes: 7, superlikes: 2, dislikes: 3, total: 12 }],
      total_reviews: 1,
      average_rating: 5,
      total_playlists: 2,
      total_jams_participated: 0,
    });
    fixture.detectChanges();

    const root = fixture.nativeElement;
    if (!(root instanceof HTMLElement)) {
      throw new TypeError('Expected root HTMLElement');
    }
    expect(root.querySelector('.dashboard-blocked-screen')).toBeNull();
    expect(root.querySelector('.mood-card')).toBeNull();
    expect(root.querySelector('.dashboard-hero')).not.toBeNull();
    expect(root.querySelector('.approval-ring .ring-center strong')?.textContent?.trim()).toBe('75%');
    expect(root.querySelector('.monthly-chart-svg')).not.toBeNull();
    expect(root.querySelector('.dashboard-secondary-columns')).not.toBeNull();

    const yearButtons = root.querySelectorAll('.year-pill');
    expect(yearButtons.length).toBe(2);
    const year2026Button = yearButtons[1];
    if (!(year2026Button instanceof HTMLButtonElement)) {
      throw new TypeError('Expected year filter button');
    }
    year2026Button.click();
    const yearReq = httpMock.expectOne('/api/profile/stats?year=2026');
    yearReq.flush({
      user_id: 1,
      year: 2026,
      available_years: [2026],
      total_interactions: 0,
      total_likes: 0,
      total_superlikes: 0,
      total_dislikes: 0,
      positive_rate: 0,
      top_genres: [],
      top_artists: [],
    });
    fixture.detectChanges();
    expect(root.querySelector('.monthly-chart-svg')).toBeNull();
  });
});
