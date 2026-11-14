import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { Playlist, Song } from '@ribbit/shared-types';
import {
  isSpotifyConnectionRequiredError,
  isSpotifyError,
  toApiError,
} from '../../core/api-error';
import { AudioPlayerService } from '../../core/audio-player.service';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlaylistService } from '../../core/services/playlist.service';
import { TransformStyleDirective } from '../../shared/dynamic-style.directive';
import { IconComponent } from '../../shared/icon.component';

/** Manages user playlists, temporary playback queue, and Spotify playlist export. */
@Component({
  selector: 'app-playlists',
  standalone: true,
  imports: [IconComponent, TransformStyleDirective],
  templateUrl: './playlists.component.html',
  styleUrl: './playlists.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlaylistsComponent {
  protected readonly state = inject(RibbitStateService);
  protected readonly player = inject(AudioPlayerService);
  private readonly playlistService = inject(PlaylistService);

  protected readonly oceanImg =
    'https://images.unsplash.com/photo-1505142468610-359e7d316be0?auto=format&fit=crop&w=1000&q=85';
  protected readonly palmImg =
    'https://images.unsplash.com/photo-1535392432937-a27c36ec07b5?auto=format&fit=crop&w=700&q=85';

  readonly currentTab = signal<'playlists' | 'queue'>('playlists');
  readonly selectedPlaylist = signal<Playlist | null>(null);
  readonly isExportingSpotify = signal<boolean>(false);
  readonly showLastQueueDetails = signal<boolean>(false);

  protected readonly queueDrag = signal<number>(0);
  private queuePointerStart: number | null = null;

  readonly currentQueueSong = computed<Song>(() => {
    const songs = this.state.songs();
    const cursor = this.state.queueCursor();
    return songs[cursor % songs.length] ?? songs[0]!;
  });

  readonly lastQueuePreview = computed<readonly number[]>(() => this.state.lastQueue().slice(0, 3));

  readonly queueCardTransform = computed<string>(() => {
    const drag = this.queueDrag();
    if (drag === 0) return '';
    return `translateX(${drag}px) rotate(${drag / 30}deg)`;
  });

  readonly selectedPlaylistTracks = computed<readonly Song[]>(() => {
    const p = this.selectedPlaylist();
    if (!p) return [];
    return p.songs ?? [];
  });

  toggleLastQueueDetails(): void {
    this.showLastQueueDetails.update((v) => !v);
  }

  selectTab(tab: 'playlists' | 'queue'): void {
    this.currentTab.set(tab);
    if (tab === 'queue') {
      this.selectedPlaylist.set(null);
      this.player.loadTrack(this.currentQueueSong().previewUrl);
    }
  }

  decideQueue(add: boolean): void {
    this.state.decideQueue(add);
    this.queueDrag.set(0);
    this.player.loadTrack(this.currentQueueSong().previewUrl);
  }

  toggleQueueCardPlay(): void {
    const song = this.currentQueueSong();
    if (this.player.activePreviewUrl() !== (song.previewUrl ?? null)) {
      this.player.loadTrack(song.previewUrl);
    }
    this.player.togglePlay();
  }

  getSong(index: number): Song {
    const list = this.state.songs();
    return list[index % list.length] ?? list[0]!;
  }

  playQueue(): void {
    const first =
      this.selectedPlaylistTracks()[0] ?? this.state.queueSongs()[0] ?? this.currentQueueSong();
    this.player.loadTrack(first.previewUrl);
    this.player.play();
    this.state.notify(`Reproduzindo "${first.title}".`);
  }

  playTrack(song: Song): void {
    this.player.loadTrack(song.previewUrl);
    this.player.play();
    this.state.notify(`Tocando "${song.title}" de ${song.artist}.`);
  }

  openCreateModal(): void {
    this.state.setModal('playlist');
  }

  openSaveQueueModal(): void {
    this.state.setModal('save-queue');
  }

  openPlaylistView(playlistOrName: Playlist | string): void {
    const resolved: Playlist =
      typeof playlistOrName === 'string'
        ? (this.state.playlists().find((p) => p.name === playlistOrName) ?? {
            id: playlistOrName,
            name: playlistOrName,
            count: 0,
            duration: '0 min',
            songs: [],
          })
        : playlistOrName;

    this.selectedPlaylist.set(resolved);

    if (resolved.playlistId !== undefined && readAuthToken()) {
      this.playlistService.getPlaylistById(resolved.playlistId).subscribe({
        next: (fresh) => {
          this.selectedPlaylist.set(fresh);
        },
        error: () => {
          // Retain cached playlist snapshot on error
        },
      });
    }
  }

  closePlaylistView(): void {
    this.selectedPlaylist.set(null);
  }

  exportCurrentToSpotify(): void {
    const p = this.selectedPlaylist();
    if (!p) return;

    if (!this.state.isSpotifyLinked()) {
      this.state.promptSpotifyConnection(
        'Conecte sua conta do Spotify nas configurações para exportar suas playlists.',
      );
      return;
    }

    this.isExportingSpotify.set(true);
    if (p.playlistId === undefined || !readAuthToken()) {
      this.state.notify('Vincule uma playlist salva no servidor para exportar ao Spotify.');
      this.isExportingSpotify.set(false);
      return;
    }

    this.playlistService.exportToSpotify(p.playlistId, p.name).subscribe({
      next: (res) => {
        this.isExportingSpotify.set(false);
        this.state.refreshPlaylists();
        this.state.notify(res.message);
      },
      error: (err: unknown) => {
        this.isExportingSpotify.set(false);
        if (
          isSpotifyConnectionRequiredError(err) ||
          (!this.state.isSpotifyLinked() && isSpotifyError(err))
        ) {
          this.state.promptSpotifyConnection(toApiError(err).message);
          return;
        }
        this.state.notify(toApiError(err).message);
      },
    });
  }

  removeTrackFromCurrent(index: number): void {
    const p = this.selectedPlaylist();
    const track = this.selectedPlaylistTracks()[index];
    if (!p || !track) return;

    if (p.playlistId !== undefined && track.trackId !== undefined && readAuthToken()) {
      this.playlistService.removeTrackFromPlaylist(p.playlistId, track.trackId).subscribe({
        next: () => {
          const updatedSongs = (p.songs ?? []).filter((_, idx) => idx !== index);
          const updated: Playlist = {
            ...p,
            count: updatedSongs.length,
            songs: updatedSongs,
          };
          this.selectedPlaylist.set(updated);
          this.state.refreshPlaylists();
          this.state.notify(`"${track.title}" removida de ${p.name}.`);
        },
        error: (err: unknown) => {
          this.state.notify(toApiError(err).message);
        },
      });
    }
  }

  deleteCurrentPlaylist(): void {
    const p = this.selectedPlaylist();
    if (!p) return;
    this.state.deletePlaylist(p);
    this.selectedPlaylist.set(null);
  }

  onQueuePointerDown(event: PointerEvent): void {
    const target = event.target as HTMLElement | null;
    if (target?.closest('button')) return;
    this.queuePointerStart = event.clientX;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  onQueuePointerMove(event: PointerEvent): void {
    if (this.queuePointerStart !== null) {
      this.queueDrag.set(event.clientX - this.queuePointerStart);
    }
  }

  onQueuePointerCancel(): void {
    this.queuePointerStart = null;
    this.queueDrag.set(0);
  }

  onQueuePointerUp(): void {
    if (this.queuePointerStart === null) return;
    this.queuePointerStart = null;
    const drag = this.queueDrag();
    if (drag > 65) {
      this.decideQueue(true);
    } else if (drag < -65) {
      this.decideQueue(false);
    } else {
      this.queueDrag.set(0);
    }
  }
}
