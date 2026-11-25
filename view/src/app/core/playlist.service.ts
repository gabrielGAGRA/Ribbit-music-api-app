import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';
import type {
  ActionSuccessApiDto,
  DeckPlaylistApiRequest,
  PaginatedTracksApiDto,
  Playlist,
  PlaylistApiDto,
} from '@ribbit/shared-types';
import { mapPlaylistDtoToPlaylist } from './api-mappers';

/** Manages user playlists, contextual deck generation, and Spotify export via /api/playlists. */
@Injectable({ providedIn: 'root' })
export class PlaylistService {
  private readonly http = inject(HttpClient);
  private readonly playlistsSignal = signal<readonly Playlist[]>([]);
  private readonly coverBlobUrlsSignal = signal<Record<number, string>>({});

  readonly playlists = this.playlistsSignal.asReadonly();
  readonly coverBlobUrls = this.coverBlobUrlsSignal.asReadonly();

  getCoverBlobUrl(playlistId: number): string | null {
    return this.coverBlobUrlsSignal()[playlistId] ?? null;
  }

  setCoverBlobUrl(playlistId: number, url: string): void {
    this.coverBlobUrlsSignal.update((curr) => ({ ...curr, [playlistId]: url }));
  }

  loadCoverBlob(playlistId: number): void {
    if (this.coverBlobUrlsSignal()[playlistId]) return;
    this.getPlaylistImageBlob(playlistId).subscribe({
      next: (blob) => {
        if (blob && blob.size > 0) {
          const objectUrl = URL.createObjectURL(blob);
          this.coverBlobUrlsSignal.update((curr) => ({ ...curr, [playlistId]: objectUrl }));
        }
      },
      error: () => {
        // Keep fallback if unavailable
      },
    });
  }

  /** Lists all playlists owned by the authenticated user. */
  getPlaylists(): Observable<readonly Playlist[]> {
    return this.http.get<readonly PlaylistApiDto[]>('/api/playlists').pipe(
      map((dtos) => dtos.map((dto) => mapPlaylistDtoToPlaylist(dto))),
      tap((list) => {
        this.playlistsSignal.set(list);
        for (const pl of list) {
          if (
            pl.playlistId !== undefined &&
            pl.coverImageUrl &&
            !pl.coverImageUrl.startsWith('http') &&
            !pl.coverImageUrl.startsWith('data:') &&
            !pl.coverImageUrl.startsWith('blob:')
          ) {
            this.loadCoverBlob(pl.playlistId);
          }
        }
      }),
    );
  }

  /** Loads a single playlist with its tracks by numeric ID. */
  getPlaylistById(playlistId: number): Observable<Playlist> {
    return this.http
      .get<PlaylistApiDto>(`/api/playlists/${playlistId}`)
      .pipe(map((dto) => mapPlaylistDtoToPlaylist(dto)));
  }

  /** Creates a new contextual deck playlist on the backend. */
  createDeckPlaylist(payload: DeckPlaylistApiRequest): Observable<Playlist> {
    const refId = payload.reference_playlist_id ?? payload.referencePlaylistId;
    const srcId = payload.source_playlist_id ?? payload.sourcePlaylistId ?? refId;
    const cleanPayload: Record<string, unknown> = { name: payload.name };
    const fields = [
      'duration_minutes',
      'genre',
      'year',
      'artist',
      'country',
      'description',
      'reference_source',
    ] as const;
    for (const field of fields) {
      const val = payload[field];
      if (val !== undefined && val !== null) cleanPayload[field] = val;
    }
    if (srcId != null) cleanPayload['source_playlist_id'] = srcId;

    return this.http.post<PlaylistApiDto>('/api/playlists/deck', cleanPayload).pipe(
      map((dto) => mapPlaylistDtoToPlaylist(dto)),
      tap((created) => {
        this.playlistsSignal.update((current) => [created, ...current]);
      }),
    );
  }

  /** Uploads a custom cover image file for a playlist via PUT /api/playlists/${playlistId}/image. */
  uploadPlaylistImage(playlistId: number, file: File): Observable<PlaylistApiDto> {
    return this.http.put<PlaylistApiDto>(`/api/playlists/${playlistId}/image`, file, {
      headers: { 'Content-Type': file.type || 'image/jpeg' },
    });
  }

  /** Retrieves the binary cover image blob for a playlist via GET /api/playlists/${playlistId}/image. */
  getPlaylistImageBlob(playlistId: number): Observable<Blob> {
    return this.http.get(`/api/playlists/${playlistId}/image`, {
      responseType: 'blob',
    });
  }

  /** Fetches candidate tracks for swipe-building a playlist. */
  getPlaylistDeck(
    playlistId: number,
    limit = 20,
    cursorId?: number,
    phase?: 'primary' | 'additional',
  ): Observable<PaginatedTracksApiDto> {
    let params = new HttpParams().set('limit', String(limit));
    if (cursorId !== undefined && cursorId !== null) {
      params = params.set('cursor_id', String(cursorId));
    }
    if (phase === 'additional') {
      params = params.set('phase', phase);
    }
    return this.http.get<PaginatedTracksApiDto>(`/api/playlists/${playlistId}/deck`, { params });
  }

  /** Adds a track to a playlist via swipe-add without polluting global likes. */
  addTrackToPlaylist(playlistId: number, trackId: number, action = 'like'): Observable<boolean> {
    return this.http
      .post<ActionSuccessApiDto>(`/api/playlists/${playlistId}/swipe-add`, {
        track_id: trackId,
        action,
      })
      .pipe(map((res) => res.success));
  }

  /** Removes a track from an existing playlist. */
  removeTrackFromPlaylist(playlistId: number, trackId: number): Observable<boolean> {
    return this.http
      .delete<ActionSuccessApiDto>(`/api/playlists/${playlistId}/tracks/${trackId}`)
      .pipe(map((res) => res.success));
  }

  /** Deletes a playlist by numeric ID. */
  deletePlaylist(playlistId: number): Observable<boolean> {
    return this.http.delete<ActionSuccessApiDto>(`/api/playlists/${playlistId}`).pipe(
      map((res) => res.success),
      tap((deleted) => {
        if (deleted) {
          this.playlistsSignal.update((list) =>
            list.filter((item) => item.playlistId !== playlistId),
          );
        }
      }),
    );
  }

  /** Exports a Ribbit playlist to the user's linked Spotify account. */
  exportToSpotify(
    playlistId: number,
    playlistName = 'Playlist',
  ): Observable<{
    readonly success: boolean;
    readonly message: string;
    readonly spotifyUrl: string;
  }> {
    return this.http.post<PlaylistApiDto>(`/api/playlists/${playlistId}/export-spotify`, {}).pipe(
      map((dto) => {
        const updated = mapPlaylistDtoToPlaylist(dto);
        this.playlistsSignal.update((list) =>
          list.map((item) => (item.playlistId === playlistId ? updated : item)),
        );
        const externalId = dto.spotify_playlist_id ?? encodeURIComponent(playlistName);
        return {
          success: true,
          message: `Playlist "${playlistName}" exportada com sucesso para sua conta do Spotify!`,
          spotifyUrl: `https://open.spotify.com/playlist/${externalId}`,
        };
      }),
    );
  }
}
