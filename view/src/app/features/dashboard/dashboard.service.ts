import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import type { AnnualStatsApiDto, DashboardViewData, Song } from '@ribbit/shared-types';
import { mapAnnualStatsToDashboard } from '../../core/api-mappers';

export type { DashboardViewData };

/** Loads retrospective listening statistics for the Dashboard view. */
@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  /** Fetches raw annual listening statistics from /api/profile/stats. */
  getAnnualStats(year?: number | null): Observable<AnnualStatsApiDto> {
    if (year != null) {
      return this.http.get<AnnualStatsApiDto>('/api/profile/stats', {
        params: { year: String(year) },
      });
    }
    return this.http.get<AnnualStatsApiDto>('/api/profile/stats');
  }

  /** Maps backend annual stats into Dashboard cards, rankings, and chart series. */
  getDashboardData(
    knownSongs: readonly Song[],
    year?: number | null,
  ): Observable<DashboardViewData> {
    return this.getAnnualStats(year).pipe(map((dto) => mapAnnualStatsToDashboard(dto, knownSongs)));
  }
}
