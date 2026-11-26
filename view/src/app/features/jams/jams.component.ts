import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { JamQueueTrack, Song } from '@ribbit/shared-types';
import { computeSongsDurationSeconds, resolveSongDurationSeconds } from '../../core/api-mappers';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { TransformStyleDirective } from '../../shared/transform-style.directive';
import { WidthPercentDirective } from '../../shared/width-percent.directive';
import { IconComponent } from '../../shared/icon.component';

/** Collaborative Jam workspace supporting room joining, deck voting, skip consensus, and queue saving. */
@Component({
  selector: 'app-jams',
  standalone: true,
  imports: [IconComponent, TransformStyleDirective, WidthPercentDirective],
  templateUrl: './jams.component.html',
  styleUrl: './jams.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JamsComponent {
  protected readonly state = inject(RibbitStateService);

  protected readonly jamView = signal<'swipe' | 'room'>('swipe');
  readonly jamDeckCursor = this.state.jamDeckCursor;
  protected readonly jamDrag = signal<{ x: number; y: number }>({ x: 0, y: 0 });
  protected readonly isDraggingJam = signal(false);
  private jamPointerStart: { x: number; y: number } | null = null;

  protected readonly currentSong = computed<Song>(
    () => this.state.jamState().currentTrack ?? this.state.currentSong(),
  );

  readonly currentJamDeckSong = this.state.currentJamDeckSong;

  protected readonly upcomingQueueItems = computed<readonly JamQueueTrack[]>(() => {
    const liveQueue = this.state.jamState().queueItems ?? [];
    if (liveQueue.length > 0 || this.state.jamState().jamId !== undefined) {
      return liveQueue;
    }
    return this.state
      .songs()
      .slice(1, 5)
      .map((song, idx) => ({ song, votePoints: 4 - idx }));
  });

  protected readonly formattedDurationMinutes = computed<string>(() =>
    String(this.state.jamState().durationMinutes).padStart(2, '0'),
  );

  private readonly jamTotalAccumulatedSeconds = computed<number>(() => {
    const jam = this.state.jamState();
    const baseSeconds = Math.max(0, (jam.accumulatedMinutes || 0) * 60);
    const currentSeconds = jam.currentTrack ? resolveSongDurationSeconds(jam.currentTrack) : 0;
    const queueSongs = (jam.queueItems ?? []).map((item) => item.song);
    return baseSeconds + currentSeconds + computeSongsDurationSeconds(queueSongs);
  });

  protected readonly jamAccumulatedMinutes = computed<number>(() => {
    const totalSeconds = this.jamTotalAccumulatedSeconds();
    if (totalSeconds <= 0) return 0;
    return Math.max(1, Math.round(totalSeconds / 60));
  });

  protected readonly jamDurationProgressPercent = computed<number>(() => {
    const jam = this.state.jamState();
    const totalMinutes = jam.durationHours * 60 + jam.durationMinutes;
    if (totalMinutes <= 0) return 0;
    const totalDurationSeconds = totalMinutes * 60;
    const accumulatedSeconds = this.jamTotalAccumulatedSeconds();
    if (accumulatedSeconds <= 0) return 0;
    return Math.min(
      100,
      Math.max(1, Math.round((accumulatedSeconds / totalDurationSeconds) * 100)),
    );
  });

  protected readonly jamSuperlikesCount = computed<number>(
    () => this.state.jamState().superlikesCount || 0,
  );
  protected readonly jamSuperlikesLimit = computed<number>(
    () => this.state.jamState().superlikesLimit || 5,
  );

  protected readonly activeJamDragAction = computed<'reject' | 'like' | 'superlike' | null>(() => {
    const { x, y } = this.jamDrag();
    const threshold = 40;
    const absX = Math.abs(x);
    const absY = Math.abs(y);

    if (absX < threshold && y > -threshold) {
      return null;
    }

    if (y <= -threshold && absY > absX) {
      return 'superlike';
    }

    if (absX >= threshold && absX >= absY) {
      return x > 0 ? 'like' : 'reject';
    }

    return null;
  });

  protected readonly jamCardTransform = computed<string>(() => {
    const { x, y } = this.jamDrag();
    if (x === 0 && y === 0) return '';
    return `translate(${x}px, ${y}px) rotate(${x / 30}deg)`;
  });

  protected selectJamView(view: 'swipe' | 'room'): void {
    this.jamView.set(view);
  }

  protected openJamModal(): void {
    if (!this.state.isSpotifyLinked()) {
      this.state.promptSpotifyConnection(
        'Conecte sua conta do Spotify para criar uma Jam no Pond.',
      );
      return;
    }
    if (!this.state.spotifyPremium()) {
      this.state.notify('Uma conta Spotify Premium é necessária para criar uma Jam no Pond.');
      this.state.showRibbyAlert({
        title: 'Spotify Premium necessário',
        message: 'O recurso de reprodução colaborativa no Pond exige uma conta Spotify Premium.',
        tone: 'plan',
        mood: 'talk',
      });
      return;
    }
    this.state.setModal('jam');
  }

  private joinJam(code: string): void {
    const cleaned = code.trim();
    if (!cleaned) return;
    if (!this.state.isSpotifyLinked()) {
      this.state.promptSpotifyConnection(
        'Conecte sua conta do Spotify para entrar na Jam no Pond.',
      );
      return;
    }
    if (!this.state.spotifyPremium()) {
      this.state.notify('Uma conta Spotify Premium é necessária para entrar na Jam no Pond.');
      this.state.showRibbyAlert({
        title: 'Spotify Premium necessário',
        message: 'O recurso de reprodução colaborativa no Pond exige uma conta Spotify Premium.',
        tone: 'plan',
        mood: 'talk',
      });
      return;
    }
    this.jamView.set('swipe');
    if (readAuthToken()) {
      this.state.joinJamRoom(cleaned);
      return;
    }
    this.state.jamState.update((cur) => ({ ...cur, active: true, code: cleaned, roomId: 999 }));
    this.state.notify(`Você entrou na Jam (${cleaned})! Deslize para pontuar músicas.`);
  }

  protected submitJoinRoom(event: Event): void {
    event.preventDefault();
    if (!(event.target instanceof HTMLFormElement)) return;
    const input = event.target.elements.namedItem('jamCode');
    this.joinJam(input instanceof HTMLInputElement && input.value ? input.value : 'RIBBIT-729');
  }

  protected copyCode(): void {
    const code = this.state.jamState().code;
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      void navigator.clipboard.writeText(code);
    }
    this.state.notify(`Código ${code} copiado.`);
  }

  protected voteSkip(): void {
    this.state.voteSkipJam();
  }

  protected advanceJam(): void {
    this.state.advanceJam();
  }

  private fetchMoreJamDeck(): void {
    const jamId = this.state.jamState().jamId;
    const nextCursor = this.state.jamDeckNextCursor();
    if (jamId && nextCursor !== null && !this.state.jamDeckLoading()) {
      this.state.loadJamDeck(jamId, nextCursor, true);
    }
  }

  protected likeCurrent(): void {
    this.state.saveJamQueueSong(this.currentSong());
  }

  protected loveTrack(song: Song): void {
    if (this.state.jamState().jamId !== undefined) {
      this.state.saveJamQueueSong(song);
      return;
    }
    this.state.notify(`${song.title} foi adicionada às suas favoritas.`);
  }

  protected leaveJam(): void {
    this.state.closeOrLeaveJam();
  }

  protected decideJamCard(action: 'reject' | 'like' | 'superlike'): void {
    this.isDraggingJam.set(false);
    this.jamDrag.set({ x: 0, y: 0 });
    const song = this.currentJamDeckSong();
    if (!song) return;
    if (action === 'superlike' && !this.state.tryConsumeJamSuperlike()) {
      return;
    }

    const hasAuthJam = this.state.jamState().jamId !== undefined && Boolean(readAuthToken());
    if (hasAuthJam) {
      this.state.voteJamTrack(song, action);
    } else {
      this.notifyLocalDecision(song.title, action);
    }

    this.state.advanceJamDeckCursor(song, !(hasAuthJam && action !== 'reject'));
    this.jamDrag.set({ x: 0, y: 0 });

    const deckSongs = this.state.jamDeckSongs();
    if (this.jamDeckCursor() >= deckSongs.length - 3) {
      this.fetchMoreJamDeck();
    }
  }

  private notifyLocalDecision(title: string, action: 'reject' | 'like' | 'superlike'): void {
    const messages: Record<'reject' | 'like' | 'superlike', string> = {
      superlike: `Superlike em "${title}"! +2 pontos na fila da Jam.`,
      like: `Like em "${title}"! +1 ponto na fila da Jam.`,
      reject: `"${title}" pulada.`,
    };
    this.state.notify(messages[action]);
  }

  protected startJamCardDrag(event: PointerEvent): void {
    if (event.isPrimary === false) return;
    if (event.target instanceof Element && event.target.closest('button')) return;
    if (event.cancelable) {
      event.preventDefault();
    }
    this.jamPointerStart = { x: event.clientX, y: event.clientY };
    this.isDraggingJam.set(true);
    if (event.currentTarget instanceof HTMLElement) {
      try {
        event.currentTarget.setPointerCapture(event.pointerId);
      } catch {
        // Synthetic or detached pointer events may reject pointer capture
      }
    }
  }

  protected moveJamCardDrag(event: PointerEvent): void {
    if (event.isPrimary === false) return;
    if (this.jamPointerStart) {
      this.jamDrag.set({
        x: event.clientX - this.jamPointerStart.x,
        y: event.clientY - this.jamPointerStart.y,
      });
    }
  }

  protected cancelJamCardDrag(): void {
    this.jamPointerStart = null;
    this.isDraggingJam.set(false);
    this.jamDrag.set({ x: 0, y: 0 });
  }

  protected finishJamCardDrag(event?: PointerEvent): void {
    if (!this.jamPointerStart || event?.isPrimary === false) return;
    this.syncFinalJamDrag(this.jamPointerStart, event);
    this.jamPointerStart = null;
    this.isDraggingJam.set(false);
    const action = this.activeJamDragAction();
    if (action) {
      this.decideJamCard(action);
    } else {
      this.jamDrag.set({ x: 0, y: 0 });
    }
  }

  protected preventNativeDrag(event: Event): void {
    event.preventDefault();
  }

  private syncFinalJamDrag(start: { x: number; y: number }, event?: PointerEvent): void {
    if (
      event &&
      (event.isTrusted || event.clientX !== 0 || event.clientY !== 0) &&
      Number.isFinite(event.clientX) &&
      Number.isFinite(event.clientY)
    ) {
      this.jamDrag.set({
        x: event.clientX - start.x,
        y: event.clientY - start.y,
      });
    }
  }
}
