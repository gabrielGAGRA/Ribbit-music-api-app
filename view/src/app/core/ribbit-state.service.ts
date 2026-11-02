import type { OnDestroy } from '@angular/core';
import { Injectable, computed, inject, signal } from '@angular/core';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import type {
  AuthApiResponse,
  CommunityReview,
  CreateJamApiRequest,
  Decision,
  DecisionKind,
  DeckPlaylistApiRequest,
  JamApiDto,
  JamState,
  Playlist,
  RecentInteractedTrackApiDto,
  Song,
  SubscriptionPlan,
  UserApiDto,
} from '@ribbit/shared-types';
import { isPremiumRequiredError, toApiError } from './api-error';
import { mapApiActionToDecision, mapJamStateDto, mapTrackDtoToSong } from './api-mappers';
import { AudioPlayerService } from './audio-player.service';
import { AuthSessionNotifier } from './auth-session.notifier';
import {
  clearAuthStorage,
  readAuthToken,
  readStoredUser,
  writeAuthToken,
  writeStoredUser,
} from './auth-token.storage';
import { MOCK_REVIEWS } from './mocks/reviews.mock';
import { MOCK_SONGS } from './mocks/songs.mock';
import { PlanService } from './services/plan.service';
import { PlaylistService } from './services/playlist.service';
import { SongService } from './services/song.service';
import { JamService } from '../features/jams/jam.service';
import { ProfileApiService } from '../features/profile/profile-api.service';

export const INITIAL_SONGS: readonly Song[] = MOCK_SONGS;
export const INITIAL_REVIEWS: readonly CommunityReview[] = MOCK_REVIEWS;

function getStoredGenres(key: string, fallback: readonly string[]): readonly string[] {
  try {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === 'string')
      : fallback;
  } catch {
    // Ignore malformed localStorage preference values
    return fallback;
  }
}

function setStoredGenres(key: string, value: readonly string[]): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // Ignore storage quota errors
  }
}

const DEFAULT_JAM_STATE: JamState = {
  active: false,
  code: '',
  roomName: 'Minha Jam',
  votes: 0,
  voteThreshold: 3,
  durationHours: 1,
  durationMinutes: 0,
  accumulatedMinutes: 0,
  superlikesCount: 0,
  superlikesLimit: 5,
  queueItems: [],
};

/** Central reactive state coordinator synchronizing Angular signals with the Ribbit FastAPI backend. */
@Injectable({ providedIn: 'root' })
export class RibbitStateService implements OnDestroy {
  private readonly songService = inject(SongService);
  private readonly playlistService = inject(PlaylistService);
  private readonly planService = inject(PlanService);
  private readonly profileApi = inject(ProfileApiService);
  private readonly jamService = inject(JamService);
  private readonly audioPlayer = inject(AudioPlayerService);
  private readonly sessionNotifier = inject(AuthSessionNotifier);

  private readonly initialUser = readStoredUser();
  private readonly hasInitialToken = readAuthToken() !== null;
  private jamPollTimer: ReturnType<typeof setInterval> | null = null;
  private readonly unsubscribeUnauthorized: () => void;

  readonly songs = signal<readonly Song[]>(INITIAL_SONGS);
  readonly discoverySong = signal<Song | null>(null);
  readonly isDeckEmpty = signal<boolean>(false);
  readonly lastSwiped = signal<{
    readonly song: Song;
    readonly kind: DecisionKind;
    readonly index: number;
  } | null>(null);

  readonly history = signal<readonly Decision[]>([]);
  readonly likedSongs = signal<readonly Song[]>([]);
  readonly lovedSongs = signal<readonly Song[]>([]);
  readonly rejectedSongs = signal<readonly Song[]>([]);

  readonly playlists = signal<readonly Playlist[]>([]);
  readonly selectedGenres = signal<readonly string[]>(
    getStoredGenres('ribbit-genres', ['Indie', 'R&B / Soul', 'Eletrônica']),
  );
  readonly blockedGenres = signal<readonly string[]>(this.initialUser?.blocked_genres ?? []);

  readonly userId = signal<number | null>(this.initialUser?.user_id ?? null);
  readonly userEmail = signal<string>(this.initialUser?.email ?? '');
  readonly userName = signal<string>(this.initialUser?.display_name ?? 'Visitante');
  readonly currentPlanId = signal<number>(this.initialUser?.plan_id ?? 1);
  readonly currentPlan = signal<string>('Free');
  readonly spotifyId = signal<string | null>(this.initialUser?.spotify_id ?? null);

