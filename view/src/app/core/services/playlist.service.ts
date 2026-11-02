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
  Song,
} from '@ribbit/shared-types';
import { mapPlaylistDtoToPlaylist, mapTrackDtoToSong } from '../api-mappers';

/** Manages user playlists, contextual deck generation, and Spotify export via /api/playlists. */
@Injectable({ providedIn: 'root' })
export class PlaylistService {
  private readonly http = inject(HttpClient);
  private readonly playlistsSignal = signal<readonly Playlist[]>([]);

  readonly playlists = this.playlistsSignal.asReadonly();

  /** Lists all playlists owned by the authenticated user. */
  getPlaylists(): Observable<readonly Playlist[]> {
    return this.http.get<readonly PlaylistApiDto[]>('/api/playlists').pipe(
      map((dtos) => dtos.map((dto) => mapPlaylistDtoToPlaylist(dto))),
      tap((list) => {
        this.playlistsSignal.set(list);
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
    return this.http.post<PlaylistApiDto>('/api/playlists/deck', payload).pipe(
      map((dto) => mapPlaylistDtoToPlaylist(dto)),
      tap((created) => {
        this.playlistsSignal.update((current) => [created, ...current]);
      }),
    );
  }

  /** Fetches candidate tracks for swipe-building a playlist. */
  getPlaylistDeck(playlistId: number, limit = 20): Observable<readonly Song[]> {
    const params = new HttpParams().set('limit', String(limit));
    return this.http
      .get<PaginatedTracksApiDto>(`/api/playlists/${playlistId}/deck`, { params })
      .pipe(map((page) => page.items.map((dto) => mapTrackDtoToSong(dto))));
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
    playlistName: string,
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
