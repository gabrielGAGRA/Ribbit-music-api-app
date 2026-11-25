import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { DashboardService } from './dashboard.service';

describe('DashboardService', () => {
  let service: DashboardService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(DashboardService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('fetches and maps annual stats into DashboardViewData', () => {
    let resultRate = -1;
    let firstArtistSummary = '';
    service.getDashboardData([]).subscribe((data) => {
      resultRate = data.positiveRatePercent;
      firstArtistSummary = data.artists[0]?.summary ?? '';
    });

    const req = httpMock.expectOne('/api/profile/stats');
    expect(req.request.method).toBe('GET');
    req.flush({
      user_id: 1,
      available_years: [2026],
      total_interactions: 10,
      total_likes: 6,
      total_superlikes: 2,
      total_dislikes: 2,
      positive_rate: 0.8,
      top_genres: [{ genre: 'indie', likes: 6, superlikes: 2, dislikes: 1, total_positive: 8 }],
      top_artists: [{ artist: 'Odesza', likes: 6, superlikes: 2, dislikes: 0, total_positive: 8 }],
      by_month: [],
      by_release_year: [],
      by_source: [],
      total_reviews: 1,
      average_rating: 5,
      total_playlists: 2,
      total_jams_participated: 0,
    });

    expect(resultRate).toBe(80);
    expect(firstArtistSummary).toBe('6 curtidas · 2 amadas');
  });

  it('passes selected year as query param when filtering annual stats', () => {
    let selectedYear: number | null = null;
    service.getDashboardData([], 2026).subscribe((data) => {
      selectedYear = data.selectedYear;
    });

    const req = httpMock.expectOne('/api/profile/stats?year=2026');
    expect(req.request.method).toBe('GET');
    req.flush({
      user_id: 1,
      year: 2026,
      available_years: [2026],
      total_interactions: 4,
      total_likes: 4,
      total_superlikes: 0,
      total_dislikes: 0,
      positive_rate: 1,
      top_genres: [],
      top_artists: [],
    });

    expect(selectedYear).toBe(2026);
  });
});
