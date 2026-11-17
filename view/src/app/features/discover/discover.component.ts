import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { DecisionKind, Playlist, Song } from '@ribbit/shared-types';
import { AudioPlayerService } from '../../core/audio-player.service';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlaylistService } from '../../core/services/playlist.service';
import {
  TransformStyleDirective,
  WaveBarStyleDirective,
} from '../../shared/dynamic-style.directive';
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

  readonly selectedTargetPlaylistId = signal<number | null>(null);

  readonly targetPlaylist = computed<Playlist | null>(() => {
    const id = this.selectedTargetPlaylistId();
    if (id === null) return null;
    return this.state.playlists().find((p) => p.playlistId === id) ?? null;
  });

  selectTargetPlaylist(playlistId: number | null): void {
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

  openCreatePlaylist(): void {
    this.state.setModal('playlist');
  }

  getPlaylistCover(playlist: Playlist): string {
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

  onTargetPlaylistChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const val = select.value;
    if (!val) {
      this.selectTargetPlaylist(null);
    } else {
      this.selectTargetPlaylist(Number(val));
    }
  }

  protected readonly availableModes: readonly string[] = [
    'Para você',
    'Por Referência',
    'Fora da bolha',
  ];
  protected readonly waveformBars = Array.from({ length: 65 });

  readonly animation = signal<string>('');
  readonly drag = signal<{ readonly x: number; readonly y: number }>({ x: 0, y: 0 });

  private pointerStart: { readonly x: number; readonly y: number } | null = null;

  readonly currentSong = computed<Song>(() => this.state.currentSong());

  readonly activeDragAction = computed<DecisionKind | null>(() => {
    const { x, y } = this.drag();
    const threshold = 40;
    const absX = Math.abs(x);
    const absY = Math.abs(y);

    if (absX < threshold && y > -threshold) {
      return null;
    }

    if (y < -threshold && absY > absX) {
      return 'love';
    }

    if (absX >= threshold && absX >= absY) {
      return x > 0 ? 'like' : 'reject';
    }

    return null;
  });

  readonly cardTransform = computed<string>(() => {
    const d = this.drag();
    if (d.x === 0 && d.y === 0) return '';
    return `translate(${d.x}px, ${d.y}px) rotate(${d.x / 30}deg)`;
  });

  readonly formattedPreviewTime = computed<string>(() => {
    const sec = Math.round(this.player.progress() * 0.3);
    return String(sec).padStart(2, '0');
  });

  selectMode(mode: string): void {
    this.state.mode.set(mode);
    this.state.loadNextDiscoveryTrack();
    if (!this.state.discoverySong()) {
      if (mode === 'Por Referência') {
        this.state.currentIndex.set(1);
      } else if (mode === 'Fora da bolha') {
        this.state.currentIndex.set(2);
      } else {
        this.state.currentIndex.set(0);
      }
    }
  }

  handleDecision(kind: DecisionKind): void {
    if (this.animation()) return;
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

      this.state.decide(kind);
      this.player.resetProgress();
      this.animation.set('');
      this.drag.set({ x: 0, y: 0 });
    }, 260);
  }

  handleUndo(): void {
    this.state.undo();
    this.player.setProgress(24);
  }

  togglePlay(): void {
    if (this.player.isPlaying()) {
      this.player.pause();
      return;
    }
    const previewUrl = this.currentSong().previewUrl;
    if ((previewUrl ?? null) !== this.player.activePreviewUrl()) {
      this.player.loadTrack(previewUrl);
    }
    this.player.play();
  }

  openFilters(): void {
    this.state.setModal('filters');
  }

  openDetails(): void {
    this.state.setModal('details');
  }

  openAddModal(): void {
    this.state.setModal('add');
  }

  onPointerDown(event: PointerEvent): void {
    const target = event.target as HTMLElement;
    if (target.closest('button')) return;
    this.pointerStart = { x: event.clientX, y: event.clientY };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  onPointerMove(event: PointerEvent): void {
    if (this.pointerStart) {
      this.drag.set({
        x: event.clientX - this.pointerStart.x,
        y: event.clientY - this.pointerStart.y,
      });
    }
  }

  onPointerCancel(): void {
    this.pointerStart = null;
    this.drag.set({ x: 0, y: 0 });
  }

  onPointerUp(): void {
    if (!this.pointerStart) return;
    this.pointerStart = null;
    const action = this.activeDragAction();
    if (action) {
      this.handleDecision(action);
    } else {
      this.drag.set({ x: 0, y: 0 });
    }
  }
}
