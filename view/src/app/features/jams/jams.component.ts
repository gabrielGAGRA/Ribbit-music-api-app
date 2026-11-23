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
  private readonly jamDeckCursor = signal<number>(0);
  private readonly jamDrag = signal<number>(0);
  private jamPointerStart: number | null = null;

  protected readonly currentSong = computed<Song>(
    () => this.state.jamState().currentTrack ?? this.state.currentSong(),
  );

  protected readonly currentJamDeckSong = computed<Song>(() => {
    const jamDeck = this.state.jamDeckSongs();
    const list = jamDeck.length > 0 ? jamDeck : this.state.songs();
    const cursor = this.jamDeckCursor();
    return list[cursor % list.length] ?? this.state.currentSong();
  });

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
    if (jamId && nextCursor) {
      this.state.loadJamDeck(jamId, nextCursor);
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
    }

    if (currentJam.jamId !== undefined && readAuthToken()) {
      this.state.voteJamTrack(song, action);
    } else if (action === 'superlike') {
      this.state.notify(`Superlike em "${song.title}"! +2 pontos na fila da Jam.`);
    } else if (action === 'like') {
      this.state.notify(`Like em "${song.title}"! +1 ponto na fila da Jam.`);
    } else {
      this.state.notify(`"${song.title}" pulada.`);
    }

    const nextCursor = this.jamDeckCursor() + 1;
    this.jamDeckCursor.set(nextCursor);
    this.jamDrag.set(0);

    const deckSongs = this.state.jamDeckSongs();
    if (nextCursor >= deckSongs.length - 3) {
      this.fetchMoreJamDeck();
    }
  }

  protected startJamCardDrag(event: PointerEvent): void {
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
