import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import type {
  ActionSuccessApiDto,
  CreateJamApiRequest,
  JamApiDto,
  JamQueueItemApiDto,
  JamStateApiDto,
  PaginatedTracksApiDto,
  SkipVoteApiDto,
  Song,
} from '@ribbit/shared-types';
import { mapTrackDtoToSong } from '../../core/api-mappers';

/** Coordinates collaborative Jam creation, joining, deck voting, and state polling via /api/jams. */
@Injectable({ providedIn: 'root' })
export class JamService {
  private readonly http = inject(HttpClient);

  /** Creates a new collaborative Jam room hosted by the authenticated user. */
  createJam(payload: CreateJamApiRequest): Observable<JamApiDto> {
    return this.http.post<JamApiDto>('/api/jams', payload);
  }

  /** Joins an active Jam room using its shared room code. */
  joinJam(roomCode: string): Observable<JamApiDto> {
    return this.http.post<JamApiDto>('/api/jams/join', {
      room_code: roomCode.trim(),
    });
  }

  /** Fetches the live Jam room state, current track, queue, and skip votes. */
  getJamState(jamId: number): Observable<JamStateApiDto> {
    return this.http.get<JamStateApiDto>(`/api/jams/${jamId}/state`);
  }

  /** Loads candidate tracks for the Jam swipe deck. */
  getJamDeck(jamId: number, limit = 20): Observable<readonly Song[]> {
    const params = new HttpParams().set('limit', String(limit));
    return this.http
      .get<PaginatedTracksApiDto>(`/api/jams/${jamId}/deck`, { params })
      .pipe(map((page) => page.items.map((dto) => mapTrackDtoToSong(dto))));
  }

  /** Votes on a Jam deck track with like (+1) or superlike (+2). */
  voteTrack(options: {
    readonly jamId: number;
    readonly trackId: number;
    readonly action: 'like' | 'superlike';
  }): Observable<JamQueueItemApiDto> {
    const points = options.action === 'superlike' ? 2 : 1;
    return this.http.post<JamQueueItemApiDto>(`/api/jams/${options.jamId}/deck-vote`, {
      track_id: options.trackId,
      action: options.action,
      points,
    });
  }

  /** Registers a democratic skip vote on the currently playing Jam track. */
  voteSkip(jamId: number, trackId?: number): Observable<SkipVoteApiDto> {
    return this.http.post<SkipVoteApiDto>(`/api/jams/${jamId}/skip-vote`, {
      track_id: trackId ?? null,
    });
  }

  /** Saves a track from the Jam queue to the user's liked songs and optional playlist. */
  saveQueueTrack(jamId: number, trackId: number, playlistId?: number): Observable<boolean> {
    return this.http
      .post<ActionSuccessApiDto>(`/api/jams/${jamId}/save-queue-track`, {
        track_id: trackId,
        playlist_id: playlistId ?? null,
      })
      .pipe(map((res) => res.success));
  }

  /** Closes an active Jam room (host only). */
  closeJam(jamId: number): Observable<JamApiDto> {
    return this.http.post<JamApiDto>(`/api/jams/${jamId}/close`, {});
  }
}
