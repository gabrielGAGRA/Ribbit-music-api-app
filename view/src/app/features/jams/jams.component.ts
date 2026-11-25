import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { JamQueueTrack, Song } from '@ribbit/shared-types';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { TransformStyleDirective } from '../../shared/transform-style.directive';
import { IconComponent } from '../../shared/icon.component';

/** Collaborative Jam workspace supporting room joining, deck voting, skip consensus, and queue saving. */
@Component({
  selector: 'app-jams',
  standalone: true,
  imports: [IconComponent, TransformStyleDirective],
  templateUrl: './jams.component.html',
  styleUrl: './jams.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JamsComponent {
  protected readonly state = inject(RibbitStateService);

  protected readonly jamView = signal<'swipe' | 'room'>('swipe');
  readonly jamDeckCursor = this.state.jamDeckCursor;
  protected readonly jamDrag = signal<number>(0);
  private jamPointerStart: number | null = null;

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

  protected readonly jamSuperlikesCount = computed<number>(
    () => this.state.jamState().superlikesCount || 0,
  );
  protected readonly jamSuperlikesLimit = computed<number>(
    () => this.state.jamState().superlikesLimit || 5,
  );

  protected readonly jamCardTransform = computed<string>(() => {
    const drag = this.jamDrag();
    if (drag === 0) return '';
    return `translateX(${drag}px) rotate(${drag / 30}deg)`;
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
    this.jamDrag.set(0);

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
    if (event.target instanceof Element && event.target.closest('button')) return;
    this.jamPointerStart = event.clientX;
    if (event.currentTarget instanceof HTMLElement) {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  }

  protected moveJamCardDrag(event: PointerEvent): void {
    if (this.jamPointerStart !== null) {
      this.jamDrag.set(event.clientX - this.jamPointerStart);
    }
  }

  protected cancelJamCardDrag(): void {
    this.jamPointerStart = null;
    this.jamDrag.set(0);
  }

  protected finishJamCardDrag(): void {
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
