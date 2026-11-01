import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlaylistService } from '../../core/services/playlist.service';
import { SongService } from '../../core/services/song.service';
import { safeInject } from '../../core/safe-inject';
import { AudioPlayerService } from '../../core/audio-player.service';
import { IconComponent } from '../../shared/icon.component';
import { Playlist, Song } from '@ribbit/shared-types';

@Component({
  selector: 'app-playlists',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './playlists.component.html',
  styleUrl: './playlists.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlaylistsComponent {
  protected readonly playlistService: PlaylistService = safeInject(PlaylistService, new PlaylistService());
  protected readonly songService: SongService = safeInject(SongService, new SongService());

  protected readonly oceanImg =
    'https://images.unsplash.com/photo-1505142468610-359e7d316be0?auto=format&fit=crop&w=1000&q=85';
  protected readonly palmImg =
    'https://images.unsplash.com/photo-1535392432937-a27c36ec07b5?auto=format&fit=crop&w=700&q=85';

  readonly currentTab = signal<'playlists' | 'queue'>('playlists');
  readonly selectedPlaylist = signal<Playlist | null>(null);
  readonly isExportingSpotify = signal<boolean>(false);

  protected readonly queueDrag = signal<number>(0);
  private queuePointerStart: number | null = null;

  readonly currentQueueSong = computed<Song>(() => {
    const songs = this.state.songs();
    const cursor = this.state.queueCursor();
    return songs[cursor % songs.length];
  });

  readonly lastQueuePreview = computed<readonly number[]>(() => {
    return this.state.lastQueue().slice(0, 3);
  });

  readonly showLastQueueDetails = signal<boolean>(false);

  toggleLastQueueDetails(): void {
    this.showLastQueueDetails.update((v) => !v);
  }

  readonly queueCardTransform = computed<string | undefined>(() => {
    const drag = this.queueDrag();
    if (drag === 0) return undefined;
    return `translateX(${drag}px) rotate(${drag / 30}deg)`;
  });

  readonly selectedPlaylistTracks = computed<readonly Song[]>(() => {
    const p = this.selectedPlaylist();
    if (!p) return [];
    if (p.songs && p.songs.length > 0) return p.songs;
    const all = this.state.songs();
    const count = Math.min(p.count || 4, all.length);
    return all.slice(0, count);
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
    protected readonly player: AudioPlayerService = inject(AudioPlayerService),
  ) {}

  selectTab(tab: 'playlists' | 'queue'): void {
    this.currentTab.set(tab);
    if (tab === 'queue') {
      this.selectedPlaylist.set(null);
    }
  }

  decideQueue(add: boolean): void {
    this.state.decideQueue(add);
    this.queueDrag.set(0);
  }

  getSong(index: number): Song {
    const list = this.state.songs();
    return list[index % list.length];
  }

  playQueue(): void {
    this.player.play();
    this.state.notify('Reproduzindo sua fila temporária.');
  }

  playTrack(song: Song): void {
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
    if (typeof playlistOrName === 'string') {
      const found = this.state.playlists().find((p) => p.name === playlistOrName);
      this.selectedPlaylist.set(
        found || { name: playlistOrName, count: 4, duration: '14 min' },
      );
    } else {
      this.selectedPlaylist.set(playlistOrName);
    }
  }

  closePlaylistView(): void {
    this.selectedPlaylist.set(null);
  }

  exportCurrentToSpotify(): void {
    const p = this.selectedPlaylist();
    if (!p) return;
    this.isExportingSpotify.set(true);
    this.playlistService.exportToSpotify(p.name).subscribe({
      next: (res) => {
        this.isExportingSpotify.set(false);
        this.state.notify(res.message);
      },
      error: () => {
        this.isExportingSpotify.set(false);
        this.state.notify('Erro ao exportar para o Spotify.');
      },
    });
  }

  removeTrackFromCurrent(index: number): void {
    const p = this.selectedPlaylist();
    if (!p) return;
    const playlistIndex = this.state.playlists().findIndex((item) => item.name === p.name);
    if (playlistIndex >= 0) {
      this.state.removeSongFromPlaylist(playlistIndex);
      const updatedList = this.state.playlists();
      this.selectedPlaylist.set(updatedList[playlistIndex] || null);
    }
  }

  deleteCurrentPlaylist(): void {
    const p = this.selectedPlaylist();
    if (!p) return;
    this.state.deletePlaylist(p.name);
    this.selectedPlaylist.set(null);
  }

  onQueuePointerDown(event: PointerEvent): void {
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
