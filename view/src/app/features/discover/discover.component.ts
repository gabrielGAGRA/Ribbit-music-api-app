import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/services/song.service';
import { safeInject } from '../../core/safe-inject';
import { AudioPlayerService } from '../../core/audio-player.service';
import { IconComponent } from '../../shared/icon.component';
import { FrogComponent } from '../../shared/frog.component';
import { DecisionKind, Song } from '@ribbit/shared-types';

@Component({
  selector: 'app-discover',
  standalone: true,
  imports: [IconComponent, FrogComponent],
  templateUrl: './discover.component.html',
  styleUrl: './discover.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DiscoverComponent {
  protected readonly songService: SongService = safeInject(SongService, new SongService());

  protected readonly availableModes: readonly string[] = [
    'Para você',
    'Por Referência',
    'Fora da bolha',
  ];
  protected readonly waveformBars = Array.from({ length: 65 });

  readonly animation = signal<string>('');
  readonly drag = signal<{ x: number; y: number }>({ x: 0, y: 0 });

  private pointerStart: { x: number; y: number } | null = null;

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

  readonly cardTransform = computed<string | undefined>(() => {
    const d = this.drag();
    if (d.x === 0 && d.y === 0) return undefined;
    return `translate(${d.x}px, ${d.y}px) rotate(${d.x / 30}deg)`;
  });

  readonly formattedPreviewTime = computed<string>(() => {
    const sec = Math.round(this.player.progress() * 0.3);
    return String(sec).padStart(2, '0');
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
    protected readonly player: AudioPlayerService = inject(AudioPlayerService),
  ) {}

  selectMode(mode: string): void {
    this.state.mode.set(mode);
    if (mode === 'Por Referência') {
      this.state.currentIndex.set(1);
    } else if (mode === 'Fora da bolha') {
      this.state.currentIndex.set(2);
    } else {
      this.state.currentIndex.set(0);
    }
  }

  handleDecision(kind: DecisionKind): void {
    if (this.animation()) return;
    this.animation.set(kind);
    setTimeout(() => {
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
    this.player.togglePlay();
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
