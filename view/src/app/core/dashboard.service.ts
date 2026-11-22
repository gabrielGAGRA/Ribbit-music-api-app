import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import type {
  AnnualStatsApiDto,
  MetricItem,
  RankedArtist,
  RankedGenre,
  Song,
} from '@ribbit/shared-types';
import { mapAnnualStatsToDashboard } from '../api-mappers';

export interface DashboardViewData {
  readonly hoursLabel: string;
  readonly metrics: readonly MetricItem[];
  readonly genres: readonly RankedGenre[];
  readonly artists: readonly RankedArtist[];
}

/** Loads retrospective listening statistics for the Dashboard view. */
@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  /** Fetches raw annual listening statistics from /api/profile/stats. */
  getAnnualStats(): Observable<AnnualStatsApiDto> {
    return this.http.get<AnnualStatsApiDto>('/api/profile/stats');
  }

  /** Maps backend annual stats into Dashboard cards and ranked lists. */
  getDashboardData(knownSongs: readonly Song[]): Observable<DashboardViewData> {
    return this.getAnnualStats().pipe(map((dto) => mapAnnualStatsToDashboard(dto, knownSongs)));
  }
}
