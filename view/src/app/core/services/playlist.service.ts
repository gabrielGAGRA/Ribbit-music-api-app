import { Injectable, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay, tap } from 'rxjs/operators';
import { Playlist } from '@ribbit/shared-types';
import { MOCK_PLAYLISTS } from '../mocks/playlists.mock';

@Injectable({ providedIn: 'root' })
export class PlaylistService {
  private readonly playlistsSignal = signal<readonly Playlist[]>(MOCK_PLAYLISTS);

  readonly playlists = this.playlistsSignal.asReadonly();

  getPlaylists(): Observable<readonly Playlist[]> {
    return of(this.playlistsSignal()).pipe(
      delay(100),
      tap((list) => this.playlistsSignal.set(list)),
    );
  }

  addPlaylist(playlist: Playlist): Observable<boolean> {
    const updated = [playlist, ...this.playlistsSignal()];
    this.playlistsSignal.set(updated);
    return of(true).pipe(delay(100));
  }

  exportToSpotify(
    playlistName: string,
  ): Observable<{ success: boolean; message: string; spotifyUrl: string }> {
    return of({
      success: true,
      message: `Playlist "${playlistName}" exportada com sucesso para sua conta do Spotify!`,
      spotifyUrl: `https://open.spotify.com/playlist/${encodeURIComponent(playlistName)}`,
    }).pipe(delay(500));
  }
}
