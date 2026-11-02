import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';
import type {
  CommunityReview,
  DecisionKind,
  InteractionApiDto,
  RecentInteractedTrackApiDto,
  ReviewApiDto,
  Song,
  TrackApiDto,
} from '@ribbit/shared-types';
import {
  mapDecisionToApiAction,
  mapReviewDtoToCommunityReview,
  mapTrackDtoToSong,
} from '../api-mappers';
import { MOCK_SONGS } from '../mocks/songs.mock';

export interface SearchTracksParams {
  readonly query?: string;
  readonly artist?: string;
  readonly album?: string;
  readonly genre?: string;
  readonly year?: number;
  readonly limit?: number;
}

function buildSearchHttpParams(params: SearchTracksParams): HttpParams {
  let httpParams = new HttpParams().set('limit', String(params.limit ?? 30));
  const optionalPairs: readonly [string, string | undefined][] = [
    ['query', params.query?.trim()],
    ['artist', params.artist],
    ['album', params.album],
    ['genre', params.genre && params.genre !== 'Todos' ? params.genre : undefined],
    [
      'year',
      params.year !== undefined && Number.isFinite(params.year) ? String(params.year) : undefined,
    ],
  ];
  for (const [key, value] of optionalPairs) {
    if (value && value.length > 0) {
      httpParams = httpParams.set(key, value);
    }
  }
  return httpParams;
}

/** Coordinates discovery, catalog search, and community reviews against /api. */
@Injectable({ providedIn: 'root' })
export class SongService {
  private readonly http = inject(HttpClient);
  private readonly songsSignal = signal<readonly Song[]>(MOCK_SONGS);
  private readonly reviewsSignal = signal<readonly CommunityReview[]>([]);

  readonly songs = this.songsSignal.asReadonly();
  readonly reviews = this.reviewsSignal.asReadonly();

  /** Fetches the next candidate track from /api/discovery/next, or null when deck is empty. */
  getNextDiscoverySong(): Observable<Song | null> {
    return this.http
      .get<TrackApiDto | null>('/api/discovery/next')
      .pipe(map((dto) => (dto ? mapTrackDtoToSong(dto) : null)));
  }

  /** Records a swipe gesture on /api/discovery/interact. */
  recordSwipe(trackId: number, kind: DecisionKind): Observable<InteractionApiDto> {
    return this.http.post<InteractionApiDto>('/api/discovery/interact', {
      track_id: trackId,
      action: mapDecisionToApiAction(kind),
    });
  }

  /** Searches the track catalog using /api/tracks/search. */
  searchSongs(params: SearchTracksParams = {}): Observable<readonly Song[]> {
    const httpParams = buildSearchHttpParams(params);
    const isUnfiltered = !params.query && !params.genre && params.year === undefined;
    return this.http.get<readonly TrackApiDto[]>('/api/tracks/search', { params: httpParams }).pipe(
      map((dtos) => dtos.map((dto) => mapTrackDtoToSong(dto))),
      tap((songs) => {
        if (isUnfiltered && songs.length > 0) {
          this.songsSignal.set(songs);
        }
      }),
    );
  }

  /** Loads the full active catalog snapshot into the shared songs signal. */
  getSongs(): Observable<readonly Song[]> {
    return this.searchSongs({ limit: 50 });
  }

  /** Fetches recently interacted tracks paired with their interaction metadata. */
  getRecentInteractedTracks(limit = 30): Observable<readonly RecentInteractedTrackApiDto[]> {
    const params = new HttpParams().set('limit', String(limit));
    return this.http.get<readonly RecentInteractedTrackApiDto[]>('/api/reviews/recent-interacted', {
      params,
    });
  }

  /** Loads the community reviews feed from /api/reviews/feed. */
  loadCommunityFeed(
    options: {
      readonly trackLookup?: ReadonlyMap<number, Song>;
      readonly currentUserId?: number;
      readonly currentUserName?: string;
      readonly days?: number;
      readonly limit?: number;
    } = {},
  ): Observable<readonly CommunityReview[]> {
    const params = new HttpParams()
      .set('days', String(options.days ?? 30))
      .set('limit', String(options.limit ?? 20));
    return this.http.get<readonly ReviewApiDto[]>('/api/reviews/feed', { params }).pipe(
      map((dtos) =>
        dtos.map((dto) =>
          mapReviewDtoToCommunityReview({
            dto,
            track: options.trackLookup?.get(dto.track_id),
            currentUserId: options.currentUserId,
            currentUserName: options.currentUserName,
          }),
        ),
      ),
      tap((reviews) => {
        this.reviewsSignal.set(reviews);
      }),
    );
  }

  /** Returns the current community reviews feed. */
  getReviews(): Observable<readonly CommunityReview[]> {
    return this.loadCommunityFeed();
  }

  /** Fetches reviews for a specific track ID. */
  getTrackReviews(options: {
    readonly trackId: number;
    readonly track?: Song;
    readonly currentUserId?: number;
    readonly currentUserName?: string;
  }): Observable<readonly CommunityReview[]> {
    return this.http.get<readonly ReviewApiDto[]>(`/api/reviews/track/${options.trackId}`).pipe(
      map((dtos) =>
        dtos.map((dto) =>
          mapReviewDtoToCommunityReview({
            dto,
            track: options.track,
            currentUserId: options.currentUserId,
            currentUserName: options.currentUserName,
          }),
        ),
      ),
    );
  }

  /** Publishes a star rating and optional comment on a track. */
  publishReview(options: {
    readonly trackId: number;
    readonly rating: number;
    readonly text?: string;
    readonly track?: Song;
    readonly currentUserId?: number;
    readonly currentUserName?: string;
  }): Observable<CommunityReview> {
    return this.http
      .post<ReviewApiDto>('/api/reviews', {
        track_id: options.trackId,
        rating: options.rating,
        text: options.text ?? null,
      })
      .pipe(
        map((dto) =>
          mapReviewDtoToCommunityReview({
            dto,
            track: options.track,
            currentUserId: options.currentUserId,
            currentUserName: options.currentUserName,
          }),
        ),
      );
  }

  /** Deletes an existing review authored by the authenticated user. */
  deleteReview(reviewId: number): Observable<boolean> {
    return this.http
      .delete<{ readonly success: boolean }>(`/api/reviews/${reviewId}`)
      .pipe(map((res) => res.success));
  }

  /** Likes a community review comment on the backend. */
  likeReview(reviewId: number): Observable<ReviewApiDto> {
    return this.http.post<ReviewApiDto>(`/api/reviews/${reviewId}/like`, {});
  }

  /** Likes a track directly from search results and optionally saves it to a playlist. */
  likeAndSaveSearchTrack(trackId: number, playlistId?: number): Observable<boolean> {
    return this.http
      .post<{ readonly success: boolean }>(`/api/reviews/${trackId}/like-and-save`, {
        playlist_id: playlistId ?? null,
      })
      .pipe(map((res) => res.success));
  }
}
