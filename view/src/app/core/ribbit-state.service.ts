import { Injectable, signal, computed } from '@angular/core';
import {
  Song,
  Decision,
  DecisionKind,
  Playlist,
  CommunityReview,
  JamState,
} from '@ribbit/shared-types';

import { MOCK_SONGS } from './mocks/songs.mock';
import { MOCK_REVIEWS } from './mocks/reviews.mock';
import { MOCK_PLAYLISTS } from './mocks/playlists.mock';

export const INITIAL_SONGS: readonly Song[] = MOCK_SONGS;
export const INITIAL_REVIEWS: readonly CommunityReview[] = MOCK_REVIEWS;

function getStored<T>(key: string, fallback: T): T {
  try {
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(key) : null;
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function setStored<T>(key: string, value: T): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // ignore
  }
}

@Injectable({ providedIn: 'root' })
export class RibbitStateService {
  readonly songs = signal<readonly Song[]>(INITIAL_SONGS);
  readonly history = signal<readonly Decision[]>(getStored<Decision[]>('ribbit-history', []));
  readonly playlists = signal<readonly Playlist[]>(
    getStored<Playlist[]>('ribbit-playlists', [...MOCK_PLAYLISTS]),
  );
  readonly selectedGenres = signal<readonly string[]>(
    getStored<string[]>('ribbit-genres', ['Indie', 'R&B / Soul', 'Eletrônica']),
  );
  readonly blockedGenres = signal<readonly string[]>(getStored<string[]>('ribbit-blocked', []));
  readonly comments = signal<readonly string[]>(getStored<string[]>('ribbit-comments', []));
  readonly userName = signal<string>(getStored<string>('ribbit-user-name', 'João Lucas'));
  readonly currentPlan = signal<string>(getStored<string>('ribbit-plan', 'Free'));
  readonly toast = signal<string>('');
  readonly activePage = signal<string>('discover');
  readonly authView = signal<'app' | 'login' | 'register'>('app');
  readonly activeModal = signal<string | null>(null);
  readonly mode = signal<string>('Para você');

  // Gamification: Superlikes Goal
  readonly superlikesGoal = signal<number>(3);
  readonly superlikesCount = computed<number>(
    () => this.history().filter((h) => h.kind === 'love').length,
  );
  readonly hasReachedSuperlikeGoal = computed<boolean>(
    () => this.superlikesCount() >= this.superlikesGoal(),
  );

  // Selected playlist for detailed view
  readonly selectedPlaylistName = signal<string | null>(null);

  // Queue
  readonly queue = signal<readonly number[]>([]);
  readonly queueCursor = signal<number>(0);
  readonly lastQueue = signal<readonly number[]>([3, 0, 2, 5]);

  // Jam
  readonly jamState = signal<JamState>({
    active: false,
    code: 'RIBBIT-729',
    roomName: 'Jam do João',
    votes: 0,
    voteThreshold: 2,
    durationHours: 1,
    durationMinutes: 30,
    superlikesCount: 0,
    superlikesLimit: 5,
  });

  // Current Song Index
  readonly currentIndex = signal<number>(0);

  readonly currentSong = computed<Song>(() => {
    const list = this.songs();
    const idx = this.currentIndex();
    return list[idx % list.length];
  });

  readonly isDeckEmpty = computed<boolean>(() => {
    return this.currentIndex() >= this.songs().length;
  });

  readonly jamVotes = computed<number>(() => this.jamState().votes);

  constructor() {
    this.calculateNextIndex();
  }

  notify(message: string): void {
    this.toast.set(message);
    setTimeout(() => {
      if (this.toast() === message) {
        this.toast.set('');
      }
    }, 3300);
  }

  clearToast(): void {
    this.toast.set('');
  }

  setPage(page: string): void {
    this.activePage.set(page);
  }

  setModal(modal: string | null): void {
    this.activeModal.set(modal);
  }

  setAuthView(view: 'app' | 'login' | 'register'): void {
    this.authView.set(view);
  }

  setUserName(name: string): void {
    this.userName.set(name);
    setStored('ribbit-user-name', name);
  }

  setPlan(plan: string): void {
    this.currentPlan.set(plan);
    setStored('ribbit-plan', plan);
  }

