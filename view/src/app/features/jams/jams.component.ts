import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import type { JamQueueTrack, Song } from '@ribbit/shared-types';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { TransformStyleDirective } from '../../shared/dynamic-style.directive';
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

  readonly jamView = signal<'swipe' | 'room'>('swipe');
  readonly jamDeckCursor = signal<number>(0);
  protected readonly jamDrag = signal<number>(0);
  private jamPointerStart: number | null = null;

  readonly currentSong = computed<Song>(
    () => this.state.jamState().currentTrack ?? this.state.currentSong(),
  );

  readonly currentJamDeckSong = computed<Song>(() => {
    const jamDeck = this.state.jamDeckSongs();
    const list = jamDeck.length > 0 ? jamDeck : this.state.songs();
    const cursor = this.jamDeckCursor();
    return list[cursor % list.length] ?? this.state.currentSong();
  });

  readonly upcomingQueueItems = computed<readonly JamQueueTrack[]>(() => {
    const liveQueue = this.state.jamState().queueItems ?? [];
    if (liveQueue.length > 0 || this.state.jamState().jamId !== undefined) {
      return liveQueue;
    }
    return this.state
      .songs()
      .slice(1, 5)
      .map((song, idx) => ({ song, votePoints: 4 - idx }));
  });

  readonly formattedDurationMinutes = computed<string>(() =>
    String(this.state.jamState().durationMinutes).padStart(2, '0'),
  );

  readonly jamSuperlikesCount = computed<number>(() => this.state.jamState().superlikesCount || 0);
  readonly jamSuperlikesLimit = computed<number>(() => this.state.jamState().superlikesLimit || 5);

  readonly jamCardTransform = computed<string>(() => {
    const drag = this.jamDrag();
    if (drag === 0) return '';
    return `translateX(${drag}px) rotate(${drag / 30}deg)`;
  });

  selectJamView(view: 'swipe' | 'room'): void {
    this.jamView.set(view);
  }

  openJamModal(): void {
    if (!this.state.isSpotifyLinked()) {
      this.state.promptSpotifyConnection('Conecte sua conta do Spotify para criar uma Jam no Pond.');
      return;
    }
    if (!this.state.spotifyPremium()) {
      this.state.notify('Uma conta Spotify Premium é necessária para criar uma Jam no Pond.');
      return;
    }
    this.state.setModal('jam');
  }

  joinJam(code: string): void {
    const cleaned = code.trim();
    if (!cleaned) return;
    if (!this.state.isSpotifyLinked()) {
      this.state.promptSpotifyConnection('Conecte sua conta do Spotify para entrar na Jam no Pond.');
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
    this.state.jamState.update((cur) => ({ ...cur, active: true, code: cleaned }));
    this.state.notify(`Você entrou na Jam (${cleaned})! Deslize para pontuar músicas.`);
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
      void navigator.clipboard.writeText(code);
    }
    this.state.notify(`Código ${code} copiado.`);
  }

  voteSkip(): void {
    this.state.voteSkipJam();
  }

  likeCurrent(): void {
    this.state.saveJamQueueSong(this.currentSong());
  }

  loveTrack(song: Song): void {
    if (this.state.jamState().jamId !== undefined) {
      this.state.saveJamQueueSong(song);
      return;
    }
    this.state.notify(`${song.title} foi adicionada às suas favoritas.`);
  }

  leaveJam(): void {
    this.state.closeOrLeaveJam();
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