  readonly toast = signal<string>('');
  readonly activePage = signal<string>('discover');
  readonly authView = signal<'app' | 'login' | 'register'>(this.hasInitialToken ? 'app' : 'login');
  readonly activeModal = signal<string | null>(null);
  readonly mode = signal<string>('Para você');

  readonly upgradePromptReason = signal<string>(
    'Este recurso faz parte dos planos pagos do Ribbit.',
  );
  readonly pendingCheckoutPlan = signal<SubscriptionPlan | null>(null);

  readonly selectedDetailsSong = signal<Song | null>(null);
  readonly activeTrackReviews = signal<readonly CommunityReview[]>([]);
  readonly searchQuery = signal<string>('');
  readonly searchFilterGenre = signal<string>('Todos');
  readonly searchFilterYear = signal<number | undefined>(undefined);

  readonly superlikesGoal = signal<number>(3);
  readonly superlikesCount = computed<number>(() => this.lovedSongs().length);
  readonly hasReachedSuperlikeGoal = computed<boolean>(
    () => this.superlikesCount() >= this.superlikesGoal(),
  );

  readonly selectedPlaylistName = signal<string | null>(null);

  readonly queue = signal<readonly number[]>([]);
  readonly queueSongs = signal<readonly Song[]>([]);
  readonly queueCursor = signal<number>(0);
  readonly lastQueue = signal<readonly number[]>([0, 1, 2]);

  readonly jamState = signal<JamState>(DEFAULT_JAM_STATE);
  readonly jamDeckSongs = signal<readonly Song[]>([]);
  readonly jamVotes = computed<number>(() => this.jamState().votes);

  readonly currentIndex = signal<number>(0);

  readonly currentSong = computed<Song>(() => {
    const activeDiscovery = this.discoverySong();
    if (activeDiscovery) {
      return activeDiscovery;
    }
    const list = this.songs();
    const idx = this.currentIndex();
    return list[idx % list.length] ?? INITIAL_SONGS[0]!;
  });

  readonly detailsTargetSong = computed<Song>(
    () => this.selectedDetailsSong() ?? this.currentSong(),
  );

  readonly isSpotifyLinked = computed<boolean>(() => Boolean(this.spotifyId()));

  constructor() {
    this.unsubscribeUnauthorized = this.sessionNotifier.onUnauthorized(() => {
      this.handleUnauthorizedSession();
    });
    if (this.hasInitialToken) {
      this.hydrateAuthenticatedSession();
    }
  }

  ngOnDestroy(): void {
    this.stopJamPolling();
    this.unsubscribeUnauthorized();
  }

  /** Displays a transient toast notification message. */
  notify(message: string): void {
    this.toast.set(message);
    setTimeout(() => {
      if (this.toast() === message) {
        this.toast.set('');
      }
    }, 3300);
  }

  /** Dismisses any active toast notification immediately. */
  clearToast(): void {
    this.toast.set('');
  }

  /** Updates the currently active navigation page identifier. */
  setPage(page: string): void {
    this.activePage.set(page);
  }

  /** Opens or closes a modal dialog, loading track reviews when opening details. */
  setModal(modal: string | null): void {
    this.activeModal.set(modal);
    if (modal === 'details') {
      const target = this.detailsTargetSong();
      if (target.trackId !== undefined) {
        this.loadReviewsForTrack(target);
      }
    } else if (modal === null) {
      this.selectedDetailsSong.set(null);
    }
  }

  /** Opens the track details & reviews modal for a specific song. */
  openTrackDetailsModal(song: Song): void {
    this.selectedDetailsSong.set(song);
    this.setModal('details');
  }

  /** Switches between authenticated shell, login, and registration views. */
  setAuthView(view: 'app' | 'login' | 'register'): void {
    this.authView.set(view);
  }

  /** Persists credentials after login or registration and hydrates backend data. */
  completeAuthentication(auth: AuthApiResponse, fallbackPlanName?: string): void {
    writeAuthToken(auth.access_token);
    this.applyUserDto(auth.user);
    if (fallbackPlanName) {
      this.currentPlan.set(fallbackPlanName);
    }
    this.authView.set('app');
    this.hydrateAuthenticatedSession();
  }

  /** Logs the current user out and clears persisted session state. */
  logout(message = 'Você saiu da sua conta.'): void {
    this.stopJamPolling();
    clearAuthStorage();
    this.resetUserCollections();
    this.authView.set('login');
    this.notify(message);
  }