  decide(kind: DecisionKind): void {
    const idx = this.currentIndex();
    const nextHistory = [...this.history().filter((h) => h.index !== idx), { index: idx, kind }];
    this.history.set(nextHistory);
    setStored('ribbit-history', nextHistory);

    const list = this.songs();
    const blocked = this.blockedGenres();
    const nextIdx = list.findIndex(
      (s, i) => i > idx && !blocked.includes(s.genre) && !nextHistory.some((h) => h.index === i),
    );

    if (nextIdx < 0) {
      this.currentIndex.set(list.length);
    } else {
      this.currentIndex.set(nextIdx);
    }

    if (kind === 'love') {
      this.notify('Uma nova favorita! Salva nas Amadas e Curtidas.');
    } else if (kind === 'like') {
      this.notify('Salva nas suas Curtidas.');
    } else {
      this.notify('Entendido. Essa faixa não aparecerá de novo.');
    }
  }

  undo(): void {
    const hist = this.history();
    const last = hist[hist.length - 1];
    if (!last) {
      this.notify('Você ainda não fez nenhum swipe.');
      return;
    }
    const updated = hist.slice(0, -1);
    this.currentIndex.set(last.index);
    this.history.set(updated);
    setStored('ribbit-history', updated);
    this.notify('Último swipe desfeito.');
  }

  createPlaylist(name: string, durationMinutes: number = 45): void {
    const count = Math.max(3, Math.round(durationMinutes / 3.5));
    const newPlaylist: Playlist = {
      name,
      count,
      duration: `${durationMinutes} min`,
    };
    const updated = [...this.playlists(), newPlaylist];
    this.playlists.set(updated);
    setStored('ribbit-playlists', updated);
    this.notify('Playlist criada na sua biblioteca local.');
  }

  addSongToPlaylist(playlistIndex: number): void {
    const current = this.playlists();
    const updated = current.map((item, idx) =>
      idx === playlistIndex ? { ...item, count: item.count + 1 } : item,
    );
    this.playlists.set(updated);
    setStored('ribbit-playlists', updated);
    this.notify(`Faixa adicionada a ${current[playlistIndex].name}.`);
  }

  deletePlaylist(name: string): void {
    const updated = this.playlists().filter((p) => p.name !== name);
    this.playlists.set(updated);
    setStored('ribbit-playlists', updated);
    if (this.selectedPlaylistName() === name) {
      this.selectedPlaylistName.set(null);
    }
    this.notify(`Playlist "${name}" foi excluída.`);
  }

  removeSongFromPlaylist(playlistIndex: number): void {
    const current = this.playlists();
    if (!current[playlistIndex]) return;
    const item = current[playlistIndex];
    const newCount = Math.max(0, item.count - 1);
    const updated = current.map((p, idx) =>
      idx === playlistIndex ? { ...p, count: newCount } : p,
    );
    this.playlists.set(updated);
    setStored('ribbit-playlists', updated);
    this.notify(`Faixa removida de ${item.name}.`);
  }

  decideQueue(add: boolean): void {
    const cursor = this.queueCursor();
    const songs = this.songs();
    const songIndex = cursor % songs.length;

    if (add && !this.queue().includes(songIndex)) {
      this.queue.set([...this.queue(), songIndex]);
      this.notify(`${songs[songIndex].title} entrou na fila.`);
    }
    this.queueCursor.set(cursor + 1);
  }

  voteSkipJam(): void {
    const current = this.jamState();
    this.jamState.set({ ...current, votes: current.votes + 1 });
    this.notify('Seu voto para pular foi registrado.');
  }

  setJamActive(active: boolean): void {
    this.jamState.set({ ...this.jamState(), active });
  }

  addComment(comment: string): void {
    if (comment.trim()) {
      const updated = [...this.comments(), comment.trim()];
      this.comments.set(updated);
      setStored('ribbit-comments', updated);
    }
  }

  deleteComment(index: number): void {
    const updated = this.comments().filter((_, i) => i !== index);
    this.comments.set(updated);
    setStored('ribbit-comments', updated);
  }

  deleteAccount(): void {
    this.history.set([]);
    this.playlists.set([]);
    this.comments.set([]);
    this.currentIndex.set(0);
    this.activeModal.set(null);
    this.authView.set('register');
    setStored('ribbit-history', []);
    setStored('ribbit-playlists', []);
    setStored('ribbit-comments', []);
  }

  setSelectedGenres(genres: readonly string[]): void {
    this.selectedGenres.set(genres);
    setStored('ribbit-genres', genres);
  }

  setBlockedGenres(blocked: readonly string[]): void {
    this.blockedGenres.set(blocked);
    setStored('ribbit-blocked', blocked);
    this.calculateNextIndex();
  }

  private calculateNextIndex(): void {
    const saved = this.history();
    const excluded = this.blockedGenres();
    const songs = this.songs();
    const next = songs.findIndex(
      (s, i) => !saved.some((h) => h.index === i) && !excluded.includes(s.genre),
    );
    this.currentIndex.set(next < 0 ? songs.length : next);
  }
}
