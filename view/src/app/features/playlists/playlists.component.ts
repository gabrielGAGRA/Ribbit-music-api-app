import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import type { Playlist, Song } from '@ribbit/shared-types';
import { isSpotifyConnectionRequiredError, isSpotifyError, toApiError } from '../../core/api-error';
import { mapPlaylistDtoToPlaylist, mapTrackDtoToSong } from '../../core/api-mappers';
import { AudioPlayerService } from '../../core/audio-player.service';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlaylistService } from '../../core/services/playlist.service';
import {
  TransformStyleDirective,
  WaveBarStyleDirective,
} from '../../shared/dynamic-style.directive';
import { IconComponent } from '../../shared/icon.component';

/** Manages user playlists, swipe deck generation for playlists, and Spotify playlist export. */
@Component({
  selector: 'app-playlists',
  standalone: true,
  imports: [IconComponent, TransformStyleDirective, WaveBarStyleDirective],
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

  readonly selectedPlaylist = signal<Playlist | null>(null);
  readonly isExportingSpotify = signal<boolean>(false);
  readonly isUploadingCover = signal<boolean>(false);
  readonly isSwipeMode = signal<boolean>(false);

  protected readonly waveformBars = Array.from({ length: 65 });

  readonly deckCandidates = signal<readonly Song[]>([]);
  readonly deckCursor = signal<number>(0);
  readonly deckLoadedFromBackend = signal<boolean>(false);
  protected readonly fallbackCursor = signal<number>(0);
  protected readonly deckDrag = signal<{ readonly x: number; readonly y: number }>({ x: 0, y: 0 });
  private deckPointerStart: { readonly x: number; readonly y: number } | null = null;

  constructor() {
    let lastReset = this.state.playlistsViewReset();
    effect(() => {
      const currentReset = this.state.playlistsViewReset();
      if (currentReset !== lastReset) {
        lastReset = currentReset;
        this.closePlaylistView();
      }
    });

    effect(() => {
      const list = this.state.playlists();
      for (const pl of list) {
        if (
          pl.playlistId !== undefined &&
          pl.coverImageUrl &&
          !this.isDirectCoverUrl(pl.coverImageUrl)
        ) {
          this.playlistService.loadCoverBlob(pl.playlistId);
        }
      }
    });
  }

  getPlaylistCoverSrc(playlist: Playlist, fallbackIndex = 0): string {
    const pId = playlist.playlistId;
    if (pId !== undefined) {
      const cached = this.playlistService.coverBlobUrls()[pId];
      if (cached) {
        return cached;
      }
    }

    const cover = playlist.coverImageUrl;
    if (cover) {
      if (this.isDirectCoverUrl(cover)) {
        return cover;
      }
      if (pId !== undefined && readAuthToken()) {
        this.playlistService.loadCoverBlob(pId);
      }
    }

    return fallbackIndex % 2 === 0 ? this.oceanImg : this.palmImg;
  }

  private isDirectCoverUrl(url: string): boolean {
    return (
      url.startsWith('http://') ||
      url.startsWith('https://') ||
      url.startsWith('data:') ||
      url.startsWith('blob:')
    );
  }

  readonly currentDeckTrack = computed<Song | null>(() => {
    const list = this.deckCandidates();
    const cursor = this.deckCursor();
    return list[cursor] ?? null;
  });

  readonly activeTrack = computed<Song | null>(() => {
    const fromDeck = this.currentDeckTrack();
    if (fromDeck) return fromDeck;
    if (this.deckLoadedFromBackend()) return null;
    const p = this.selectedPlaylist();
    if (!p) return null;
    const existingKeys = new Set(
      (p.songs ?? []).map((s) => (s.trackId !== undefined ? String(s.trackId) : s.title)),
    );
    const all = this.state.songs();
    const available = all.filter(
      (s) => !existingKeys.has(s.trackId !== undefined ? String(s.trackId) : s.title),
    );
    const pool = available.length > 0 ? available : all;
    if (pool.length > 0) {
      const idx = this.fallbackCursor() % pool.length;
      return pool[idx] ?? pool[0] ?? null;
    }
    return null;
  });

  readonly activeDeckDragAction = computed<'like' | 'dislike' | null>(() => {
    const { x } = this.deckDrag();
    if (x > 40) return 'like';
    if (x < -40) return 'dislike';
    return null;
  });

  readonly deckCardTransform = computed<string>(() => {
    const d = this.deckDrag();
    if (d.x === 0 && d.y === 0) return '';
    return `translate(${d.x}px, ${d.y}px) rotate(${d.x / 30}deg)`;
  });

  readonly formattedPreviewTime = computed<string>(() => {
    const sec = Math.round(this.player.progress() * 0.3);
    return String(sec).padStart(2, '0');
  });

  readonly selectedPlaylistTracks = computed<readonly Song[]>(() => {
    const p = this.selectedPlaylist();
    if (!p) return [];
    return p.songs ?? [];
  });

  toggleSwipeMode(): void {
    this.player.pause();
    if (this.selectedPlaylistTracks().length === 0) {
      this.isSwipeMode.set(true);
      if (this.deckCandidates().length === 0) {
        this.loadPlaylistDeck();
      }
      return;
    }
    const next = !this.isSwipeMode();
    this.isSwipeMode.set(next);
    if (next && this.deckCandidates().length === 0) {
      this.loadPlaylistDeck();
    }
  }

  openPlaylistSwipeDeck(playlist: Playlist): void {
    this.openPlaylistView(playlist);
    this.isSwipeMode.set(true);
    this.loadPlaylistDeck();
  }

  loadPlaylistDeck(): void {
    const p = this.selectedPlaylist();
    if (!p?.playlistId) {
      this.deckLoadedFromBackend.set(false);
      this.deckCandidates.set(this.state.songs());
      this.deckCursor.set(0);
      return;
    }
    this.playlistService.getPlaylistDeck(p.playlistId, 25).subscribe({
      next: (page) => {
        const candidates = page.items.map((dto) => mapTrackDtoToSong(dto));
        this.deckLoadedFromBackend.set(true);
        this.deckCandidates.set(candidates);
        this.deckCursor.set(0);
      },
      error: () => {
        this.deckLoadedFromBackend.set(false);
        this.deckCandidates.set([]);
        this.deckCursor.set(0);
      },
    });
  }

  loadMoreRecommendations(): void {
    const p = this.selectedPlaylist();
    if (p?.playlistId && readAuthToken()) {
      this.loadPlaylistDeck();
      return;
    }
    const existingKeys = new Set(
      (p?.songs ?? []).map((s) => (s.trackId !== undefined ? String(s.trackId) : s.title)),
    );
    const all = this.state.songs();
    const available = all.filter(
      (s) => !existingKeys.has(s.trackId !== undefined ? String(s.trackId) : s.title),
    );
    const pool = available.length > 0 ? available : all;
    if (pool.length > 0) {
      this.deckCandidates.set(pool);
      this.deckCursor.set(0);
    } else {
      this.loadPlaylistDeck();
    }
  }

  onCoverFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    const p = this.selectedPlaylist();
    if (!p || !p.playlistId || !file) return;

    this.isUploadingCover.set(true);
    const previewUrl = URL.createObjectURL(file);
    this.playlistService.setCoverBlobUrl(p.playlistId, previewUrl);
    this.playlistService.uploadPlaylistImage(p.playlistId, file).subscribe({
      next: (updatedDto) => {
        this.isUploadingCover.set(false);
        const mapped = mapPlaylistDtoToPlaylist(updatedDto);
        this.selectedPlaylist.set(mapped);
        this.state.refreshPlaylists();
        this.state.notify('Capa da playlist atualizada com sucesso!');
      },
      error: (err: unknown) => {
        this.isUploadingCover.set(false);
        this.state.notify(toApiError(err).message);
      },
    });
  }

  swipeDeckTrack(action: 'like' | 'dislike'): void {
    const p = this.selectedPlaylist();
    const track = this.activeTrack();
    this.deckDrag.set({ x: 0, y: 0 });
    if (!p || !track) return;

    if (action === 'like') {
      if (p.playlistId !== undefined && track.trackId !== undefined && readAuthToken()) {
        this.playlistService.addTrackToPlaylist(p.playlistId, track.trackId, 'like').subscribe({
          next: () => {
            const currentSongs = p.songs ?? [];
            const exists = currentSongs.some((s) => s.trackId === track.trackId);
            const updatedSongs = exists ? currentSongs : [...currentSongs, track];
            const updated: Playlist = {
              ...p,
              count: updatedSongs.length,
              songs: updatedSongs,
            };
            this.selectedPlaylist.set(updated);
            this.state.refreshPlaylists();
            this.state.notify(`"${track.title}" adicionada a ${p.name}!`);
          },
          error: (err: unknown) => {
            this.state.notify(toApiError(err).message);
          },
        });
      } else {
        const currentSongs = p.songs ?? [];
        const updated: Playlist = {
          ...p,
          count: currentSongs.length + 1,
          songs: [...currentSongs, track],
        };
        this.selectedPlaylist.set(updated);
        this.state.notify(`"${track.title}" adicionada a ${p.name}!`);
      }
    }

    this.deckCursor.update((c) => c + 1);
    this.fallbackCursor.update((c) => c + 1);
    this.player.resetProgress();
  }

  onDeckPointerDown(event: PointerEvent): void {
    const target = event.target as HTMLElement | null;
    if (target?.closest('button')) return;
    this.deckPointerStart = { x: event.clientX, y: event.clientY };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  onDeckPointerMove(event: PointerEvent): void {
    if (this.deckPointerStart) {
      this.deckDrag.set({
        x: event.clientX - this.deckPointerStart.x,
        y: event.clientY - this.deckPointerStart.y,
      });
    }
  }

  onDeckPointerCancel(): void {
    this.deckPointerStart = null;
    this.deckDrag.set({ x: 0, y: 0 });
  }

  onDeckPointerUp(): void {
    if (!this.deckPointerStart) return;
    this.deckPointerStart = null;
    const { x } = this.deckDrag();
    if (x > 65) {
      this.swipeDeckTrack('like');
    } else if (x < -65) {
      this.swipeDeckTrack('dislike');
    } else {
      this.deckDrag.set({ x: 0, y: 0 });
    }
  }

  toggleDeckPlay(song: Song): void {
    if (this.player.isPlaying()) {
      this.player.pause();
      return;
    }
    this.player.loadTrack(song.previewUrl);
    this.player.play();
  }

  openTrackDetails(song: Song): void {
    this.state.selectedDetailsSong.set(song);
    this.state.setModal('details');
  }

  playPlaylist(): void {
    if (this.player.isPlaying()) {
      this.player.pause();
      return;
    }
    const first = this.selectedPlaylistTracks()[0];
    if (first) {
      this.player.loadTrack(first.previewUrl);
      this.player.play();
      this.state.notify(`Reproduzindo "${first.title}".`);
    }
  }

  playQueue(): void {
    this.playPlaylist();
  }

  playTrack(song: Song): void {
    this.player.loadTrack(song.previewUrl);
    this.player.play();
    this.state.notify(`Tocando "${song.title}" de ${song.artist}.`);
  }

  openCreateModal(): void {
    this.state.setModal('playlist');
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

    this.player.pause();
    this.deckLoadedFromBackend.set(false);
    this.selectedPlaylist.set(resolved);
    const hasTracks = (resolved.songs?.length ?? 0) > 0 || resolved.count > 0;
    this.isSwipeMode.set(!hasTracks);
    this.loadPlaylistDeck();

    if (resolved.playlistId !== undefined && readAuthToken()) {
      this.playlistService.getPlaylistById(resolved.playlistId).subscribe({
        next: (fresh) => {
          this.selectedPlaylist.set(fresh);
          const freshHasTracks = (fresh.songs?.length ?? 0) > 0;
          if (!freshHasTracks) {
            this.isSwipeMode.set(true);
            this.loadPlaylistDeck();
          }
        },
        error: () => {
          // Retain cached playlist snapshot on error
        },
      });
    }
  }

  closePlaylistView(): void {
    this.player.pause();
    this.deckLoadedFromBackend.set(false);
    this.selectedPlaylist.set(null);
    this.isSwipeMode.set(false);
  }

  exportPlaylist(playlistId: number, name = 'Playlist', event?: Event): void {
    event?.stopPropagation();
    if (!this.state.isSpotifyLinked()) {
      this.state.promptSpotifyConnection(
        'Conecte sua conta do Spotify nas configurações para exportar suas playlists.',
      );
      return;
    }

    this.isExportingSpotify.set(true);
    if (!readAuthToken()) {
      this.state.notify('Vincule uma playlist salva no servidor para exportar ao Spotify.');
      this.isExportingSpotify.set(false);
      return;
    }

    this.playlistService.exportToSpotify(playlistId, name).subscribe({
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

  exportCurrentToSpotify(): void {
    const p = this.selectedPlaylist();
    if (!p) return;

    if (!this.state.isSpotifyLinked()) {
      this.state.promptSpotifyConnection(
        'Conecte sua conta do Spotify nas configurações para exportar suas playlists.',
      );
      return;
    }

    if (p.playlistId === undefined || !readAuthToken()) {
      this.state.notify('Vincule uma playlist salva no servidor para exportar ao Spotify.');
      this.isExportingSpotify.set(false);
      return;
    }

    this.exportPlaylist(p.playlistId, p.name);
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
}
