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
import { PlaylistService } from '../../core/playlist.service';
import { readFirstSelectedFile } from '../../shared/dom-event-values';
import { TransformStyleDirective } from '../../shared/transform-style.directive';
import { WaveBarStyleDirective } from '../../shared/wave-bar-style.directive';
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

  private readonly oceanImg =
    'https://images.unsplash.com/photo-1505142468610-359e7d316be0?auto=format&fit=crop&w=1000&q=85';
  private readonly palmImg =
    'https://images.unsplash.com/photo-1535392432937-a27c36ec07b5?auto=format&fit=crop&w=700&q=85';

  protected readonly selectedPlaylist = signal<Playlist | null>(null);
  protected readonly isExportingSpotify = signal<boolean>(false);
  protected readonly isUploadingCover = signal<boolean>(false);
  protected readonly isSwipeMode = signal<boolean>(false);

  protected readonly waveformBars = Array.from({ length: 65 });

  private readonly deckCandidates = signal<readonly Song[]>([]);
  private readonly deckCursor = signal<number>(0);
  private readonly deckLoadedFromBackend = signal<boolean>(false);
  protected readonly isLoadingDeck = signal<boolean>(false);
  private readonly fallbackCursor = signal<number>(0);
  private readonly deckDrag = signal<{ readonly x: number; readonly y: number }>({ x: 0, y: 0 });
  protected readonly isDragging = signal<boolean>(false);
  private deckPointerStart: { readonly x: number; readonly y: number } | null = null;
  private deckModifiedDuringSwipe = false;

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

  protected getPlaylistCoverSrc(playlist: Playlist, fallbackIndex = 0): string {
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

  private readonly currentDeckTrack = computed<Song | null>(() => {
    const list = this.deckCandidates();
    const cursor = this.deckCursor();
    return list[cursor] ?? null;
  });

  protected readonly activeTrack = computed<Song | null>(() => {
    const fromDeck = this.currentDeckTrack();
    if (fromDeck) return fromDeck;
    const p = this.selectedPlaylist();
    if (!p) return null;
    if (this.deckLoadedFromBackend() || this.isLoadingDeck() || (p.playlistId !== undefined && readAuthToken())) {
      return null;
    }
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

  protected readonly activeDeckDragAction = computed<'like' | 'dislike' | null>(() => {
    const { x } = this.deckDrag();
    if (x > 40) return 'like';
    if (x < -40) return 'dislike';
    return null;
  });

  protected readonly deckCardTransform = computed<string>(() => {
    const d = this.deckDrag();
    if (d.x === 0 && d.y === 0) return '';
    return `translate(${d.x}px, ${d.y}px) rotate(${d.x / 30}deg)`;
  });

  protected readonly formattedPreviewTime = computed<string>(() => {
    const sec = Math.round(this.player.progress() * 0.3);
    return String(sec).padStart(2, '0');
  });

  protected readonly selectedPlaylistTracks = computed<readonly Song[]>(() => {
    const p = this.selectedPlaylist();
    if (!p) return [];
    return p.songs ?? [];
  });

  protected toggleSwipeMode(): void {
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
    if (!next && this.deckModifiedDuringSwipe) {
      this.deckModifiedDuringSwipe = false;
      this.state.refreshPlaylists();
    }
    if (next && this.deckCandidates().length === 0) {
      this.loadPlaylistDeck();
    }
  }

  private preloadUpcomingDeckImages(candidates: readonly Song[], startIndex: number): void {
    if (typeof Image === 'undefined') return;
    for (let i = startIndex; i < Math.min(startIndex + 3, candidates.length); i++) {
      const url = candidates[i]?.image;
      if (url) {
        const img = new Image();
        img.src = url;
      }
    }
  }

  private loadPlaylistDeck(): void {
    const p = this.selectedPlaylist();
    if (!p?.playlistId || !readAuthToken()) {
      this.isLoadingDeck.set(false);
      this.deckLoadedFromBackend.set(false);
      this.deckCandidates.set(this.state.songs());
      this.deckCursor.set(0);
      this.preloadUpcomingDeckImages(this.state.songs(), 0);
      return;
    }
    this.isLoadingDeck.set(true);
    this.deckCandidates.set([]);
    this.deckCursor.set(0);
    this.playlistService.getPlaylistDeck(p.playlistId, 25).subscribe({
      next: (page) => {
        const candidates = page.items.map((dto) => mapTrackDtoToSong(dto));
        this.isLoadingDeck.set(false);
        this.deckLoadedFromBackend.set(true);
        this.deckCandidates.set(candidates);
        this.deckCursor.set(0);
        this.preloadUpcomingDeckImages(candidates, 0);
      },
      error: () => {
        this.isLoadingDeck.set(false);
        this.deckLoadedFromBackend.set(true);
        this.deckCandidates.set([]);
        this.deckCursor.set(0);
      },
    });
  }

  protected loadMoreRecommendations(): void {
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

  protected uploadPlaylistCover(event: Event): void {
    const file = readFirstSelectedFile(event);
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

  protected swipeDeckTrack(action: 'like' | 'dislike'): void {
    const p = this.selectedPlaylist();
    const track = this.activeTrack();
    this.isDragging.set(false);
    this.deckDrag.set({ x: 0, y: 0 });
    this.player.pause();
    if (!p || !track) return;

    if (action === 'like') {
      this.selectedPlaylist.update((current) => {
        if (!current) return current;
        const currentSongs = current.songs ?? [];
        const exists =
          track.trackId !== undefined && currentSongs.some((s) => s.trackId === track.trackId);
        const updatedSongs = exists ? currentSongs : [...currentSongs, track];
        return {
          ...current,
          count: updatedSongs.length,
          songs: updatedSongs,
        };
      });
      this.state.notify(`"${track.title}" adicionada a ${p.name}!`);

      if (p.playlistId !== undefined && track.trackId !== undefined && readAuthToken()) {
        this.deckModifiedDuringSwipe = true;
        this.playlistService.addTrackToPlaylist(p.playlistId, track.trackId, 'like').subscribe({
          error: (err: unknown) => {
            this.state.notify(toApiError(err).message);
            this.state.refreshPlaylists();
          },
        });
      }
    }

    const nextCursor = this.deckCursor() + 1;
    this.deckCursor.set(nextCursor);
    this.fallbackCursor.update((c) => c + 1);
    this.preloadUpcomingDeckImages(this.deckCandidates(), nextCursor);
  }

  protected startDeckCardDrag(event: PointerEvent): void {
    if (event.target instanceof HTMLElement && event.target.closest('button')) return;
    this.deckPointerStart = { x: event.clientX, y: event.clientY };
    this.isDragging.set(true);
    if (event.currentTarget instanceof HTMLElement) {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  }

  protected moveDeckCardDrag(event: PointerEvent): void {
    if (this.deckPointerStart) {
      this.deckDrag.set({
        x: event.clientX - this.deckPointerStart.x,
        y: event.clientY - this.deckPointerStart.y,
      });
    }
  }

  protected cancelDeckCardDrag(): void {
    this.deckPointerStart = null;
    this.isDragging.set(false);
    this.deckDrag.set({ x: 0, y: 0 });
  }

  protected finishDeckCardDrag(): void {
    if (!this.deckPointerStart) return;
    this.deckPointerStart = null;
    this.isDragging.set(false);
    const { x } = this.deckDrag();
    if (x > 65) {
      this.swipeDeckTrack('like');
    } else if (x < -65) {
      this.swipeDeckTrack('dislike');
    } else {
      this.deckDrag.set({ x: 0, y: 0 });
    }
  }

  protected toggleDeckPlay(song: Song): void {
    if (this.player.isPlaying()) {
      this.player.pause();
      return;
    }
    this.state.recordTrackAccess(song, 'playlist');
    this.player.loadTrack(song.previewUrl);
    this.player.play();
  }

  protected openTrackDetails(song: Song): void {
    this.state.selectedDetailsSong.set(song);
    this.state.setModal('details');
  }

  protected openCreateModal(): void {
    this.state.setModal('playlist');
  }

  protected openPlaylistView(playlistOrName: Playlist | string): void {
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
          }
        },
        error: () => {
          // Retain cached playlist snapshot on error
        },
      });
    }
  }

  protected closePlaylistView(): void {
    this.player.pause();
    if (this.deckModifiedDuringSwipe) {
      this.deckModifiedDuringSwipe = false;
      this.state.refreshPlaylists();
    }
    this.deckLoadedFromBackend.set(false);
    this.selectedPlaylist.set(null);
    this.isSwipeMode.set(false);
  }

  private exportPlaylist(playlistId: number, name = 'Playlist', event?: Event): void {
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

  protected exportCurrentToSpotify(): void {
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

  protected removeTrackFromCurrent(index: number): void {
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

  protected deleteCurrentPlaylist(): void {
    const p = this.selectedPlaylist();
    if (!p) return;
    this.state.deletePlaylist(p);
    this.selectedPlaylist.set(null);
  }
}
