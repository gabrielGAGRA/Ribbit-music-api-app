import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { Router } from '@angular/router';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/services/song.service';
import { safeInject } from '../../core/safe-inject';
import { IconComponent } from '../../shared/icon.component';
import { Song } from '@ribbit/shared-types';

@Component({
  selector: 'app-jams',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './jams.component.html',
  styleUrl: './jams.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JamsComponent {
  private readonly router: Router | null = safeInject(Router, null);
  protected readonly songService: SongService = safeInject(SongService, new SongService());

  readonly jamView = signal<'swipe' | 'room'>('swipe');
  readonly jamDeckCursor = signal<number>(0);
  protected readonly jamDrag = signal<number>(0);
  private jamPointerStart: number | null = null;

  readonly currentSong = computed<Song>(() => this.state.currentSong());

  readonly currentJamDeckSong = computed<Song>(() => {
    const list = this.state.songs();
    const cursor = this.jamDeckCursor();
    return list[cursor % list.length];
  });

  readonly upcomingSongs = computed<readonly Song[]>(() => {
    return this.state.songs().slice(1, 5);
  });

  readonly formattedDurationMinutes = computed<string>(() => {
    return String(this.state.jamState().durationMinutes).padStart(2, '0');
  });

  readonly jamSuperlikesCount = computed<number>(
    () => this.state.jamState().superlikesCount || 0,
  );
  readonly jamSuperlikesLimit = computed<number>(
    () => this.state.jamState().superlikesLimit || 5,
  );

  readonly jamCardTransform = computed<string | undefined>(() => {
    const drag = this.jamDrag();
    if (drag === 0) return undefined;
    return `translateX(${drag}px) rotate(${drag / 30}deg)`;
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
  ) {}

  selectJamView(view: 'swipe' | 'room'): void {
    this.jamView.set(view);
  }

  openJamModal(): void {
    this.state.setModal('jam');
  }

  joinJam(code: string): void {
    this.state.setJamActive(true);
    this.jamView.set('swipe');
    this.state.notify(`Você entrou na Jam (${code})! Deslize para pontuar músicas.`);
  }

  onJoinSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const input = form.elements.namedItem('jamCode') as HTMLInputElement;
    this.joinJam(input.value || 'RIBBIT-729');
  }

  copyCode(): void {
    const code = this.state.jamState().code;
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(code);
    }
    this.state.notify(`Código ${code} copiado.`);
  }

  voteSkip(): void {
    this.state.voteSkipJam();
  }

  likeCurrent(): void {
    this.state.decide('like');
  }

  loveTrack(song: Song): void {
    const songIndex = this.state.songs().indexOf(song);
    if (songIndex >= 0) {
      const hist = [
        ...this.state.history().filter((item) => item.index !== songIndex),
        { index: songIndex, kind: 'love' as const },
      ];
      this.state.history.set(hist);
      this.state.notify(`${song.title} foi adicionada às suas favoritas.`);
    }
  }

  decideJamCard(action: 'reject' | 'like' | 'superlike'): void {
    const song = this.currentJamDeckSong();
    const currentJam = this.state.jamState();

    if (action === 'superlike') {
      const currentCount = currentJam.superlikesCount || 0;
      const limit = currentJam.superlikesLimit || 5;
      if (currentCount >= limit) {
        this.state.notify(`Limite de superlikes da sala atingido (${limit}/${limit}).`);
        return;
      }
      this.state.jamState.set({
        ...currentJam,
        superlikesCount: currentCount + 1,
      });
      this.state.notify(`Superlike em "${song.title}"! +2 pontos na fila da Jam.`);
    } else if (action === 'like') {
      this.state.notify(`Like em "${song.title}"! +1 ponto na fila da Jam.`);
    } else {
      this.state.notify(`"${song.title}" pulada.`);
    }

    this.jamDeckCursor.set(this.jamDeckCursor() + 1);
    this.jamDrag.set(0);
  }

  onJamPointerDown(event: PointerEvent): void {
    this.jamPointerStart = event.clientX;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  onJamPointerMove(event: PointerEvent): void {
    if (this.jamPointerStart !== null) {
      this.jamDrag.set(event.clientX - this.jamPointerStart);
    }
  }

  onJamPointerCancel(): void {
    this.jamPointerStart = null;
    this.jamDrag.set(0);
  }

  onJamPointerUp(): void {
    if (this.jamPointerStart === null) return;
    this.jamPointerStart = null;
    const drag = this.jamDrag();
    if (drag > 65) {
      this.decideJamCard('like');
    } else if (drag < -65) {
      this.decideJamCard('reject');
    } else {
      this.jamDrag.set(0);
    }
  }
}
