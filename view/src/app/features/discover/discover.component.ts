import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { DecisionKind, Playlist, Song } from '@ribbit/shared-types';
import { AudioPlayerService } from '../../core/audio-player.service';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlaylistService } from '../../core/playlist.service';
import { TransformStyleDirective } from '../../shared/transform-style.directive';
import { WaveBarStyleDirective } from '../../shared/wave-bar-style.directive';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';

/** Primary Tinder-style musical discovery deck backed by /api/discovery. */
@Component({
  selector: 'app-discover',
  standalone: true,
  imports: [IconComponent, FrogComponent, TransformStyleDirective, WaveBarStyleDirective],
  templateUrl: './discover.component.html',
  styleUrl: './discover.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DiscoverComponent {
  protected readonly state = inject(RibbitStateService);
  protected readonly player = inject(AudioPlayerService);
  private readonly playlistService = inject(PlaylistService);
  private readonly router = inject(Router, { optional: true });

  protected readonly selectedTargetPlaylistId = signal<number | null>(null);

  protected readonly targetPlaylist = computed<Playlist | null>(() => {
    const id = this.selectedTargetPlaylistId();
    if (id === null) return null;
    return this.state.playlists().find((p) => p.playlistId === id) ?? null;
  });

  protected selectTargetPlaylist(playlistId: number | null): void {
    this.selectedTargetPlaylistId.set(playlistId);
    if (playlistId !== null) {
      const pl = this.state.playlists().find((p) => p.playlistId === playlistId);
      if (pl) {
        this.state.notify(`Swipes configurados para a playlist "${pl.name}"`);
      }
    } else {
      this.state.notify('Swipes configurados para Meu Perfil (Geral)');
    }
  }

  protected openCreatePlaylist(): void {
    this.state.setModal('playlist');
  }

  protected getPlaylistCover(playlist: Playlist): string {
    const pId = playlist.playlistId;
    if (pId !== undefined) {
      const cached = this.playlistService.coverBlobUrls()[pId];
      if (cached) return cached;
      if (
        playlist.coverImageUrl &&
        !playlist.coverImageUrl.startsWith('http') &&
        !playlist.coverImageUrl.startsWith('data:') &&
        !playlist.coverImageUrl.startsWith('blob:')
      ) {
        this.playlistService.loadCoverBlob(pId);
      }
    }
    return (
      playlist.coverImageUrl ??
      'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=400&q=80'
    );
  }

  protected readonly waveformBars = Array.from({ length: 65 });

  protected readonly animation = signal<string>('');
  private readonly drag = signal<{ readonly x: number; readonly y: number }>({ x: 0, y: 0 });
  protected readonly isDragging = signal<boolean>(false);

  private pointerStart: { readonly x: number; readonly y: number } | null = null;

  protected readonly currentSong = computed<Song>(() => this.state.currentSong());

  protected readonly activeDragAction = computed<DecisionKind | null>(() => {
    const { x, y } = this.drag();
    const threshold = 40;
    const absX = Math.abs(x);
    const absY = Math.abs(y);

    if (absX < threshold && y > -threshold) {
      return null;
    }

    if (y <= -threshold && absY > absX) {
      return 'love';
    }

    if (absX >= threshold && absX >= absY) {
      return x > 0 ? 'like' : 'reject';
    }

    return null;
  });

  protected readonly cardTransform = computed<string>(() => {
    const d = this.drag();
    if (d.x === 0 && d.y === 0) return '';
    return `translate(${d.x}px, ${d.y}px) rotate(${d.x / 30}deg)`;
  });

  protected readonly formattedPreviewTime = computed<string>(() => {
    const sec = Math.round(this.player.progress() * 0.3);
    return String(sec).padStart(2, '0');
  });

  protected submitDecision(kind: DecisionKind): void {
    if (this.animation()) return;
    this.player.unlock();
    this.player.pause();
    this.animation.set(kind);
    const target = this.targetPlaylist();
    const song = this.currentSong();

    setTimeout(() => {
      if ((kind === 'like' || kind === 'love') && target && target.playlistId && song.trackId) {
        this.playlistService.addTrackToPlaylist(target.playlistId, song.trackId, kind).subscribe({
          next: () => {
            this.state.refreshPlaylists();
            this.state.notify(`"${song.title}" adicionada à playlist "${target.name}"!`);
          },
          error: () => {
            // Notification handled or fallback
          },
        });
      }

      const communityReturnSong = this.state.consumeCommunityReturnSong(song);
      this.state.decide(kind, communityReturnSong === null);
      this.animation.set('');
      this.drag.set({ x: 0, y: 0 });
      if (communityReturnSong !== null) {
        this.state.setPage('explore');
        void this.router?.navigate(['/explore']).catch(() => false);
        this.state.openTrackDetailsModal(communityReturnSong);
      }
    }, 260);
  }

  protected undoLastDecision(): void {
    this.state.undo();
  }

  protected togglePlay(): void {
    if (this.player.isPlaying()) {
      this.player.pause();
      return;
    }
    const song = this.currentSong();
    this.state.recordTrackAccess(song, 'play');
    const previewUrl = song.previewUrl;
    if ((previewUrl ?? null) !== this.player.activePreviewUrl()) {
      this.player.loadTrack(previewUrl);
    }
    this.player.play();
  }

  protected openDetails(): void {
    this.state.setModal('details');
  }

  protected openAddModal(): void {
    this.state.setModal('add');
  }

  protected startCardDrag(event: PointerEvent): void {
    if (event.isPrimary === false) return;
    if (event.target instanceof Element && event.target.closest('button')) return;
    if (event.cancelable) {
      event.preventDefault();
    }
    this.player.unlock();
    this.pointerStart = { x: event.clientX, y: event.clientY };
    this.isDragging.set(true);
    if (event.currentTarget instanceof HTMLElement) {
      try {
        event.currentTarget.setPointerCapture(event.pointerId);
      } catch {
        // Synthetic or detached pointer events may reject pointer capture
      }
    }
  }

  protected moveCardDrag(event: PointerEvent): void {
    if (event.isPrimary === false) return;
    if (this.pointerStart) {
      this.drag.set({
        x: event.clientX - this.pointerStart.x,
        y: event.clientY - this.pointerStart.y,
      });
    }
  }

  protected cancelCardDrag(): void {
    this.pointerStart = null;
    this.isDragging.set(false);
    this.drag.set({ x: 0, y: 0 });
  }

  protected finishCardDrag(event?: PointerEvent): void {
    if (!this.pointerStart || event?.isPrimary === false) return;
    this.syncFinalDrag(this.pointerStart, event);
    this.pointerStart = null;
    this.isDragging.set(false);
    this.player.unlock();
    const action = this.activeDragAction();
    if (action) {
      this.submitDecision(action);
    } else {
      this.drag.set({ x: 0, y: 0 });
    }
  }

  protected preventNativeDrag(event: Event): void {
    event.preventDefault();
  }

  private syncFinalDrag(start: { x: number; y: number }, event?: PointerEvent): void {
    if (
      event &&
      (event.isTrusted || event.clientX !== 0 || event.clientY !== 0) &&
      Number.isFinite(event.clientX) &&
      Number.isFinite(event.clientY)
    ) {
      this.drag.set({
        x: event.clientX - start.x,
        y: event.clientY - start.y,
      });
    }
  }
}