  /** Synchronizes user profile, catalog, playlists, discovery card, and history from /api. */
  hydrateAuthenticatedSession(): void {
    if (!readAuthToken()) return;

    this.planService
      .loadPlanDtos()
      .pipe(catchError(() => of([])))
      .subscribe();

    this.profileApi.getProfile().subscribe({
      next: (profile) => {
        this.applyUserDto(profile.user);
        this.currentPlan.set(profile.plan.name);
        this.currentPlanId.set(profile.plan.plan_id);
      },
      error: () => {
        // 401 is handled centrally by authInterceptor
      },
    });

    this.refreshCatalogAndFeed();
    this.refreshPlaylists();
    this.refreshInteractedCollections();
    this.loadNextDiscoveryTrack();
  }

  /** Fetches the next candidate song for the Discovery deck. */
  loadNextDiscoveryTrack(): void {
    if (!readAuthToken()) return;
    this.songService.getNextDiscoverySong().subscribe({
      next: (song) => {
        if (song) {
          this.discoverySong.set(song);
          this.isDeckEmpty.set(false);
          this.audioPlayer.loadTrack(song.previewUrl);
        } else {
          this.discoverySong.set(null);
          this.isDeckEmpty.set(true);
        }
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Reloads the user's playlists from /api/playlists. */
  refreshPlaylists(): void {
    if (!readAuthToken()) return;
    this.playlistService.getPlaylists().subscribe({
      next: (list) => {
        this.playlists.set(list);
      },
      error: () => {
        // Keep current playlists snapshot on transient error
      },
    });
  }

  /** Reloads interacted track collections (likes, loved, rejected) from backend history. */
  refreshInteractedCollections(): void {
    if (!readAuthToken()) return;
    forkJoin({
      recent: this.songService
        .getRecentInteractedTracks(100)
        .pipe(catchError(() => of([] as readonly RecentInteractedTrackApiDto[]))),
      allHistory: this.profileApi.listHistory().pipe(catchError(() => of([]))),
    }).subscribe(({ recent, allHistory }) => {
      this.applyInteractedHistory(recent, allHistory.length);
    });
  }

  /** Reloads the catalog and community reviews feed. */
  refreshCatalogAndFeed(): void {
    if (!readAuthToken()) return;
    this.songService.getSongs().subscribe({
      next: (catalog) => {
        if (catalog.length > 0) {
          this.songs.set(catalog);
          this.lastQueue.set(
            catalog.slice(0, Math.min(4, catalog.length)).map((_, index) => index),
          );
        }
        const lookup = this.buildTrackLookup(catalog);
        this.songService
          .loadCommunityFeed({
            trackLookup: lookup,
            currentUserId: this.userId() ?? undefined,
            currentUserName: this.userName(),
          })
          .pipe(catchError(() => of([])))
          .subscribe();
      },
      error: () => {
        // Keep fallback songs if catalog endpoint is temporarily unreachable
      },
    });
  }

  /** Updates the user's display name on the backend via PUT /api/profile/me. */
  setUserName(name: string): void {
    const trimmed = name.trim();
    if (!trimmed) return;
    this.userName.set(trimmed);
    if (!readAuthToken()) return;

    this.profileApi.updateProfile({ displayName: trimmed }).subscribe({
      next: (updated) => {
        this.applyUserDto(updated);
        this.notify(`Nome atualizado para "${updated.display_name}".`);
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Sets the current plan label locally or initiates plan change flow. */
  setPlan(planName: string): void {
    this.currentPlan.set(planName);
  }

  /** Opens the mock payment checkout modal for paid plans or downgrades to Free. */
  initiatePlanSelection(plan: SubscriptionPlan): void {
    if (plan.name === this.currentPlan()) {
      this.notify(`Você já está no plano ${plan.displayName}.`);
      return;
    }
    if (plan.name === 'Free') {
      this.cancelSubscription();
      return;
    }
    this.pendingCheckoutPlan.set(plan);
    this.setModal('checkout');
  }

  /** Completes simulated payment and persists the new subscription tier on the backend. */
  confirmMockPlanCheckout(paymentMethod: 'card' | 'pix'): void {
    const targetPlan = this.pendingCheckoutPlan();
    if (!targetPlan) return;

    const resolvedPlanId =
      targetPlan.planId ?? this.planService.resolvePlanIdByName(targetPlan.name);

    this.planService.changePlan(resolvedPlanId).subscribe({
      next: (updatedUser) => {
        this.applyUserDto(updatedUser);
        this.currentPlan.set(targetPlan.name);
        this.currentPlanId.set(resolvedPlanId);
        this.pendingCheckoutPlan.set(null);
        this.setModal(null);
        const methodLabel = paymentMethod === 'pix' ? 'PIX' : 'Cartão';
        this.notify(
          `Pagamento simulado (${methodLabel}) confirmado! Bem-vindo ao ${targetPlan.displayName}.`,
        );
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Cancels the user's paid subscription via DELETE /api/profile/plan. */
  cancelSubscription(): void {
    if (!readAuthToken()) {
      this.currentPlan.set('Free');
      this.notify('Assinatura cancelada. Seu plano agora é o Free.');
      return;
    }
    this.planService.cancelPlan().subscribe({
      next: (updatedUser) => {
        this.applyUserDto(updatedUser);
        this.currentPlan.set('Free');
        this.currentPlanId.set(updatedUser.plan_id);
        this.notify('Assinatura cancelada. Seu plano agora é o Free.');
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Surfaces an upgrade notice modal directing Free users to /plans when a feature returns 403. */
  promptPlanUpgrade(reason: string): void {
    this.upgradePromptReason.set(reason);
    this.setModal('upgrade');
  }

  /** Links or unlinks a Spotify account via POST /api/profile/link-spotify. */
  toggleSpotifyLink(): void {
    const uid = this.userId();
    if (uid === null) return;
    const nextSpotifyId = this.isSpotifyLinked() ? '' : `spotify_user_${uid}`;
    this.profileApi.linkSpotify(uid, nextSpotifyId).subscribe({
      next: (updatedUser) => {
        this.applyUserDto(updatedUser);
        this.notify(
          this.isSpotifyLinked()
            ? 'Conta do Spotify vinculada com sucesso.'
            : 'Conta do Spotify desvinculada.',
        );
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Records a swipe decision on /api/discovery/interact and advances to the next track. */
  decide(kind: DecisionKind): void {
    const song = this.currentSong();
    const idx = this.currentIndex();
    const nextHistory: readonly Decision[] = [
      ...this.history().filter((item) => item.index !== idx),
      { index: idx, kind, ...(song.trackId !== undefined ? { trackId: song.trackId } : {}) },
    ];
    this.history.set(nextHistory);
    this.lastSwiped.set({ song, kind, index: idx });
    this.applyLocalSwipeCollectionUpdate(song, kind);
    this.notifySwipeDecision(kind);

    if (song.trackId !== undefined && readAuthToken()) {
      this.songService.recordSwipe(song.trackId, kind).subscribe({
        next: () => {
          this.loadNextDiscoveryTrack();
          this.refreshInteractedCollections();
        },
        error: (err: unknown) => {
          this.notify(toApiError(err).message);
        },
      });
      return;
    }

    this.advanceLocalFallbackIndex(idx, nextHistory);
  }

  /** Restores the last swiped song back onto the Discovery card so the user can re-decide. */
  undo(): void {
    const last = this.lastSwiped();
    if (!last) {
      this.notify('Você ainda não fez nenhum swipe.');
      return;
    }
    this.currentIndex.set(last.index);
    if (last.song.trackId !== undefined) {
      this.discoverySong.set(last.song);
    }
    this.isDeckEmpty.set(false);
    this.lastSwiped.set(null);
    this.history.update((items) => items.slice(0, -1));
    this.audioPlayer.loadTrack(last.song.previewUrl);
    this.notify('Último swipe desfeito. Avalie a faixa novamente.');
  }

  /** Revises a previous interaction from Collection via PUT /api/profile/interaction. */
  reviseCollectionItem(song: Song, currentKind: DecisionKind): void {
    if (song.trackId === undefined || this.userId() === null) {
      return;
    }
    const targetAction = currentKind === 'reject' ? 'like' : 'dislike';
    this.profileApi
      .changeInteraction({
        userId: this.userId()!,
        trackId: song.trackId,
        newAction: targetAction,
      })
      .subscribe({
        next: () => {
          this.refreshInteractedCollections();
          if (currentKind === 'reject') {
            this.discoverySong.set(song);
            this.isDeckEmpty.set(false);
            this.notify(`"${song.title}" ganhou uma segunda chance!`);
          } else {
            this.notify(`"${song.title}" foi atualizada na sua coleção.`);
          }
        },
        error: (err: unknown) => {
          if (isPremiumRequiredError(err)) {
            this.promptPlanUpgrade(
              'Revisar músicas rejeitadas ou alterar escolhas passadas é exclusivo dos planos Ribbit Pro e Família.',
            );
            return;
          }
          this.notify(toApiError(err).message);
        },
      });
  }

  /** Creates a contextual playlist on the backend and optionally populates it with tracks. */
  createPlaylist(
    name: string,
    durationMinutes = 45,
    extraFilters: Omit<DeckPlaylistApiRequest, 'name' | 'duration_minutes'> = {},
    seedSongs: readonly Song[] = [],
  ): void {
    const trimmedName = name.trim() || 'Minha nova frequência';
    if (!readAuthToken()) return;

    this.playlistService
      .createDeckPlaylist({
        name: trimmedName,
        duration_minutes: durationMinutes,
        ...extraFilters,
      })
      .subscribe({
        next: (created) => {
          this.playlists.set(this.playlistService.playlists());
          this.populatePlaylistSeedTracks(created.playlistId, seedSongs);
          this.notify(`Playlist "${created.name}" criada na sua biblioteca.`);
        },
        error: (err: unknown) => {
          this.notify(toApiError(err).message);
        },
      });
  }

  /** Adds the current (or provided) song to an existing playlist via swipe-add. */
  addSongToPlaylist(playlistIndex: number, targetSong?: Song): void {
    const playlist = this.playlists()[playlistIndex];
    const song = targetSong ?? this.currentSong();
    if (!playlist?.playlistId || song.trackId === undefined) {
      this.notify('Selecione uma faixa válida para adicionar à playlist.');
      return;
    }

    this.playlistService.addTrackToPlaylist(playlist.playlistId, song.trackId).subscribe({
      next: () => {
        this.refreshSinglePlaylist(playlist.playlistId!);
        this.notify(`"${song.title}" adicionada a ${playlist.name}.`);
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Deletes a playlist by name or Playlist reference on the backend. */
  deletePlaylist(nameOrPlaylist: string | Playlist): void {
    const playlist =
      typeof nameOrPlaylist === 'string'
        ? this.playlists().find((item) => item.name === nameOrPlaylist)
        : nameOrPlaylist;
    if (!playlist?.playlistId) return;

    this.playlistService.deletePlaylist(playlist.playlistId).subscribe({
      next: () => {
        this.playlists.set(this.playlistService.playlists());
        if (this.selectedPlaylistName() === playlist.name) {
          this.selectedPlaylistName.set(null);
        }
        this.notify(`Playlist "${playlist.name}" foi excluída.`);
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Removes a track from a playlist on the backend and refreshes playlist state. */
  removeTrackFromPlaylist(playlistId: number, trackId: number, playlistName: string): void {
    this.playlistService.removeTrackFromPlaylist(playlistId, trackId).subscribe({
      next: () => {
        this.refreshSinglePlaylist(playlistId);
        this.notify(`Faixa removida de ${playlistName}.`);
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Manages temporary session queue swipe decisions. */
  decideQueue(add: boolean): void {
    const cursor = this.queueCursor();
    const list = this.songs();
    const songIndex = cursor % list.length;
    const song = list[songIndex];

    if (add && song && !this.queue().includes(songIndex)) {
      this.queue.set([...this.queue(), songIndex]);
      this.queueSongs.update((prev) => [...prev, song]);
      this.notify(`${song.title} entrou na fila.`);
    }
    this.queueCursor.set(cursor + 1);
  }

  /** Creates a collaborative Jam room on /api/jams and starts live state polling. */
  createJamRoom(payload: CreateJamApiRequest): void {
    this.jamService.createJam(payload).subscribe({
      next: (jamDto) => {
        this.activateJamFromDto(jamDto);
        this.notify(`Jam "${jamDto.room_name}" criada! Código: ${jamDto.room_code}`);
      },
      error: (err: unknown) => {
        if (isPremiumRequiredError(err)) {
          this.promptPlanUpgrade(toApiError(err).message);
          return;
        }
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Joins an active Jam room via room code on POST /api/jams/join. */
  joinJamRoom(roomCode: string): void {
    const cleaned = roomCode.trim();
    if (!cleaned) return;
    this.jamService.joinJam(cleaned).subscribe({
      next: (jamDto) => {
        this.activateJamFromDto(jamDto);
        this.notify(`Você entrou na Jam (${jamDto.room_code})! Deslize para pontuar.`);
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Votes on a Jam deck card (like +1 or superlike +2) and syncs room state. */
  voteJamTrack(song: Song, action: 'reject' | 'like' | 'superlike'): void {
    const jamId = this.jamState().jamId;
    if (action === 'reject') {
      this.notify(`"${song.title}" pulada.`);
      return;
    }
    if (!jamId || song.trackId === undefined) return;

    this.jamService.voteTrack({ jamId, trackId: song.trackId, action }).subscribe({
      next: () => {
        const pts = action === 'superlike' ? '+2 pontos' : '+1 ponto';
        this.notify(
          `${action === 'superlike' ? 'Superlike' : 'Like'} em "${song.title}"! ${pts} na fila.`,
        );
        this.syncJamState(jamId);
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Registers a skip vote on the active Jam track via POST /api/jams/{id}/skip-vote. */
  voteSkipJam(): void {
    const jam = this.jamState();
    if (!jam.jamId) {
      this.jamState.set({ ...jam, votes: jam.votes + 1 });
      this.notify('Seu voto para pular foi registrado.');
      return;
    }
    const activeTrackId = jam.currentTrack?.trackId;
    this.jamService.voteSkip(jam.jamId, activeTrackId).subscribe({
      next: (res) => {
        this.jamState.update((cur) => ({
          ...cur,
          votes: res.votes,
          voteThreshold: res.threshold,
          active: res.is_active,
        }));
        this.syncJamState(jam.jamId!);
        this.notify(
          res.advanced
            ? 'Votação atingida! Pulando para a próxima faixa da Jam.'
            : `Voto registrado (${res.votes}/${res.threshold}).`,
        );
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Saves a track from the Jam queue to the user's liked songs via POST /api/jams/{id}/save-queue-track. */
  saveJamQueueSong(song: Song): void {
    const jamId = this.jamState().jamId;
    if (!jamId || song.trackId === undefined) return;
    this.jamService.saveQueueTrack(jamId, song.trackId).subscribe({
      next: () => {
        this.refreshInteractedCollections();
        this.notify(`"${song.title}" foi salva nas suas Curtidas!`);
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Closes the active Jam room (for hosts) or leaves the room locally. */
  closeOrLeaveJam(): void {
    const jam = this.jamState();
    this.stopJamPolling();
    if (jam.jamId && jam.hostUserId === this.userId()) {
      this.jamService.closeJam(jam.jamId).subscribe({
        next: () => {
          this.jamState.set(DEFAULT_JAM_STATE);
          this.notify('Jam encerrada para todos os participantes.');
        },
        error: () => {
          this.jamState.set(DEFAULT_JAM_STATE);
        },
      });
      return;
    }
    this.jamState.set(DEFAULT_JAM_STATE);
    this.notify('Você saiu da Jam.');
  }

  /** Toggles Jam active flag locally when needed. */
  setJamActive(active: boolean): void {
    this.jamState.set({ ...this.jamState(), active });
    if (!active) {
      this.stopJamPolling();
    }
  }

  /** Loads reviews for a specific track into activeTrackReviews. */
  loadReviewsForTrack(song: Song): void {
    if (song.trackId === undefined) return;
    this.songService
      .getTrackReviews({
        trackId: song.trackId,
        track: song,
        currentUserId: this.userId() ?? undefined,
        currentUserName: this.userName(),
      })
      .subscribe({
        next: (reviews) => {
          this.activeTrackReviews.set(reviews);
        },
        error: () => {
          this.activeTrackReviews.set([]);
        },
      });
  }

  /** Publishes a review on POST /api/reviews for the currently inspected track. */
  publishTrackReview(rating: number, commentText: string): void {
    const target = this.detailsTargetSong();
    if (target.trackId === undefined) return;
    const effectiveRating = rating >= 1 && rating <= 5 ? rating : 5;
    this.songService
      .publishReview({
        trackId: target.trackId,
        rating: effectiveRating,
        text: commentText.trim(),
        track: target,
        currentUserId: this.userId() ?? undefined,
        currentUserName: this.userName(),
      })
      .subscribe({
        next: (created) => {
          this.activeTrackReviews.update((list) => [created, ...list]);
          this.refreshCatalogAndFeed();
          this.notify('Sua avaliação foi publicada na comunidade!');
        },
        error: (err: unknown) => {
          this.notify(toApiError(err).message);
        },
      });
  }

  /** Deletes one of the user's published reviews via DELETE /api/reviews/{id}. */
  deleteTrackReview(reviewId: number): void {
    this.songService.deleteReview(reviewId).subscribe({
      next: () => {
        this.activeTrackReviews.update((list) => list.filter((r) => r.id !== reviewId));
        this.refreshCatalogAndFeed();
        this.notify('Avaliação excluída.');
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Deletes the authenticated user's account via DELETE /api/profile/account. */
  deleteAccount(): void {
    if (!readAuthToken()) {
      this.resetUserCollections();
      this.activeModal.set(null);
      this.authView.set('register');
      return;
    }

    this.profileApi.deleteAccount().subscribe({
      next: () => {
        this.stopJamPolling();
        clearAuthStorage();
        this.resetUserCollections();
        this.activeModal.set(null);
        this.authView.set('register');
        this.notify('Sua conta e todos os seus dados foram excluídos.');
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Persists favorite genres locally for UI recommendations context. */
  setSelectedGenres(genres: readonly string[]): void {
    this.selectedGenres.set(genres);
    setStoredGenres('ribbit-genres', genres);
  }

  /** Updates blocked genres on PUT /api/profile/blocked-genres (triggers upgrade modal on 403). */
  setBlockedGenres(blocked: readonly string[]): void {
    const previous = this.blockedGenres();
    this.blockedGenres.set(blocked);
    if (!readAuthToken()) return;

    this.profileApi.updateBlockedGenres(blocked).subscribe({
      next: (updatedUser) => {
        this.applyUserDto(updatedUser);
        this.loadNextDiscoveryTrack();
      },
      error: (err: unknown) => {
        this.blockedGenres.set(previous);
        if (isPremiumRequiredError(err)) {
          this.promptPlanUpgrade(
            'Bloquear gêneros indesejados é um benefício exclusivo dos planos Ribbit Pro e Família.',
          );
          return;
        }
        this.notify(toApiError(err).message);
      },
    });
  }

  private applyUserDto(user: UserApiDto): void {
    writeStoredUser(user);
    this.userId.set(user.user_id);
    this.userEmail.set(user.email);
    this.userName.set(user.display_name);
    this.currentPlanId.set(user.plan_id);
    this.spotifyId.set(user.spotify_id ?? null);
    this.blockedGenres.set(user.blocked_genres ? [...user.blocked_genres] : []);
  }

  private applyInteractedHistory(
    recentItems: readonly RecentInteractedTrackApiDto[],
    _totalCount: number,
  ): void {
    const likes: Song[] = [];
    const loved: Song[] = [];
    const rejected: Song[] = [];

    for (const entry of recentItems) {
      const song = mapTrackDtoToSong(entry.track);
      const kind = mapApiActionToDecision(entry.interaction.action);
      if (kind === 'love') {
        loved.push(song);
        likes.push(song);
      } else if (kind === 'like') {
        likes.push(song);
      } else {
        rejected.push(song);
      }
    }

    this.likedSongs.set(likes);
    this.lovedSongs.set(loved);
    this.rejectedSongs.set(rejected);
  }

  private applyLocalSwipeCollectionUpdate(song: Song, kind: DecisionKind): void {
    const notSame = (item: Song): boolean =>
      song.trackId !== undefined ? item.trackId !== song.trackId : item.title !== song.title;

    this.likedSongs.update((list) =>
      kind === 'reject' ? list.filter(notSame) : [song, ...list.filter(notSame)],
    );
    this.lovedSongs.update((list) =>
      kind === 'love' ? [song, ...list.filter(notSame)] : list.filter(notSame),
    );
    this.rejectedSongs.update((list) =>
      kind === 'reject' ? [song, ...list.filter(notSame)] : list.filter(notSame),
    );
  }

  private notifySwipeDecision(kind: DecisionKind): void {
    if (kind === 'love') {
      this.notify('Uma nova favorita! Salva nas Amadas e Curtidas.');
    } else if (kind === 'like') {
      this.notify('Salva nas suas Curtidas.');
    } else {
      this.notify('Entendido. Essa faixa não aparecerá de novo.');
    }
  }

  private advanceLocalFallbackIndex(idx: number, nextHistory: readonly Decision[]): void {
    const list = this.songs();
    const blocked = this.blockedGenres();
    const nextIdx = list.findIndex(
      (s, i) => i > idx && !blocked.includes(s.genre) && !nextHistory.some((h) => h.index === i),
    );
    if (nextIdx < 0) {
      this.isDeckEmpty.set(true);
    } else {
      this.currentIndex.set(nextIdx);
    }
  }

  private populatePlaylistSeedTracks(
    playlistId: number | undefined,
    seedSongs: readonly Song[],
  ): void {
    if (!playlistId || seedSongs.length === 0) return;
    const validTrackIds = seedSongs
      .map((item) => item.trackId)
      .filter((id): id is number => id !== undefined);
    if (validTrackIds.length === 0) return;

    forkJoin(
      validTrackIds.map((trackId) =>
        this.playlistService
          .addTrackToPlaylist(playlistId, trackId)
          .pipe(catchError(() => of(false))),
      ),
    ).subscribe(() => {
      this.refreshSinglePlaylist(playlistId);
    });
  }

  private refreshSinglePlaylist(playlistId: number): void {
    this.playlistService.getPlaylistById(playlistId).subscribe({
      next: (fresh) => {
        this.playlists.update((list) =>
          list.map((item) => (item.playlistId === playlistId ? fresh : item)),
        );
      },
      error: () => {
        this.refreshPlaylists();
      },
    });
  }

  private activateJamFromDto(jamDto: JamApiDto): void {
    const jamId = jamDto.jam_id;
    const hours = Math.floor(jamDto.duration_minutes / 60);
    const mins = jamDto.duration_minutes % 60;
    this.jamState.set({
      ...(jamId != null ? { jamId } : {}),
      hostUserId: jamDto.host_user_id,
      active: jamDto.is_active,
      code: jamDto.room_code,
      roomName: jamDto.room_name,
      votes: 0,
      voteThreshold: jamDto.skip_votes_threshold,
      durationHours: hours,
      durationMinutes: mins,
      accumulatedMinutes: Math.round(jamDto.accumulated_duration_seconds / 60),
      superlikesCount: jamDto.superlikes_used,
      superlikesLimit: jamDto.max_superlikes,
      queueItems: [],
    });

    if (jamId != null) {
      this.loadJamDeck(jamId);
      this.syncJamState(jamId);
      this.startJamPolling(jamId);
    }
  }

  private loadJamDeck(jamId: number): void {
    this.jamService.getJamDeck(jamId, 30).subscribe({
      next: (deck) => {
        this.jamDeckSongs.set(deck);
      },
      error: () => {
        this.jamDeckSongs.set(this.songs());
      },
    });
  }

  private syncJamState(jamId: number): void {
    this.jamService.getJamState(jamId).subscribe({
      next: (stateDto) => {
        const lookup = this.buildTrackLookup([...this.songs(), ...this.jamDeckSongs()]);
        const mapped = mapJamStateDto({
          dto: stateDto,
          trackLookup: lookup,
          fallbackSong: this.currentSong(),
        });
        this.jamState.set(mapped);
        if (!mapped.active) {
          this.stopJamPolling();
        }
      },
      error: () => {
        // Keep last valid Jam state during transient poll hiccups
      },
    });
  }

  private startJamPolling(jamId: number): void {
    this.stopJamPolling();
    this.jamPollTimer = setInterval(() => {
      if (this.jamState().active && this.activePage() === 'jams') {
        this.syncJamState(jamId);
      }
    }, 4000);
  }

  private stopJamPolling(): void {
    if (this.jamPollTimer !== null) {
      clearInterval(this.jamPollTimer);
      this.jamPollTimer = null;
    }
  }

  private buildTrackLookup(tracks: readonly Song[]): Map<number, Song> {
    const map = new Map<number, Song>();
    for (const track of tracks) {
      if (track.trackId !== undefined) {
        map.set(track.trackId, track);
      }
    }
    return map;
  }

  private handleUnauthorizedSession(): void {
    this.stopJamPolling();
    this.resetUserCollections();
    this.authView.set('login');
    this.notify('Sua sessão expirou. Entre novamente para continuar.');
  }

  private resetUserCollections(): void {
    this.history.set([]);
    this.likedSongs.set([]);
    this.lovedSongs.set([]);
    this.rejectedSongs.set([]);
    this.playlists.set([]);
    this.activeTrackReviews.set([]);
    this.discoverySong.set(null);
    this.lastSwiped.set(null);
    this.isDeckEmpty.set(false);
    this.jamState.set(DEFAULT_JAM_STATE);
    this.userId.set(null);
    this.userEmail.set('');
    this.userName.set('Visitante');
    this.currentPlan.set('Free');
    this.currentPlanId.set(1);
    this.spotifyId.set(null);
    this.activeModal.set(null);
  }
}
