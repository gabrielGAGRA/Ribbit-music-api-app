import type { OnDestroy } from '@angular/core';
import { Injectable, computed, inject, signal } from '@angular/core';
import type { Subscription } from 'rxjs';
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
  TrackAccessHistoryItem,
  TrackAccessSource,
  UserApiDto,
} from '@ribbit/shared-types';
import {
  isPremiumRequiredError,
  isSpotifyConnectionRequiredError,
  isSpotifyError,
  isSpotifyPremiumRequiredError,
  toApiError,
} from './api-error';
import {
  computeSongsDurationSeconds,
  formatTotalMinutes,
  isPlaylistDurationLimitReached,
  mapApiActionToDecision,
  mapJamStateDto,
  mapTrackDtoToSong,
} from './api-mappers';
import { AudioPlayerService } from './audio-player.service';
import { AuthSessionNotifier } from './auth-session.notifier';
import { matchesGenreFilter } from './genre-catalog';
import {
  clearAuthStorage,
  readAuthToken,
  readStoredUser,
  writeAuthToken,
  writeStoredUser,
} from './auth-token.storage';
import { PlanService } from './plan.service';
import { PlaylistService } from './playlist.service';
import { SongService } from './song.service';
import type { ReviewSortOption } from './song.service';
import { JamService } from '../features/jams/jam.service';
import { ProfileApiService } from '../features/profile/profile-api.service';

export const INITIAL_SONGS: readonly Song[] = [];
export const INITIAL_REVIEWS: readonly CommunityReview[] = [];

const EMPTY_SONG: Song = {
  title: '',
  artist: '',
  genre: '',
  time: '0:00',
  image: '',
  album: '',
  year: '',
  match: 0,
};

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

function getStoredTheme(fallback: 'light' | 'dark'): 'light' | 'dark' {
  try {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem('ribbit-theme');
    return raw === 'light' || raw === 'dark' ? raw : fallback;
  } catch {
    return fallback;
  }
}

function setStoredTheme(theme: 'light' | 'dark'): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('ribbit-theme', theme);
    }
  } catch {
    // Ignore storage quota errors
  }
}

interface JamDeckProgress {
  readonly cursorTrackId?: number;
  readonly seenTrackIds: readonly number[];
}

export interface GoogleOAuthQueryParams {
  readonly googleAuth: string | null;
  readonly googleAuthError: string | null;
  readonly googleOAuthStart: boolean;
}

function readGoogleOAuthQueryParams(): GoogleOAuthQueryParams | null {
  if (typeof window === 'undefined' || !window.location.search) {
    return null;
  }
  const params = new URLSearchParams(window.location.search);
  const googleAuth = params.get('google_auth');
  const googleAuthError = params.get('google_auth_error');
  const googleOAuthStart = params.get('google_oauth_start') === '1';
  if (!googleAuth && googleAuthError === null && !googleOAuthStart) {
    return null;
  }
  return { googleAuth, googleAuthError, googleOAuthStart };
}

function getJamDeckStorageKey(userId: number | null, jamId: number): string {
  return `ribbit:jam_deck:${userId ?? 'anon'}:${jamId}`;
}

function readStoredJamDeckProgress(userId: number | null, jamId: number): JamDeckProgress {
  try {
    if (typeof localStorage === 'undefined') return { seenTrackIds: [] };
    const raw = localStorage.getItem(getJamDeckStorageKey(userId, jamId));
    if (!raw) return { seenTrackIds: [] };
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) {
      return { seenTrackIds: [] };
    }
    // The parsed value is an object, so this cast is safe for reading optional known keys.
    const record = parsed as Record<string, unknown>;
    const rawCursor = record['cursorTrackId'];
    const cursorTrackId =
      typeof rawCursor === 'number' && Number.isFinite(rawCursor) ? rawCursor : undefined;
    const rawSeen = Array.isArray(record['seenTrackIds']) ? record['seenTrackIds'] : [];
    const seenTrackIds = rawSeen.filter(
      (id): id is number => typeof id === 'number' && Number.isFinite(id),
    );
    return {
      ...(cursorTrackId !== undefined ? { cursorTrackId } : {}),
      seenTrackIds,
    };
  } catch {
    // Ignore malformed localStorage Jam deck progress
    return { seenTrackIds: [] };
  }
}

