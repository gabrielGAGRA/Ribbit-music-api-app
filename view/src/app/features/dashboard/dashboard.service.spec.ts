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
    let resultHours = '';
    service.getDashboardData([]).subscribe((data) => {
      resultHours = data.hoursLabel;
    });

    const req = httpMock.expectOne('/api/profile/stats');
    expect(req.request.method).toBe('GET');
    req.flush({
      total_likes: 10,
      estimated_listening_hours: 12.5,
      top_genres: ['Indie'],
      top_artists: ['Odesza'],
    });

    expect(resultHours).toBe('12.5h');
  });
});
