import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay } from 'rxjs/operators';
import { MetricItem, RankedGenre } from '@ribbit/shared-types';
import { MOCK_METRICS, MOCK_FAVORITE_GENRES } from '../mocks/dashboard.mock';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  getMetrics(): Observable<readonly MetricItem[]> {
    return of(MOCK_METRICS).pipe(delay(100));
  }

  getFavoriteGenres(): Observable<readonly RankedGenre[]> {
    return of(MOCK_FAVORITE_GENRES).pipe(delay(100));
  }
}
