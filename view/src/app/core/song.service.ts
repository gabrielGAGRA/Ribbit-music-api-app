import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';
import type {
  CommunityReview,
  DecisionKind,
  InteractionApiDto,
  RecentInteractedTrackApiDto,
  RecordTrackAccessApiDto,
  ReviewApiDto,
  Song,
  TrackAccessSource,
  TrackApiDto,
  UndoInteractionApiDto,
  UserAccessHistoryApiDto,
} from '@ribbit/shared-types';
import {
  mapDecisionToApiAction,
  mapReviewDtoToCommunityReview,
  mapTrackDtoToSong,
} from './api-mappers';

export type ReviewSortOption = 'recent' | 'oldest' | 'likes' | 'rating_desc' | 'rating_asc';

export interface SearchTracksParams {
  readonly query?: string;
  readonly artist?: string;
  readonly album?: string;
  readonly genre?: string;
  readonly year?: number;
  readonly startYear?: number;
  readonly endYear?: number;
  readonly minRating?: number | null;
  readonly sortBy?: 'rating_desc' | 'rating_asc' | null;
  readonly limit?: number;
}

function formatFiniteNumber(value?: number | null): string | undefined {
  return value != null && Number.isFinite(value) ? String(value) : undefined;
}

function buildSearchHttpParams(params: SearchTracksParams): HttpParams {
  let httpParams = new HttpParams().set('limit', String(params.limit ?? 30));
  const optionalPairs: readonly [string, string | undefined][] = [
    ['query', params.query?.trim()],
    ['artist', params.artist],
    ['album', params.album],
    ['genre', params.genre && params.genre !== 'Todos' ? params.genre : undefined],
    ['year', formatFiniteNumber(params.year)],
    ['start_year', formatFiniteNumber(params.startYear)],
    ['end_year', formatFiniteNumber(params.endYear)],
    ['min_rating', formatFiniteNumber(params.minRating)],
    ['sort_by', params.sortBy ?? undefined],
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
  private readonly songsSignal = signal<readonly Song[]>([]);
  private readonly reviewsSignal = signal<readonly CommunityReview[]>([]);
  private readonly userReviewsSignal = signal<readonly CommunityReview[]>([]);

  readonly songs = this.songsSignal.asReadonly();
  readonly reviews = this.reviewsSignal.asReadonly();
  readonly userReviews = this.userReviewsSignal.asReadonly();

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

  /** Reverts the last swipe interaction on /api/discovery/undo. */
  undoSwipe(): Observable<UndoInteractionApiDto> {
    return this.http.post<UndoInteractionApiDto>('/api/discovery/undo', {});
  }

  /** Searches the track catalog using /api/tracks/search. */
  searchSongs(params: SearchTracksParams = {}): Observable<readonly Song[]> {
    const httpParams = buildSearchHttpParams(params);
    const isUnfiltered =
      !params.query &&
      !params.genre &&
      !params.artist &&
      !params.album &&
      params.year === undefined &&
      params.startYear === undefined &&
      params.endYear === undefined &&
      params.minRating == null &&
      !params.sortBy;
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
      readonly days?: number | null;
      readonly limit?: number;
      readonly sortBy?: ReviewSortOption;
    } = {},
  ): Observable<readonly CommunityReview[]> {
    let params = new HttpParams().set('limit', String(options.limit ?? 20));
    const effectiveDays = options.days === undefined ? 1 : options.days;
    if (effectiveDays != null && Number.isFinite(effectiveDays)) {
      params = params.set('days', String(effectiveDays));
    }
    if (options.sortBy) {
      params = params.set('sort_by', options.sortBy);
    }
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

  /** Loads all-time reviews authored by the authenticated user from /api/reviews/me. */
  loadUserReviews(
    options: {
      readonly trackLookup?: ReadonlyMap<number, Song>;
      readonly currentUserId?: number;
      readonly currentUserName?: string;
      readonly limit?: number;
    } = {},
  ): Observable<readonly CommunityReview[]> {
    const params = new HttpParams().set('limit', String(options.limit ?? 50));
    return this.http.get<readonly ReviewApiDto[]>('/api/reviews/me', { params }).pipe(
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
        this.userReviewsSignal.set(reviews);
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
    readonly sortBy?: ReviewSortOption;
  }): Observable<readonly CommunityReview[]> {
    let params = new HttpParams();
    if (options.sortBy) {
      params = params.set('sort_by', options.sortBy);
    }
    return this.http
      .get<readonly ReviewApiDto[]>(`/api/reviews/track/${options.trackId}`, { params })
      .pipe(
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

  /** Records an explicit user access to a track via POST /api/tracks/{id}/access. */
  recordTrackAccess(
    trackId: number,
    source: TrackAccessSource,
  ): Observable<RecordTrackAccessApiDto> {
    return this.http.post<RecordTrackAccessApiDto>(`/api/tracks/${trackId}/access`, {
      source,
    });
  }

  /** Fetches the authenticated user's active access history and seen track IDs. */
  getUserAccessHistory(limit = 100, offset = 0): Observable<UserAccessHistoryApiDto> {
    const params = new HttpParams().set('limit', String(limit)).set('offset', String(offset));
    return this.http.get<UserAccessHistoryApiDto>('/api/profile/access-history', { params });
  }
}
