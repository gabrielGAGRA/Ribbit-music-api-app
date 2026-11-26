import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import type { PaginatedTracksApiDto, Playlist, ReferenceSource, Song } from '@ribbit/shared-types';
import { isSpotifyConnectionRequiredError, isSpotifyError, toApiError } from '../../core/api-error';
import {
  computeSongsDurationSeconds,
  extractReferenceSourceFromFilters,
  formatTotalMinutes,
  mapPlaylistDtoToPlaylist,
  mapTrackDtoToSong,
} from '../../core/api-mappers';
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
  private readonly deckPhase = signal<'primary' | 'additional'>('primary');
  protected readonly referenceExhausted = signal<boolean>(false);
  protected readonly additionalReferenceWarning = signal<string | null>(null);
  private readonly fallbackCursor = signal<number>(0);
  private readonly deckDrag = signal<{ readonly x: number; readonly y: number }>({ x: 0, y: 0 });
  protected readonly isDragging = signal<boolean>(false);
  private deckPointerStart: { readonly x: number; readonly y: number } | null = null;
  private deckModifiedDuringSwipe = false;
  private deckNextCursor: number | null = null;

  private readonly referenceSourceLabels: Record<ReferenceSource, string> = {
    curtidas: 'Minhas Curtidas',
    amadas: 'Minhas Amadas (Superlikes)',
    playlists: 'Outras Playlists da Biblioteca',
    livre: 'Descoberta Livre (Catálogo geral)',
  };

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

  private songKey(song: Song): string {
    return song.trackId !== undefined ? String(song.trackId) : song.title;
  }

  private pickFallbackTrack(playlist: Playlist): Song | null {
    const existingKeys = new Set((playlist.songs ?? []).map((s) => this.songKey(s)));
    const all = this.state.songs();
    const available = all.filter((s) => !existingKeys.has(this.songKey(s)));
    const pool = available.length > 0 ? available : all;
    if (pool.length === 0) return null;
    const idx = this.fallbackCursor() % pool.length;
    return pool[idx] ?? pool[0] ?? null;
  }

  protected readonly selectedPlaylistTracks = computed<readonly Song[]>(() => {
    const p = this.selectedPlaylist();
    if (!p) return [];
    return p.songs ?? [];
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

  protected readonly selectedPlaylistDurationSeconds = computed<number>(() => {
    const p = this.selectedPlaylist();
    if (!p) return 0;
    const songs = p.songs ?? [];
    if (songs.length > 0) {
      return computeSongsDurationSeconds(songs);
    }
    return p.totalDurationSeconds ?? 0;
  });

  protected readonly isDurationLimitReached = computed<boolean>(() => {
    const max = this.selectedPlaylist()?.maxDurationSeconds;
    return max != null && max > 0 && this.selectedPlaylistDurationSeconds() >= max;
  });

  protected readonly formattedMaxDuration = computed<string | null>(() =>
    this.formatMaxDuration(this.selectedPlaylist()?.maxDurationSeconds),
  );

  private readonly playlistReferenceConfig = computed<{
    readonly hasSourcePlaylist: boolean;
    readonly referenceSource: ReferenceSource | null;
  }>(() => {
    const p = this.selectedPlaylist();
    if (!p) {
      return { hasSourcePlaylist: false, referenceSource: null };
    }
    const hasSourcePlaylist =
      (p.sourcePlaylistId != null && p.sourcePlaylistId > 0) ||
      (p.referencePlaylistId != null && p.referencePlaylistId > 0);
    const referenceSource = p.referenceSource ?? extractReferenceSourceFromFilters(p.deckFilters);
    return { hasSourcePlaylist, referenceSource };
  });

  protected readonly isSwipeBlocked = computed<boolean>(
    () => this.isDurationLimitReached() || this.referenceExhausted(),
  );

  protected formatMaxDuration(seconds: number | null | undefined): string | null {
    if (seconds == null || seconds <= 0) return null;
    return formatTotalMinutes(seconds);
  }

  protected readonly activeTrack = computed<Song | null>(() => {
    if (this.isSwipeBlocked()) {
      return null;
    }
    const fromDeck = this.currentDeckTrack();
    if (fromDeck) return fromDeck;
    const playlist = this.selectedPlaylist();
    const isServerDeck = Boolean(playlist?.playlistId !== undefined && readAuthToken());
    if (!playlist || this.deckLoadedFromBackend() || this.isLoadingDeck() || isServerDeck) {
      return null;
    }
    return this.pickFallbackTrack(playlist);
  });

  private notifySwipeBlocked(): void {
    this.state.notify(
      this.isDurationLimitReached()
        ? 'Esta playlist já atingiu o limite de duração. Remova uma faixa para continuar.'
        : 'Todas as faixas desta referência já foram exibidas.',
    );
  }

  protected toggleSwipeMode(): void {
    this.player.pause();
    const hasTracks = this.selectedPlaylistTracks().length > 0;
    const next = hasTracks ? !this.isSwipeMode() : true;
    if (next && this.isSwipeBlocked()) {
      if (hasTracks) this.notifySwipeBlocked();
      return;
    }
    this.isSwipeMode.set(next);
    if (!next && this.deckModifiedDuringSwipe) {
      this.deckModifiedDuringSwipe = false;
      this.state.refreshPlaylists();
    }
    if (next && this.deckCandidates().length === 0) {
      this.loadPlaylistDeck();
    }
  }

  private resetDeckSessionState(): void {
    this.deckNextCursor = null;
    this.deckLoadedFromBackend.set(false);
    this.deckPhase.set('primary');
    this.referenceExhausted.set(false);
    this.additionalReferenceWarning.set(null);
    this.deckCandidates.set([]);
    this.deckCursor.set(0);
  }

  private transitionToAdditionalOrBlock(): boolean {
    if (this.isDurationLimitReached()) {
      return false;
    }
    const { hasSourcePlaylist, referenceSource } = this.playlistReferenceConfig();
    if (hasSourcePlaylist && this.deckPhase() === 'primary') {
      if (referenceSource) {
        this.deckPhase.set('additional');
        const label = this.referenceSourceLabels[referenceSource];
        const msg = `Todas as faixas da playlist de referência foram exibidas. Agora usando a referência adicional: ${label}.`;
        this.additionalReferenceWarning.set(msg);
        this.state.notify(msg);
        this.loadPlaylistDeck(undefined, 'additional');
        return true;
      }
      this.referenceExhausted.set(true);
      this.deckNextCursor = null;
      this.isLoadingDeck.set(false);
      this.deckLoadedFromBackend.set(true);
      this.deckCandidates.set([]);
      this.deckCursor.set(0);
      this.state.notify(
        'Todas as faixas da playlist de referência já foram exibidas. Swipe bloqueado.',
      );
      return true;
    }
    if (
      referenceSource === 'curtidas' ||
      referenceSource === 'amadas' ||
      referenceSource === 'playlists'
    ) {
      this.referenceExhausted.set(true);
      this.deckNextCursor = null;
      this.isLoadingDeck.set(false);
      this.deckLoadedFromBackend.set(true);
      this.deckCandidates.set([]);
      this.deckCursor.set(0);
      this.state.notify('Todas as faixas da referência já foram exibidas. Swipe bloqueado.');
      return true;
    }
    return false;
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

  private handleDeckPage(
    page: PaginatedTracksApiDto,
    cursorId: number | undefined,
    phase: 'primary' | 'additional',
  ): void {
    const candidates = page.items.map((dto) => mapTrackDtoToSong(dto));
    if (candidates.length === 0) {
      if (this.transitionToAdditionalOrBlock()) {
        return;
      }
      if (cursorId !== undefined) {
        this.deckNextCursor = null;
        this.loadPlaylistDeck(undefined, phase);
        return;
      }
    }
    this.deckNextCursor = page.has_more ? (page.next_cursor ?? null) : null;
    this.isLoadingDeck.set(false);
    this.deckLoadedFromBackend.set(true);
    this.deckCandidates.set(candidates);
    this.deckCursor.set(0);
    this.preloadUpcomingDeckImages(candidates, 0);
  }

  private loadPlaylistDeck(
    cursorId?: number,
    phase: 'primary' | 'additional' = this.deckPhase(),
  ): void {
    const p = this.selectedPlaylist();
    if (this.isDurationLimitReached()) {
      this.deckNextCursor = null;
      this.isLoadingDeck.set(false);
      this.deckLoadedFromBackend.set(true);
      this.deckCandidates.set([]);
      this.deckCursor.set(0);
      return;
    }
    if (!p?.playlistId || !readAuthToken()) {
      this.deckNextCursor = null;
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
    this.playlistService.getPlaylistDeck(p.playlistId, 25, cursorId, phase).subscribe({
      next: (page) => {
        this.handleDeckPage(page, cursorId, phase);
      },
      error: () => {
        this.deckNextCursor = null;
        this.isLoadingDeck.set(false);
        this.deckLoadedFromBackend.set(true);
        this.deckCandidates.set([]);
        this.deckCursor.set(0);
      },
    });
  }

  protected loadMoreRecommendations(): void {
    if (this.isSwipeBlocked()) {
      return;
    }
    const p = this.selectedPlaylist();
    if (p?.playlistId && readAuthToken()) {
      this.loadPlaylistDeck(this.deckNextCursor ?? undefined, this.deckPhase());
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

  private persistLikedDeckTrack(playlist: Playlist, track: Song): void {
    this.selectedPlaylist.update((current) => {
      if (!current) return current;
      const currentSongs = current.songs ?? [];
      const exists =
        track.trackId !== undefined && currentSongs.some((s) => s.trackId === track.trackId);
      const updatedSongs = exists ? currentSongs : [...currentSongs, track];
      const totalDurationSeconds = computeSongsDurationSeconds(updatedSongs);
      return {
        ...current,
        count: updatedSongs.length,
        duration: formatTotalMinutes(totalDurationSeconds),
        totalDurationSeconds,
        songs: updatedSongs,
      };
    });
    this.state.notify(`"${track.title}" adicionada a ${playlist.name}!`);

    const playlistId = playlist.playlistId;
    if (playlistId === undefined || track.trackId === undefined || !readAuthToken()) {
      return;
    }
    this.deckModifiedDuringSwipe = true;
    this.playlistService.addTrackToPlaylist(playlistId, track.trackId, 'like').subscribe({
      error: (err: unknown) => {
        this.syncPlaylistAfterAddError(playlistId, err);
      },
    });
  }

  private syncPlaylistAfterAddError(playlistId: number, err: unknown): void {
    this.state.notify(toApiError(err).message);
    this.state.refreshPlaylists();
    this.playlistService.getPlaylistById(playlistId).subscribe({
      next: (fresh) => {
        if (this.selectedPlaylist()?.playlistId === playlistId) {
          this.selectedPlaylist.set(fresh);
        }
      },
      error: () => undefined,
    });
  }

  private advanceAfterDeckSwipe(playlist: Playlist, nextCursor: number): void {
    if (this.isDurationLimitReached()) {
      this.player.pause();
      this.state.notify(
        'Limite de duração da playlist atingido. Swipe bloqueado até remover uma faixa.',
      );
      return;
    }

    if (nextCursor >= this.deckCandidates().length) {
      if (this.deckNextCursor !== null && playlist.playlistId !== undefined && readAuthToken()) {
        this.loadPlaylistDeck(this.deckNextCursor, this.deckPhase());
        return;
      }
      if (this.transitionToAdditionalOrBlock()) {
        return;
      }
    }

    this.preloadUpcomingDeckImages(this.deckCandidates(), nextCursor);
    const nextTrack = this.activeTrack();
    if (nextTrack) {
      this.player.loadTrack(nextTrack.previewUrl);
      this.player.play();
    }
  }

  protected swipeDeckTrack(action: 'like' | 'dislike'): void {
    const p = this.selectedPlaylist();
    const track = this.activeTrack();
    this.isDragging.set(false);
    this.deckDrag.set({ x: 0, y: 0 });
    this.player.unlock();
    this.player.pause();
    if (!p || !track || this.isSwipeBlocked()) return;

    if (action === 'like') {
      this.persistLikedDeckTrack(p, track);
    }

    const nextCursor = this.deckCursor() + 1;
    this.deckCursor.set(nextCursor);
    this.fallbackCursor.update((c) => c + 1);
    this.advanceAfterDeckSwipe(p, nextCursor);
  }

  protected startDeckCardDrag(event: PointerEvent): void {
    if (this.isSwipeBlocked()) return;
    if (event.isPrimary === false) return;
    if (event.target instanceof Element && event.target.closest('button')) return;
    if (event.cancelable) {
      event.preventDefault();
    }
    this.player.unlock();
    this.deckPointerStart = { x: event.clientX, y: event.clientY };
    this.isDragging.set(true);
    if (event.currentTarget instanceof HTMLElement) {
      try {
        event.currentTarget.setPointerCapture(event.pointerId);
      } catch {
        // Synthetic or detached pointer events may reject pointer capture
      }
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

  protected finishDeckCardDrag(event?: PointerEvent): void {
    if (!this.deckPointerStart || event?.isPrimary === false) return;
    this.syncFinalDeckDrag(this.deckPointerStart, event);
    this.deckPointerStart = null;
    this.isDragging.set(false);
    this.player.unlock();
    const { x } = this.deckDrag();
    if (x > 65) {
      this.swipeDeckTrack('like');
    } else if (x < -65) {
      this.swipeDeckTrack('dislike');
    } else {
      this.deckDrag.set({ x: 0, y: 0 });
    }
  }

  protected preventNativeDrag(event: Event): void {
    event.preventDefault();
  }

  private syncFinalDeckDrag(start: { x: number; y: number }, event?: PointerEvent): void {
    if (
      event &&
      (event.isTrusted || event.clientX !== 0 || event.clientY !== 0) &&
      Number.isFinite(event.clientX) &&
      Number.isFinite(event.clientY)
    ) {
      this.deckDrag.set({
        x: event.clientX - start.x,
        y: event.clientY - start.y,
      });
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
    this.resetDeckSessionState();
    this.selectedPlaylist.set(resolved);
    const hasTracks = (resolved.songs?.length ?? 0) > 0 || resolved.count > 0;
    this.isSwipeMode.set(!hasTracks && !this.isDurationLimitReached());
    if (!this.isDurationLimitReached()) {
      this.loadPlaylistDeck();
    } else {
      this.deckLoadedFromBackend.set(true);
    }

    if (resolved.playlistId !== undefined && readAuthToken()) {
      this.playlistService.getPlaylistById(resolved.playlistId).subscribe({
        next: (fresh) => {
          if (this.selectedPlaylist()?.playlistId !== resolved.playlistId) return;
          this.selectedPlaylist.set(fresh);
          const freshHasTracks = (fresh.songs?.length ?? 0) > 0;
          if (this.isDurationLimitReached()) {
            this.player.pause();
            this.deckCandidates.set([]);
            this.deckLoadedFromBackend.set(true);
          } else if (!freshHasTracks) {
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
    this.resetDeckSessionState();
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
          const totalDurationSeconds = computeSongsDurationSeconds(updatedSongs);
          const updated: Playlist = {
            ...p,
            count: updatedSongs.length,
            duration: formatTotalMinutes(totalDurationSeconds),
            totalDurationSeconds,
            songs: updatedSongs,
          };
          this.selectedPlaylist.set(updated);
          this.referenceExhausted.set(false);
          if (!this.isDurationLimitReached()) {
            this.deckPhase.set('primary');
            this.additionalReferenceWarning.set(null);
            this.deckNextCursor = null;
            this.deckCandidates.set([]);
            this.deckCursor.set(0);
            if (this.isSwipeMode() || updatedSongs.length === 0) {
              this.loadPlaylistDeck();
            }
          }
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