function writeStoredJamDeckProgress(
  userId: number | null,
  jamId: number,
  progress: JamDeckProgress,
): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(getJamDeckStorageKey(userId, jamId), JSON.stringify(progress));
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
  private jamDeckLoadSub: Subscription | null = null;
  private jamStateSyncSub: Subscription | null = null;
  private jamSessionEpoch = 0;
  private jamStateSyncSeq = 0;
  private readonly jamConfirmedSeenTrackIds = new Set<number>();
  private serverJamSuperlikes = 0;
  private pendingJamSuperlikes = 0;
  private readonly unsubscribeUnauthorized: () => void;
  private readonly recentAccessTimestamps = new Map<string, number>();

  readonly songs = signal<readonly Song[]>(INITIAL_SONGS);
  readonly accessHistory = signal<readonly TrackAccessHistoryItem[]>([]);
  readonly seenTrackIds = signal<ReadonlySet<number>>(new Set());
  readonly discoverySong = signal<Song | null>(null);
  private readonly discoveryQueue: Song[] = [];
  private discoveryPrefetchInFlight = false;
  private readonly discoveryQueueTarget = 3;
  readonly isDeckEmpty = signal<boolean>(false);
  readonly isLoadingDiscovery = signal<boolean>(false);
  private readonly swipeUndoStack = signal<
    readonly {
      readonly song: Song;
      readonly kind: DecisionKind;
      readonly index: number;
    }[]
  >([]);
  readonly lastSwiped = computed(() => {
    const stack = this.swipeUndoStack();
    return stack[stack.length - 1] ?? null;
  });

  readonly history = signal<readonly Decision[]>([]);
  readonly likedSongs = signal<readonly Song[]>([]);
  readonly lovedSongs = signal<readonly Song[]>([]);
  readonly rejectedSongs = signal<readonly Song[]>([]);

  readonly playlists = signal<readonly Playlist[]>([]);
  readonly selectedGenres = signal<readonly string[]>(
    getStoredGenres('ribbit-genres', ['Rock', 'Pop', 'Indie']).slice(0, 3),
  );
  readonly blockedGenres = signal<readonly string[]>(this.initialUser?.blocked_genres ?? []);
  readonly blockedArtists = signal<readonly string[]>(this.initialUser?.blocked_artists ?? []);

  readonly userId = signal<number | null>(this.initialUser?.user_id ?? null);
  readonly primaryAccountId = signal<number | null>(this.initialUser?.primary_account_id ?? null);
  readonly userEmail = signal<string>(this.initialUser?.email ?? '');
  readonly userName = signal<string>(this.initialUser?.display_name ?? 'Visitante');
  readonly userAge = signal<number | null>(this.initialUser?.age ?? null);
  readonly isMinorUser = computed<boolean>(() => {
    const age = this.userAge();
    return age !== null && age < 18;
  });
  readonly currentPlanId = signal<number>(this.initialUser?.plan_id ?? 1);
  readonly currentPlan = signal<string>('Free');
  readonly isAdmin = signal<boolean>(Boolean(this.initialUser?.is_admin));
  readonly hasPaidAccess = computed<boolean>(
    () => this.isAdmin() || this.currentPlan().toLowerCase() !== 'free',
  );
  readonly hasFamilyAccess = computed<boolean>(() => {
    if (this.isAdmin()) return true;
    const planName = this.currentPlan().toLowerCase();
    return planName.includes('famíl') || planName.includes('famil');
  });
  readonly spotifyId = signal<string | null>(this.initialUser?.spotify_id ?? null);
  readonly spotifyPremium = signal<boolean>(Boolean(this.initialUser?.spotify_premium));
  readonly preferredTheme = signal<'light' | 'dark'>(
    getStoredTheme(
      this.initialUser?.preferred_theme === 'light' || this.initialUser?.preferred_theme === 'dark'
        ? this.initialUser.preferred_theme
        : 'dark',
    ),
  );
  readonly favoriteGenres = signal<readonly string[]>(this.initialUser?.favorite_genres ?? []);

  readonly toast = signal<string>('');
  readonly activePage = signal<string>('discover');
  readonly authView = signal<'app' | 'login' | 'register' | 'forgot-password'>(
    this.hasInitialToken ? 'app' : 'login',
  );
  readonly activeModal = signal<string | null>(null);
  readonly mode = signal<string>('Para você');

  readonly upgradePromptReason = signal<string>(
    'Este recurso faz parte dos planos pagos do Ribbit.',
  );
  readonly spotifyPromptReason = signal<string>(
    'Conecte sua conta do Spotify para utilizar o Pond.',
  );
  readonly pendingCheckoutPlan = signal<SubscriptionPlan | null>(null);

  readonly selectedDetailsSong = signal<Song | null>(null);
  readonly pendingCommunityReturnSong = signal<Song | null>(null);
  readonly activeTrackReviews = signal<readonly CommunityReview[]>([]);
  readonly searchQuery = signal<string>('');
  readonly searchFilterGenre = signal<string>('Todos');
  readonly searchFilterArtist = signal<string>('');
  readonly searchFilterYear = signal<number | undefined>(undefined);
  readonly searchFilterStartDate = signal<string>('');
  readonly searchFilterEndDate = signal<string>('');
  readonly searchFilterMinRating = signal<number | null>(null);
  readonly searchSortBy = signal<'default' | 'rating_desc' | 'rating_asc'>('default');
  readonly communityFeedSort = signal<ReviewSortOption>('likes');
  readonly trackReviewsSort = signal<ReviewSortOption>('recent');

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
  readonly jamDeckCursor = signal<number>(0);
  readonly jamDeckNextCursor = signal<number | null>(null);
  readonly jamDeckLoaded = signal<boolean>(false);
  readonly jamDeckLoading = signal<boolean>(false);
  readonly jamSeenTrackIds = signal<ReadonlySet<number>>(new Set());
  readonly jamSeenFallbackKeys = signal<ReadonlySet<string>>(new Set());
  readonly jamVotes = computed<number>(() => this.jamState().votes);
  readonly currentJamDeckSong = computed<Song | null>(() => {
    const jamDeck = this.jamDeckSongs();
    const cursor = this.jamDeckCursor();
    if (cursor < jamDeck.length) {
      return jamDeck[cursor] ?? null;
    }
    if (this.jamDeckLoading() || this.jamDeckNextCursor() !== null) {
      return null;
    }
    return this.findNextJamFallbackSong(jamDeck);
  });

  readonly currentIndex = signal<number>(0);

  readonly currentSong = computed<Song>(() => {
    const activeDiscovery = this.discoverySong();
    if (activeDiscovery) {
      return activeDiscovery;
    }
    const list = this.songs();
    const idx = this.currentIndex();
    return list.length > 0 ? (list[idx % list.length] ?? EMPTY_SONG) : EMPTY_SONG;
  });

  readonly detailsTargetSong = computed<Song>(
    () => this.selectedDetailsSong() ?? this.currentSong(),
  );

  readonly isSpotifyLinked = computed<boolean>(() => Boolean(this.spotifyId()));
  private pendingGoogleOAuthParams: GoogleOAuthQueryParams | null = readGoogleOAuthQueryParams();

  constructor() {
    this.applyTheme(this.preferredTheme());
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

  readonly playlistsViewReset = signal<number>(0);

  /** Requests the playlists view to return to the full playlists grid. */
  resetPlaylistsView(): void {
    this.playlistsViewReset.update((v) => v + 1);
  }

  /** Updates the currently active navigation page identifier. */
  setPage(page: string): void {
    if (page !== 'discover') {
      this.pendingCommunityReturnSong.set(null);
    }
    this.activePage.set(page);
  }

  /** Returns and clears any Google OAuth callback query parameters captured on boot. */
  consumePendingGoogleOAuthParams(): GoogleOAuthQueryParams | null {
    const pending = this.pendingGoogleOAuthParams;
    this.pendingGoogleOAuthParams = null;
    return pending;
  }

  /** Opens or closes a modal dialog, loading track reviews when opening details. */
  setModal(modal: string | null): void {
    this.activeModal.set(modal);
    if (modal === 'details') {
      const target = this.detailsTargetSong();
      if (target.trackId !== undefined) {
        this.loadReviewsForTrack(target);
        this.recordTrackAccess(target, 'details');
      }
    } else if (modal === null) {
      this.selectedDetailsSong.set(null);
    }
  }

  /** Opens the unavailable-track informational modal when a removed catalog track is opened. */
  openUnavailableTrackModal(song: Song): void {
    this.selectedDetailsSong.set(song);
    this.setModal('track-unavailable');
  }

  /** Opens the track details & reviews modal for a specific song. */
  openTrackDetailsModal(song: Song): void {
    if (song.isDeleted) {
      this.openUnavailableTrackModal(song);
      return;
    }
    this.selectedDetailsSong.set(song);
    this.setModal('details');
  }

  /** Opens a community track in Discovery swipe mode and remembers it for return to its reviews. */
  openTrackForCommunitySwipe(song: Song): boolean {
    if (song.isDeleted) {
      this.openUnavailableTrackModal(song);
      return false;
    }
    this.pendingCommunityReturnSong.set(song);
    this.discoverySong.set(song);
    this.audioPlayer.loadTrack(song.previewUrl);
    this.setPage('discover');
    return true;
  }

  /** Consumes and returns the originating community song if the swiped card matches it. */
  consumeCommunityReturnSong(swipedSong: Song): Song | null {
    const pending = this.pendingCommunityReturnSong();
    this.pendingCommunityReturnSong.set(null);
    if (!pending) return null;
    if (pending.trackId !== undefined && swipedSong.trackId !== undefined) {
      return pending.trackId === swipedSong.trackId ? pending : null;
    }
    return pending.title === swipedSong.title && pending.artist === swipedSong.artist
      ? pending
      : null;
  }

  /** Switches between authenticated shell, login, registration, and forgot-password views. */
  setAuthView(view: 'app' | 'login' | 'register' | 'forgot-password'): void {
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

    // Trigger onboarding on first access
    if (typeof localStorage !== 'undefined') {
      const email = auth.user.email;
      const seen = localStorage.getItem(`ribbit:onboarding_done:${email}`);
      if (!seen) {
        this.setModal('onboarding');
      }
    }
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

    this.refreshUserPreferences();
    this.refreshCatalogAndFeed();
    this.refreshPlaylists();
    this.refreshInteractedCollections();
    this.refreshAccessHistory();
    this.loadNextDiscoveryTrack();
  }

  /** Reloads active track access history and distinct seen track IDs from /api/profile/access-history. */
  refreshAccessHistory(): void {
    if (!readAuthToken()) return;
    this.songService
      .getUserAccessHistory(100, 0)
      .pipe(catchError(() => of(null)))
      .subscribe((res) => {
        if (res === null) return;
        this.accessHistory.set(res.items);
        this.seenTrackIds.set(new Set(res.seen_track_ids));
      });
  }

  /** Checks whether the given track ID has already been seen/listened by the user. */
  isTrackSeen(trackId?: number): boolean {
    if (trackId === undefined) return false;
    return this.seenTrackIds().has(trackId);
  }

  /** Records an explicit track access, updating seenTrackIds optimistically and deduplicating rapid clicks. */
  recordTrackAccess(song: Song, source: TrackAccessSource): void {
    const trackId = song.trackId;
    if (trackId === undefined) return;

    this.seenTrackIds.update((prev) => {
      if (prev.has(trackId)) return prev;
      const next = new Set(prev);
      next.add(trackId);
      return next;
    });

    const dedupeKey = `${String(trackId)}:${source}`;
    const now = Date.now();
    const lastRecorded = this.recentAccessTimestamps.get(dedupeKey);
    if (lastRecorded !== undefined && now - lastRecorded < 5000) {
      return;
    }
    this.recentAccessTimestamps.set(dedupeKey, now);

    if (!readAuthToken()) return;
    this.songService.recordTrackAccess(trackId, source).subscribe({
      next: () => {
        this.refreshAccessHistory();
      },
      error: () => {
        // Non-blocking telemetry: keep optimistic seen state
      },
    });
  }

  /** Synchronizes blocked genres, favorite genres, and theme preference from /api/profile/*. */
  refreshUserPreferences(): void {
    if (!readAuthToken()) return;
    forkJoin({
      blocked: this.profileApi
        .listBlockedGenres()
        .pipe(catchError(() => of<readonly string[] | null>(null))),
      favorites: this.profileApi
        .getFavoriteGenres()
        .pipe(catchError(() => of<readonly string[] | null>(null))),
      theme: this.profileApi.getTheme().pipe(catchError(() => of<string | null>(null))),
    }).subscribe(({ blocked, favorites, theme }) => {
      if (blocked !== null) {
        this.blockedGenres.set([...blocked]);
      }
      if (favorites !== null && favorites.length > 0) {
        this.favoriteGenres.set([...favorites]);
        this.selectedGenres.set([...favorites]);
        setStoredGenres('ribbit-genres', favorites);
      }
      if (theme === 'light' || theme === 'dark') {
        this.preferredTheme.set(theme);
        this.applyTheme(theme);
        setStoredTheme(theme);
      }
    });
  }

  private preloadCoverImage(url: string | undefined): void {
    if (!url || typeof Image === 'undefined') return;
    const img = new Image();
    img.src = url;
  }

  private refillDiscoveryQueue(): void {
    if (
      !readAuthToken() ||
      this.discoveryPrefetchInFlight ||
      this.discoveryQueue.length >= this.discoveryQueueTarget
    ) {
      return;
    }
    this.discoveryPrefetchInFlight = true;
    this.songService.getNextDiscoverySong().subscribe({
      next: (song) => {
        this.discoveryPrefetchInFlight = false;
        if (!song) return;
        const currentId = this.discoverySong()?.trackId;
        const alreadyQueued = this.discoveryQueue.some(
          (queued) => queued.trackId !== undefined && queued.trackId === song.trackId,
        );
        if (song.trackId !== undefined && song.trackId !== currentId && !alreadyQueued) {
          this.discoveryQueue.push(song);
          this.preloadCoverImage(song.image);
        }
        if (this.discoveryQueue.length < this.discoveryQueueTarget) {
          setTimeout(() => {
            this.refillDiscoveryQueue();
          }, 0);
        }
      },
      error: () => {
        this.discoveryPrefetchInFlight = false;
      },
    });
  }

  /** Fetches the next candidate song for the Discovery deck (using prefetched queue when ready). */
  loadNextDiscoveryTrack(resetQueue = false, autoPlay = false): void {
    if (!readAuthToken()) return;
    if (resetQueue) {
      this.discoveryQueue.length = 0;
    }
    const nextSong = this.discoveryQueue.shift();
    if (nextSong) {
      this.discoverySong.set(nextSong);
      this.isDeckEmpty.set(false);
      this.audioPlayer.loadTrack(nextSong.previewUrl);
      if (autoPlay) {
        this.audioPlayer.play();
      }
      setTimeout(() => {
        this.refillDiscoveryQueue();
      }, 0);
      return;
    }
    this.songService.getNextDiscoverySong().subscribe({
      next: (song) => {
        if (song) {
          this.discoverySong.set(song);
          this.isDeckEmpty.set(false);
          this.preloadCoverImage(song.image);
          this.audioPlayer.loadTrack(song.previewUrl);
          if (autoPlay) {
            this.audioPlayer.play();
          }
          setTimeout(() => {
            this.refillDiscoveryQueue();
          }, 0);
        } else {
          this.discoveryQueue.length = 0;
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
        .getRecentInteractedTracks(1000)
        .pipe(catchError(() => of<readonly RecentInteractedTrackApiDto[]>([]))),
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
            sortBy: this.communityFeedSort(),
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

  /** Applies and optionally persists preferred theme ('light' | 'dark'). */
  setTheme(theme: 'light' | 'dark', persist = true): void {
    this.preferredTheme.set(theme);
    this.applyTheme(theme);
    setStoredTheme(theme);
    if (persist && readAuthToken()) {
      this.profileApi.updateTheme(theme).subscribe({
        error: () => {},
      });
    }
  }

  private applyTheme(theme: 'light' | 'dark'): void {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme);
      if (document.body) {
        document.body.setAttribute('data-theme', theme);
      }
    }
  }

  /** Saves favorite genres via /api/profile/favorite-genres (maximum 3 genres). */
  saveFavoriteGenres(genres: readonly string[]): void {
    const limited = genres.slice(0, 3);
    this.favoriteGenres.set(limited);
    this.selectedGenres.set(limited);
    setStoredGenres('ribbit-genres', limited);
    if (readAuthToken()) {
      this.profileApi.updateFavoriteGenres(limited).subscribe({
        next: () => {
          this.loadNextDiscoveryTrack(true);
          this.notify('Gêneros favoritos atualizados com sucesso!');
        },
        error: (err: unknown) => {
          this.notify(toApiError(err).message);
        },
      });
    }
  }
  setPlan(planName: string): void {
    this.currentPlan.set(planName);
  }

  /** Opens the mock payment checkout modal for paid plans or downgrades to Free. */
  initiatePlanSelection(plan: SubscriptionPlan): void {
    if (this.isAdmin()) {
      this.notify('Como Administrador, você já tem acesso gratuito completo ao Plano Família.');
      return;
    }
    if (plan.name === this.currentPlan()) {
      this.notify(`Você já está no plano ${plan.displayName}.`);
      return;
    }
    if (this.isMinorUser() && plan.name !== 'Free') {
      this.notify('Somente usuários maiores de 18 anos podem assinar planos pagos.');
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

  /** Surfaces a connection notice modal directing users to /settings when Spotify connection is required. */
  promptSpotifyConnection(reason?: string): void {
    if (reason) {
      this.spotifyPromptReason.set(reason);
    }
    this.setModal('spotify-connect');
  }

  /** Links a Spotify account via POST /api/profile/link-spotify or unlinks via DELETE /api/spotify/connection. */
  toggleSpotifyLink(): void {
    const uid = this.userId();
    if (uid === null) return;
    const request$ = this.isSpotifyLinked()
      ? this.profileApi.unlinkSpotify()
      : this.profileApi.linkSpotify(`spotify_user_${uid}`);
    request$.subscribe({
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

  /** Unlinks the user's Spotify account and clears OAuth tokens. */
  unlinkSpotifyAccount(): void {
    this.profileApi.unlinkSpotify().subscribe({
      next: (updatedUser) => {
        this.applyUserDto(updatedUser);
        this.notify('Conta do Spotify desvinculada com sucesso.');
      },
      error: (err: unknown) => {
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Records a swipe decision on /api/discovery/interact and advances to the next track. */
  decide(kind: DecisionKind, autoPlayNext = true): void {
    const song = this.currentSong();
    const idx = this.currentIndex();
    const nextHistory: readonly Decision[] = [
      ...this.history().filter((item) => item.index !== idx),
      { index: idx, kind, ...(song.trackId !== undefined ? { trackId: song.trackId } : {}) },
    ];
    this.history.set(nextHistory);
    this.swipeUndoStack.update((stack) => [...stack, { song, kind, index: idx }]);
    this.applyLocalSwipeCollectionUpdate(song, kind);
    this.notifySwipeDecision(kind);

    if (song.trackId !== undefined) {
      const swipedTrackId = song.trackId;
      this.seenTrackIds.update((prev) => {
        if (prev.has(swipedTrackId)) return prev;
        const next = new Set(prev);
        next.add(swipedTrackId);
        return next;
      });
    }

    if (song.trackId !== undefined && readAuthToken()) {
      const hadQueued = this.discoveryQueue.length > 0;
      this.isLoadingDiscovery.set(true);
      if (hadQueued) {
        this.loadNextDiscoveryTrack(false, autoPlayNext);
      }
      this.songService.recordSwipe(song.trackId, kind).subscribe({
        next: () => {
          this.isLoadingDiscovery.set(false);
          if (!hadQueued) {
            this.loadNextDiscoveryTrack(false, autoPlayNext);
          } else {
            this.refillDiscoveryQueue();
          }
          this.refreshInteractedCollections();
          this.refreshAccessHistory();
        },
        error: (err: unknown) => {
          this.isLoadingDiscovery.set(false);
          this.notify(toApiError(err).message);
        },
      });
      return;
    }

    this.advanceLocalFallbackIndex(idx, nextHistory);
  }

  /** Restores the last swiped song back onto the Discovery card so the user can re-decide. */
  undo(): void {
    const stack = this.swipeUndoStack();
    const last = stack[stack.length - 1] ?? null;

    if (readAuthToken()) {
      this.songService.undoSwipe().subscribe({
        next: (res) => {
          const popped = stack[stack.length - 1] ?? null;
          if (popped) {
            this.swipeUndoStack.update((items) => items.slice(0, -1));
            this.currentIndex.set(popped.index);
          }
          const restoredSong = res.track
            ? mapTrackDtoToSong(res.track)
            : (popped?.song ?? this.songs().find((s) => s.trackId === res.track_id) ?? null);
          if (restoredSong) {
            this.discoverySong.set(restoredSong);
            this.removeSongFromLocalCollections(restoredSong);
            this.audioPlayer.loadTrack(restoredSong.previewUrl);
            this.audioPlayer.setProgress(24);
          }
          this.isDeckEmpty.set(false);
          this.isLoadingDiscovery.set(false);
          this.history.update((items) => items.slice(0, -1));
          this.refreshInteractedCollections();
          this.notify('Último swipe desfeito. Avalie a faixa novamente.');
        },
        error: (err: unknown) => {
          if (isPremiumRequiredError(err)) {
            this.promptPlanUpgrade(
              'Desfazer o último swipe é um recurso exclusivo dos planos Ribbit Pro e Família.',
            );
            return;
          }
          const apiErr = toApiError(err);
          if (apiErr.status === 404) {
            this.notify('Você ainda não fez nenhum swipe.');
            return;
          }
          this.notify(apiErr.message);
        },
      });
      return;
    }

    if (!last) {
      this.notify('Você ainda não fez nenhum swipe.');
      return;
    }

    this.currentIndex.set(last.index);
    if (last.song.trackId !== undefined) {
      this.discoverySong.set(last.song);
    }
    this.removeSongFromLocalCollections(last.song);
    this.isDeckEmpty.set(false);
    this.isLoadingDiscovery.set(false);
    this.swipeUndoStack.update((items) => items.slice(0, -1));
    this.history.update((items) => items.slice(0, -1));
    this.audioPlayer.loadTrack(last.song.previewUrl);
    this.audioPlayer.setProgress(24);
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
        trackId: song.trackId,
        newAction: targetAction,
      })
      .subscribe({
        next: () => {
          this.refreshInteractedCollections();
          if (currentKind === 'reject') {
            this.discoverySong.set(song);
            this.isDeckEmpty.set(false);
            this.isLoadingDiscovery.set(false);
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

  private createLocalMockPlaylist(
    name: string,
    durationMinutes: number | null,
    extraFilters: Omit<DeckPlaylistApiRequest, 'name' | 'duration_minutes'>,
    seedSongs: readonly Song[],
  ): Playlist {
    const refId =
      extraFilters.reference_playlist_id ??
      extraFilters.source_playlist_id ??
      extraFilters.referencePlaylistId;
    const totalDurationSeconds = computeSongsDurationSeconds(seedSongs);
    return {
      id: String(Date.now()),
      playlistId: Date.now(),
      name,
      count: seedSongs.length,
      duration: formatTotalMinutes(totalDurationSeconds),
      totalDurationSeconds,
      songs: seedSongs,
      ...(durationMinutes != null ? { maxDurationSeconds: durationMinutes * 60 } : {}),
      ...(refId ? { referencePlaylistId: refId, sourcePlaylistId: refId } : {}),
      ...(extraFilters.reference_source ? { referenceSource: extraFilters.reference_source } : {}),
      ...(extraFilters.startDate ? { startDate: extraFilters.startDate } : {}),
      ...(extraFilters.endDate ? { endDate: extraFilters.endDate } : {}),
    };
  }

  /** Creates a contextual playlist on the backend and optionally populates it with tracks. */
  createPlaylist(
    name: string,
    durationMinutes: number | null = null,
    extraFilters: Omit<DeckPlaylistApiRequest, 'name' | 'duration_minutes'> = {},
    seedSongs: readonly Song[] = [],
  ): void {
    const trimmedName = name.trim() || 'Minha nova frequência';
    if (!readAuthToken()) {
      const mockCreated = this.createLocalMockPlaylist(
        trimmedName,
        durationMinutes,
        extraFilters,
        seedSongs,
      );
      this.playlists.update((list) => [mockCreated, ...list]);
      this.notify(`Playlist "${mockCreated.name}" criada na sua biblioteca.`);
      return;
    }

    this.playlistService
      .createDeckPlaylist({
        name: trimmedName,
        ...(durationMinutes != null ? { duration_minutes: durationMinutes } : {}),
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

  private appendSongOptimistically(playlistIndex: number, playlist: Playlist, song: Song): void {
    const currentSongs = playlist.songs ?? [];
    const exists = currentSongs.some(
      (s) => (s.trackId && song.trackId && s.trackId === song.trackId) || s.title === song.title,
    );
    if (exists) return;
    const updatedSongs = [...currentSongs, song];
    const nextSeconds = computeSongsDurationSeconds(updatedSongs);
    const updated: Playlist = {
      ...playlist,
      count: updatedSongs.length,
      duration: formatTotalMinutes(nextSeconds),
      totalDurationSeconds: nextSeconds,
      songs: updatedSongs,
    };
    this.playlists.update((list) =>
      list.map((item, idx) => (idx === playlistIndex ? updated : item)),
    );
  }

  /** Adds the current (or provided) song to an existing playlist via swipe-add. */
  addSongToPlaylist(playlistIndex: number, targetSong?: Song): void {
    const playlist = this.playlists()[playlistIndex];
    const song = targetSong ?? this.currentSong();
    if (!playlist) {
      this.notify('Selecione uma playlist válida para adicionar a música.');
      return;
    }
    if (isPlaylistDurationLimitReached(playlist)) {
      this.notify(`A playlist "${playlist.name}" já atingiu o limite de duração.`);
      return;
    }

    this.appendSongOptimistically(playlistIndex, playlist, song);

    const playlistId = playlist.playlistId;
    if (playlistId && song.trackId !== undefined && readAuthToken()) {
      this.playlistService.addTrackToPlaylist(playlistId, song.trackId).subscribe({
        next: () => {
          this.refreshSinglePlaylist(playlistId);
          this.notify(`"${song.title}" adicionada a ${playlist.name}.`);
        },
        error: (err: unknown) => {
          this.notify(toApiError(err).message);
          this.refreshPlaylists();
        },
      });
      return;
    }
    this.notify(`"${song.title}" adicionada a ${playlist.name}.`);
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
        if (
          isSpotifyConnectionRequiredError(err) ||
          (!this.isSpotifyLinked() && isSpotifyError(err))
        ) {
          this.promptSpotifyConnection(toApiError(err).message);
          return;
        }
        if (isSpotifyPremiumRequiredError(err) || isSpotifyError(err)) {
          this.setModal(null);
          this.notify(toApiError(err).message);
          return;
        }
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
        if (
          isSpotifyConnectionRequiredError(err) ||
          (!this.isSpotifyLinked() && isSpotifyError(err))
        ) {
          this.promptSpotifyConnection(toApiError(err).message);
          return;
        }
        if (isSpotifyPremiumRequiredError(err) || isSpotifyError(err)) {
          this.setModal(null);
          this.notify(toApiError(err).message);
          return;
        }
        if (isPremiumRequiredError(err)) {
          this.promptPlanUpgrade(toApiError(err).message);
          return;
        }
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Attempts to reserve one room superlike optimistically before voting. */
  tryConsumeJamSuperlike(): boolean {
    const currentJam = this.jamState();
    const currentCount = currentJam.superlikesCount || 0;
    const limit = currentJam.superlikesLimit || 5;
    if (currentCount >= limit) {
      this.notify(`Limite de superlikes da sala atingido (${limit}/${limit}).`);
      return false;
    }
    if (currentJam.jamId !== undefined && readAuthToken()) {
      this.pendingJamSuperlikes += 1;
      this.recomputeJamSuperlikesCount();
    } else {
      this.jamState.set({
        ...currentJam,
        superlikesCount: currentCount + 1,
      });
    }
    return true;
  }

  /** Votes on a Jam deck card (like +1 or superlike +2) and syncs room state. */
  voteJamTrack(song: Song, action: 'reject' | 'like' | 'superlike'): void {
    const jamId = this.jamState().jamId;
    if (action === 'reject') {
      this.notify(`"${song.title}" pulada.`);
      return;
    }
    if (!jamId || song.trackId === undefined) return;
    const trackId = song.trackId;
    const requestEpoch = this.jamSessionEpoch;
    const cursorBeforeAdvance = this.jamDeckCursor();

    this.jamService.voteTrack({ jamId, trackId, action }).subscribe({
      next: () => {
        if (this.jamSessionEpoch !== requestEpoch || this.jamState().jamId !== jamId) {
          return;
        }
        if (action === 'superlike') {
          this.serverJamSuperlikes += 1;
          this.pendingJamSuperlikes = Math.max(0, this.pendingJamSuperlikes - 1);
          this.recomputeJamSuperlikesCount();
        }
        this.persistJamTrackSeen(jamId, trackId);
        const pts = action === 'superlike' ? '+2 pontos' : '+1 ponto';
        this.notify(
          `${action === 'superlike' ? 'Superlike' : 'Like'} em "${song.title}"! ${pts} na fila.`,
        );
        this.syncJamState(jamId);
      },
      error: (err: unknown) => {
        if (this.jamSessionEpoch !== requestEpoch || this.jamState().jamId !== jamId) {
          return;
        }
        this.rollbackFailedJamVote(jamId, trackId, action === 'superlike', cursorBeforeAdvance);
        this.notify(toApiError(err).message);
      },
    });
  }

  /** Registers a skip vote on the active Jam track via POST /api/jams/{id}/skip-vote. */
  voteSkipJam(): void {
    const jam = this.jamState();
    const jamId = jam.jamId;
    if (!jamId) {
      this.jamState.set({ ...jam, votes: jam.votes + 1 });
      this.notify('Seu voto para pular foi registrado.');
      return;
    }
    const activeTrackId = jam.currentTrack?.trackId;
    this.jamService.voteSkip(jamId, activeTrackId).subscribe({
      next: (res) => {
        this.jamState.update((cur) => ({
          ...cur,
          votes: res.votes,
          voteThreshold: res.threshold,
          active: res.is_active,
        }));
        this.syncJamState(jamId);
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

  /** Advances the active Jam track immediately (host only) via POST /api/jams/{id}/advance. */
  advanceJam(): void {
    const jamId = this.jamState().jamId;
    if (!jamId) return;
    this.jamService.advanceJam(jamId).subscribe({
      next: () => {
        this.syncJamState(jamId);
        this.notify('Faixa da Jam avançada pelo anfitrião.');
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

  /** Records a Jam card decision locally and advances the persistent deck cursor. */
  advanceJamDeckCursor(song: Song, persist = true): void {
    const currentCursor = this.jamDeckCursor();
    const jamDeck = this.jamDeckSongs();
    const jamId = this.jamState().jamId;

    if (song.trackId !== undefined) {
      const updatedSeen = new Set(this.jamSeenTrackIds());
      updatedSeen.add(song.trackId);
      this.jamSeenTrackIds.set(updatedSeen);

      if (persist) {
        this.jamConfirmedSeenTrackIds.add(song.trackId);
        if (jamId !== undefined) {
          this.persistJamTrackSeen(jamId, song.trackId);
        }
      }
    } else {
      const updatedFallback = new Set(this.jamSeenFallbackKeys());
      updatedFallback.add(song.title);
      this.jamSeenFallbackKeys.set(updatedFallback);
    }

    this.jamDeckCursor.set(this.findNextJamDeckCursor(currentCursor + 1, jamDeck));
  }

  private findNextJamDeckCursor(startIndex: number, jamDeck: readonly Song[]): number {
    const seenIds = this.jamSeenTrackIds();
    let idx = startIndex;
    while (idx < jamDeck.length) {
      const candidateId = jamDeck[idx]?.trackId;
      if (candidateId === undefined || !seenIds.has(candidateId)) {
        return idx;
      }
      idx += 1;
    }
    return idx;
  }

  private persistJamTrackSeen(jamId: number, trackId: number): void {
    this.jamConfirmedSeenTrackIds.add(trackId);

    const updatedSeen = new Set(this.jamSeenTrackIds());
    updatedSeen.add(trackId);
    this.jamSeenTrackIds.set(updatedSeen);

    const prev = readStoredJamDeckProgress(this.userId(), jamId);
    const cursorTrackId = this.resolveContiguousBackendCursor(prev.cursorTrackId);
    writeStoredJamDeckProgress(this.userId(), jamId, {
      ...(cursorTrackId !== undefined ? { cursorTrackId } : {}),
      seenTrackIds: Array.from(this.jamConfirmedSeenTrackIds),
    });
  }

  private resolveContiguousBackendCursor(
    prevCursorTrackId: number | undefined,
  ): number | undefined {
    let contiguousCursor = prevCursorTrackId;
    for (const song of this.jamDeckSongs()) {
      if (song.trackId === undefined || !this.jamConfirmedSeenTrackIds.has(song.trackId)) {
        break;
      }
      contiguousCursor = song.trackId;
    }
    return contiguousCursor;
  }

  private recomputeJamSuperlikesCount(): void {
    const currentJam = this.jamState();
    const limit = currentJam.superlikesLimit ?? 5;
    const effectiveSuperlikes = Math.min(
      limit,
      this.serverJamSuperlikes + this.pendingJamSuperlikes,
    );
    this.jamState.set({
      ...currentJam,
      superlikesCount: effectiveSuperlikes,
    });
  }

  private rollbackFailedJamVote(
    jamId: number,
    trackId: number,
    wasSuperlike: boolean,
    cursorBeforeAdvance: number,
  ): void {
    if (wasSuperlike) {
      this.pendingJamSuperlikes = Math.max(0, this.pendingJamSuperlikes - 1);
      this.recomputeJamSuperlikesCount();
      this.syncJamState(jamId);
    }
    const updatedSeen = new Set(this.jamSeenTrackIds());
    updatedSeen.delete(trackId);
    this.jamSeenTrackIds.set(updatedSeen);
    if (this.jamDeckCursor() > cursorBeforeAdvance) {
      this.jamDeckCursor.set(cursorBeforeAdvance);
    }
  }

  /** Closes the active Jam room (for hosts) or leaves the room locally. */
  closeOrLeaveJam(): void {
    const jam = this.jamState();
    this.stopJamPolling();
    const jamId = jam.jamId ?? jam.roomId;
    const isHost = Boolean(jamId && jam.hostUserId === this.userId());
    this.jamState.set(DEFAULT_JAM_STATE);
    this.resetJamDeckState();
    if (isHost && jamId !== undefined) {
      this.jamService.closeJam(jamId).subscribe({
        next: () => {
          this.notify('Jam encerrada para todos os participantes.');
        },
        error: () => {
          // Room state already cleared locally
        },
      });
      return;
    }
    this.notify('Você saiu da Jam.');
  }

  /** Toggles Jam active flag locally when needed. */
  setJamActive(active: boolean): void {
    this.jamState.set({ ...this.jamState(), active });
    if (!active) {
      this.stopJamPolling();
    }
  }

  /** Reloads community reviews feed with the specified or active sort order. */
  loadCommunityFeed(sortBy?: ReviewSortOption): void {
    if (sortBy) {
      this.communityFeedSort.set(sortBy);
    }
    if (!readAuthToken()) return;
    const lookup = this.buildTrackLookup(this.songs());
    this.songService
      .loadCommunityFeed({
        trackLookup: lookup,
        currentUserId: this.userId() ?? undefined,
        currentUserName: this.userName(),
        sortBy: this.communityFeedSort(),
      })
      .pipe(catchError(() => of([])))
      .subscribe();
  }

  /** Resets all search query and filter signals to their defaults. */
  clearSearchFilters(): void {
    this.searchQuery.set('');
    this.searchFilterGenre.set('Todos');
    this.searchFilterArtist.set('');
    this.searchFilterYear.set(undefined);
    this.searchFilterStartDate.set('');
    this.searchFilterEndDate.set('');
    this.searchFilterMinRating.set(null);
    this.searchSortBy.set('default');
  }

  /** Loads reviews for a specific track into activeTrackReviews. */
  loadReviewsForTrack(song: Song, sortBy?: ReviewSortOption): void {
    if (sortBy) {
      this.trackReviewsSort.set(sortBy);
    }
    if (song.trackId === undefined) return;
    this.songService
      .getTrackReviews({
        trackId: song.trackId,
        track: song,
        currentUserId: this.userId() ?? undefined,
        currentUserName: this.userName(),
        sortBy: this.trackReviewsSort(),
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

  /** Persists favorite genres locally for UI recommendations context (maximum 3 genres). */
  setSelectedGenres(genres: readonly string[]): void {
    const limited = genres.slice(0, 3);
    this.selectedGenres.set(limited);
    setStoredGenres('ribbit-genres', limited);
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

  applyUserDto(user: UserApiDto): void {
    writeStoredUser(user);
    this.userId.set(user.user_id);
    this.primaryAccountId.set(user.primary_account_id ?? null);
    this.userEmail.set(user.email);
    this.userName.set(user.display_name);
    this.userAge.set(user.age ?? null);
    this.currentPlanId.set(user.plan_id);
    this.isAdmin.set(Boolean(user.is_admin));
    this.spotifyId.set(user.spotify_id ?? null);
    this.spotifyPremium.set(Boolean(user.spotify_premium));
    this.applyUserPreferencesFromDto(user);
  }

  private applyUserPreferencesFromDto(user: UserApiDto): void {
    this.blockedGenres.set(user.blocked_genres ? [...user.blocked_genres] : []);
    this.blockedArtists.set(user.blocked_artists ? [...user.blocked_artists] : []);
    if (user.preferred_theme === 'light' || user.preferred_theme === 'dark') {
      this.preferredTheme.set(user.preferred_theme);
      this.applyTheme(user.preferred_theme);
      setStoredTheme(user.preferred_theme);
    }
    if (user.favorite_genres && user.favorite_genres.length > 0) {
      this.favoriteGenres.set([...user.favorite_genres]);
      this.selectedGenres.set([...user.favorite_genres]);
    }
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

  private removeSongFromLocalCollections(song: Song): void {
    const notSame = (item: Song): boolean =>
      song.trackId !== undefined ? item.trackId !== song.trackId : item.title !== song.title;

    this.likedSongs.update((list) => list.filter((item) => notSame(item)));
    this.lovedSongs.update((list) => list.filter((item) => notSame(item)));
    this.rejectedSongs.update((list) => list.filter((item) => notSame(item)));
  }

  private applyLocalSwipeCollectionUpdate(song: Song, kind: DecisionKind): void {
    const notSame = (item: Song): boolean =>
      song.trackId !== undefined ? item.trackId !== song.trackId : item.title !== song.title;

    this.likedSongs.update((list) =>
      kind === 'reject'
        ? list.filter((item) => notSame(item))
        : [song, ...list.filter((item) => notSame(item))],
    );
    this.lovedSongs.update((list) =>
      kind === 'love'
        ? [song, ...list.filter((item) => notSame(item))]
        : list.filter((item) => notSame(item)),
    );
    this.rejectedSongs.update((list) =>
      kind === 'reject'
        ? [song, ...list.filter((item) => notSame(item))]
        : list.filter((item) => notSame(item)),
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
      (s, i) =>
        i > idx &&
        !blocked.some((b) => matchesGenreFilter(s.genre, b)) &&
        !nextHistory.some((h) => h.index === i),
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
      ...(jamId != null ? { jamId, roomId: jamId } : {}),
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
      deckSource:
        jamDto.deck_source === 'curtidas' || jamDto.deck_source === 'playlist'
          ? jamDto.deck_source
          : 'livre',
      ...(jamDto.source_playlist_id != null ? { sourcePlaylistId: jamDto.source_playlist_id } : {}),
      queueItems: [],
    });

    this.resetJamDeckState();
    this.serverJamSuperlikes = jamDto.superlikes_used ?? 0;

    if (jamId != null) {
      const saved = readStoredJamDeckProgress(this.userId(), jamId);
      this.jamSeenTrackIds.set(new Set(saved.seenTrackIds));
      for (const id of saved.seenTrackIds) {
        this.jamConfirmedSeenTrackIds.add(id);
      }
      this.loadJamDeck(jamId, saved.cursorTrackId, false);
      this.syncJamState(jamId);
      this.startJamPolling(jamId);
    }
  }

  loadJamDeck(jamId: number, cursorId?: number, append = Boolean(cursorId)): void {
    if (append && this.jamDeckLoading()) {
      return;
    }
    if (!append) {
      this.jamDeckLoadSub?.unsubscribe();
      this.jamDeckLoadSub = null;
    }
    const requestEpoch = this.jamSessionEpoch;
    this.jamDeckLoading.set(true);
    this.jamDeckLoadSub = this.jamService.getJamDeck(jamId, 30, cursorId).subscribe({
      next: (page) => {
        if (this.jamSessionEpoch !== requestEpoch || this.jamState().jamId !== jamId) {
          return;
        }
        this.jamDeckLoading.set(false);
        this.jamDeckLoaded.set(true);
        const songs = this.filterUnseenJamSongs(page.items.map((dto) => mapTrackDtoToSong(dto)));
        this.applyJamDeckPage(songs, append);
        const nextCursor = page.next_cursor ?? null;
        this.jamDeckNextCursor.set(nextCursor);
        if (songs.length === 0 && nextCursor !== null && nextCursor !== cursorId) {
          this.loadJamDeck(jamId, nextCursor, append);
        }
      },
      error: () => {
        if (this.jamSessionEpoch !== requestEpoch || this.jamState().jamId !== jamId) {
          return;
        }
        this.jamDeckLoading.set(false);
        this.jamDeckNextCursor.set(null);
        if (!append) {
          this.jamDeckLoaded.set(true);
          this.jamDeckSongs.set([]);
          this.jamDeckCursor.set(0);
        }
      },
    });
  }

  private filterUnseenJamSongs(songs: readonly Song[]): Song[] {
    const seenIds = this.jamSeenTrackIds();
    return songs.filter((song) => song.trackId === undefined || !seenIds.has(song.trackId));
  }

  private applyJamDeckPage(songs: readonly Song[], append: boolean): void {
    if (!append) {
      this.jamDeckSongs.set(songs);
      this.jamDeckCursor.set(0);
      return;
    }
    this.jamDeckSongs.update((cur) => {
      const existingIds = new Set(
        cur.map((item) => item.trackId).filter((id): id is number => id !== undefined),
      );
      const uniqueNew = songs.filter(
        (song) => song.trackId === undefined || !existingIds.has(song.trackId),
      );
      return [...cur, ...uniqueNew];
    });
  }

  private findNextJamFallbackSong(jamDeck: readonly Song[]): Song | null {
    const jam = this.jamState();
    const excludedIds = this.buildJamExcludedTrackIds(jam, jamDeck);
    const blocked = this.blockedGenres();
    const requireTrackId = jam.jamId !== undefined && Boolean(readAuthToken());
    const seenKeys = this.jamSeenFallbackKeys();

    return (
      this.songs().find((song) => {
        if (blocked.some((b) => matchesGenreFilter(song.genre, b))) {
          return false;
        }
        if (song.trackId !== undefined) {
          return !excludedIds.has(song.trackId);
        }
        return !requireTrackId && !seenKeys.has(song.title);
      }) ?? null
    );
  }

  private buildJamExcludedTrackIds(jam: JamState, jamDeck: readonly Song[]): Set<number> {
    const excludedIds = new Set<number>(this.jamSeenTrackIds());
    if (jam.currentTrack?.trackId !== undefined) {
      excludedIds.add(jam.currentTrack.trackId);
    }
    for (const item of jam.queueItems ?? []) {
      if (item.song.trackId !== undefined) {
        excludedIds.add(item.song.trackId);
      }
    }
    for (const deckSong of jamDeck) {
      if (deckSong.trackId !== undefined) {
        excludedIds.add(deckSong.trackId);
      }
    }
    return excludedIds;
  }

  private resetJamDeckState(): void {
    this.jamSessionEpoch += 1;
    this.jamStateSyncSeq += 1;
    this.jamDeckLoadSub?.unsubscribe();
    this.jamDeckLoadSub = null;
    this.jamStateSyncSub?.unsubscribe();
    this.jamStateSyncSub = null;
    this.jamConfirmedSeenTrackIds.clear();
    this.serverJamSuperlikes = 0;
    this.pendingJamSuperlikes = 0;
    this.jamDeckSongs.set([]);
    this.jamDeckCursor.set(0);
    this.jamDeckNextCursor.set(null);
    this.jamDeckLoaded.set(false);
    this.jamDeckLoading.set(false);
    this.jamSeenTrackIds.set(new Set());
    this.jamSeenFallbackKeys.set(new Set());
  }

  private syncJamState(jamId: number): void {
    this.jamStateSyncSub?.unsubscribe();
    this.jamStateSyncSeq += 1;
    const requestEpoch = this.jamSessionEpoch;
    const syncSeq = this.jamStateSyncSeq;
    this.jamStateSyncSub = this.jamService.getJamState(jamId).subscribe({
      next: (stateDto) => {
        if (
          this.jamSessionEpoch !== requestEpoch ||
          this.jamStateSyncSeq !== syncSeq ||
          this.jamState().jamId !== jamId
        ) {
          return;
        }
        const lookup = this.buildTrackLookup([...this.songs(), ...this.jamDeckSongs()]);
        const mapped = mapJamStateDto({
          dto: stateDto,
          trackLookup: lookup,
          fallbackSong: this.currentSong(),
        });
        this.serverJamSuperlikes = mapped.superlikesCount ?? 0;
        const limit =
          mapped.superlikesLimit ?? this.serverJamSuperlikes + this.pendingJamSuperlikes;
        const effectiveSuperlikes = Math.min(
          limit,
          this.serverJamSuperlikes + this.pendingJamSuperlikes,
        );
        this.jamState.set({ ...mapped, superlikesCount: effectiveSuperlikes });
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
    this.accessHistory.set([]);
    this.seenTrackIds.set(new Set());
    this.recentAccessTimestamps.clear();
    this.playlists.set([]);
    this.activeTrackReviews.set([]);
    this.pendingCommunityReturnSong.set(null);
    this.discoveryQueue.length = 0;
    this.discoverySong.set(null);
    this.swipeUndoStack.set([]);
    this.isDeckEmpty.set(false);
    this.isLoadingDiscovery.set(false);
    this.jamState.set(DEFAULT_JAM_STATE);
    this.resetJamDeckState();
    this.userId.set(null);
    this.userEmail.set('');
    this.userName.set('Visitante');
    this.userAge.set(null);
    this.currentPlan.set('Free');
    this.currentPlanId.set(1);
    this.isAdmin.set(false);
    this.spotifyId.set(null);
    this.blockedGenres.set([]);
    this.blockedArtists.set([]);
    this.activeModal.set(null);
  }
}
