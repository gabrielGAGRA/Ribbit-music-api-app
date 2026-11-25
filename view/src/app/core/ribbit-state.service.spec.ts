import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import type {
  AuthApiResponse,
  PlanApiDto,
  PlaylistApiDto,
  SubscriptionPlan,
  TrackApiDto,
} from '@ribbit/shared-types';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { authInterceptor } from './auth.interceptor';
import { RibbitStateService } from './ribbit-state.service';

const SAMPLE_TRACK: TrackApiDto = {
  track_id: 101,
  title: 'Luzes da Avenida',
  artist: 'Terno Rei',
  album: 'Gêmeos',
  genre: 'Indie',
  duration_seconds: 215,
  release_year: 2022,
  cover_url: null,
  itunes_preview_url: 'https://cdn.ribbit.test/preview-101.mp3',
  country: 'BR',
  explicit: false,
  is_deleted: false,
};

const SAMPLE_PLANS: readonly PlanApiDto[] = [
  { plan_id: 1, name: 'Free', monthly_price: 0, max_profiles: 1 },
  { plan_id: 2, name: 'Individual', monthly_price: 14.9, max_profiles: 1 },
  { plan_id: 3, name: 'Família', monthly_price: 27.9, max_profiles: 6 },
];

const SAMPLE_AUTH: AuthApiResponse = {
  access_token: 'jwt-test-token',
  token_type: 'bearer',
  user: {
    user_id: 7,
    email: 'mateus@ribbit.app',
    display_name: 'Mateus',
    age: 26,
    spotify_id: null,
    plan_id: 1,
    blocked_genres: [],
    is_admin: false,
  },
};

function flushInitialHydration(httpMock: HttpTestingController): void {
  httpMock.expectOne('/api/plans').flush(SAMPLE_PLANS);
  httpMock.expectOne('/api/profile/me').flush({
    user: SAMPLE_AUTH.user,
    plan: SAMPLE_PLANS[0]!,
  });
  httpMock.expectOne('/api/profile/blocked-genres').flush([]);
  httpMock.expectOne('/api/profile/favorite-genres').flush(['Indie']);
  httpMock.expectOne('/api/profile/theme').flush('dark');
  httpMock.expectOne('/api/tracks/search?limit=50').flush([SAMPLE_TRACK]);
  httpMock.expectOne('/api/reviews/feed?limit=20&days=1&sort_by=likes').flush([]);
  httpMock.expectOne('/api/playlists').flush([]);
  httpMock.expectOne('/api/reviews/recent-interacted?limit=1000').flush([]);
  httpMock.expectOne('/api/profile/interactions').flush([]);
  httpMock.expectOne('/api/profile/access-history?limit=100&offset=0').flush({
    items: [],
    seen_track_ids: [],
  });
  httpMock.expectOne('/api/discovery/next').flush(SAMPLE_TRACK);
}

describe('RibbitStateService', () => {
  let service: RibbitStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(RibbitStateService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    service.ngOnDestroy();
    httpMock.verify();
    localStorage.clear();
  });

  it('starts on login view when no token is stored in localStorage', () => {
    expect(service.authView()).toBe('login');
    expect(service.songs()).toEqual([]);
    expect(service.currentPlan()).toBe('Free');
  });

  it('hydrates authenticated session after completeAuthentication and loads discovery track', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    expect(service.authView()).toBe('app');
    expect(service.userName()).toBe('Mateus');

    flushInitialHydration(httpMock);
    expect(service.discoverySong()?.title).toBe('Luzes da Avenida');
    expect(service.isDeckEmpty()).toBe(false);
  });

  it('records swipe decisions via /api/discovery/interact and supports undo()', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    service.decide('love');
    expect(service.toast()).toContain('favorita');
    expect(service.lovedSongs().length).toBe(1);

    const interactReq = httpMock.expectOne('/api/discovery/interact');
    expect(interactReq.request.method).toBe('POST');
    expect(interactReq.request.body).toEqual({ track_id: 101, action: 'superlike' });
    interactReq.flush({
      interaction_id: 1,
      user_id: 7,
      track_id: 101,
      action: 'superlike',
      created_at: '2026-01-01T12:00:00Z',
    });

    httpMock.expectOne('/api/discovery/next').flush(null);
    httpMock.expectOne('/api/reviews/recent-interacted?limit=1000').flush([
      {
        interaction: {
          interaction_id: 1,
          user_id: 7,
          track_id: 101,
          action: 'superlike',
          created_at: '2026-01-01T12:00:00Z',
        },
        track: SAMPLE_TRACK,
      },
    ]);
    httpMock.expectOne('/api/profile/interactions').flush([]);
    expect(service.isLoadingDiscovery()).toBe(false);
    httpMock.expectOne('/api/profile/access-history?limit=100&offset=0').flush({
      items: [],
      seen_track_ids: [101],
    });
    expect(service.isDeckEmpty()).toBe(true);

    service.undo();
    const undoReq = httpMock.expectOne('/api/discovery/undo');
    expect(undoReq.request.method).toBe('POST');
    undoReq.flush({
      interaction_id: 1,
      track_id: 101,
      action: 'superlike',
      created_at: '2026-01-01T12:00:00Z',
    });
    httpMock.expectOne('/api/reviews/recent-interacted?limit=1000').flush([]);
    httpMock.expectOne('/api/profile/interactions').flush([]);

    expect(service.isDeckEmpty()).toBe(false);
    expect(service.discoverySong()?.trackId).toBe(101);
    expect(service.toast()).toContain('desfeito');
  });

  it('opens upgrade modal when undo returns 403 on Free plan', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    service.decide('love');
    expect(service.isLoadingDiscovery()).toBe(true);
    const interactReq = httpMock.expectOne('/api/discovery/interact');
    interactReq.flush({
      interaction_id: 1,
      user_id: 7,
      track_id: 101,
      action: 'superlike',
      created_at: '2026-01-01T12:00:00Z',
    });
    httpMock.expectOne('/api/discovery/next').flush(null);
    httpMock.expectOne('/api/reviews/recent-interacted?limit=1000').flush([]);
    httpMock.expectOne('/api/profile/interactions').flush([]);
    httpMock.expectOne('/api/profile/access-history?limit=100&offset=0').flush({
      items: [],
      seen_track_ids: [101],
    });

    service.undo();
    const undoReq = httpMock.expectOne('/api/discovery/undo');
    undoReq.flush(
      { detail: 'Feature exclusive to Premium subscribers.' },
      { status: 403, statusText: 'Forbidden' },
    );

    expect(service.activeModal()).toBe('upgrade');
    expect(service.upgradePromptReason()).toContain('Desfazer');
  });

  it('opens upgrade modal when updating blocked genres returns 403 on Free plan', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    service.setBlockedGenres(['Funk']);
    const req = httpMock.expectOne('/api/profile/blocked-genres');
    expect(req.request.method).toBe('PUT');
    req.flush(
      { detail: 'Blocking genres requires a paid subscription plan.' },
      { status: 403, statusText: 'Forbidden' },
    );

    expect(service.blockedGenres()).toEqual([]);
    expect(service.activeModal()).toBe('upgrade');
  });

  it('opens mock checkout modal for paid plans and calls PUT /api/profile/plan on confirmation', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    const proPlan: SubscriptionPlan = {
      planId: 2,
      name: 'Individual',
      displayName: 'Ribbit Pro',
      price: 'R$ 14,90',
      copy: 'Sua experiência completa.',
      featured: true,
      features: ['Swipes ilimitados'],
    };

    service.initiatePlanSelection(proPlan);
    expect(service.activeModal()).toBe('checkout');
    expect(service.pendingCheckoutPlan()?.name).toBe('Individual');

    service.confirmMockPlanCheckout('pix');
    const req = httpMock.expectOne('/api/profile/plan');
    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual({ new_plan_id: 2 });
    req.flush({ ...SAMPLE_AUTH.user, plan_id: 2 });

    expect(service.currentPlan()).toBe('Individual');
    expect(service.activeModal()).toBeNull();
    expect(service.toast()).toContain('PIX');
  });

  it('creates playlists, manages temporary queue, handles jam skip votes, and deletes account', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    service.createPlaylist('Noite Indie', 45, {
      reference_playlist_id: 12,
      source_playlist_id: 12,
    });
    const playlistReq = httpMock.expectOne('/api/playlists/deck');
    expect(playlistReq.request.method).toBe('POST');
    expect(playlistReq.request.body).toEqual({
      name: 'Noite Indie',
      duration_minutes: 45,
      source_playlist_id: 12,
    });
    const createdPlaylist: PlaylistApiDto = {
      playlist_id: 50,
      user_id: 7,
      name: 'Noite Indie',
      description: null,
      max_duration_seconds: 2700,
      is_exported: false,
      spotify_playlist_id: null,
      total_duration_seconds: 0,
      tracks: [],
    };
    playlistReq.flush(createdPlaylist);
    expect(service.playlists().some((p) => p.name === 'Noite Indie')).toBe(true);

    service.createPlaylist('Sem Limite Padrão', null, { reference_source: 'amadas' });
    const noDurationReq = httpMock.expectOne('/api/playlists/deck');
    expect(noDurationReq.request.body).toEqual({
      name: 'Sem Limite Padrão',
      reference_source: 'amadas',
    });
    noDurationReq.flush({
      playlist_id: 51,
      user_id: 7,
      name: 'Sem Limite Padrão',
      description: null,
      max_duration_seconds: null,
      is_exported: false,
      spotify_playlist_id: null,
      total_duration_seconds: 0,
      deck_filters: '{"reference_source":"amadas"}',
      tracks: [],
    });
    const createdNoLimit = service.playlists().find((p) => p.playlistId === 51);
    expect(createdNoLimit?.duration).toBe('0 min');
    expect(createdNoLimit?.maxDurationSeconds).toBeUndefined();
    expect(createdNoLimit?.referenceSource).toBe('amadas');

    service.decideQueue(true);
    expect(service.queue().length).toBe(1);

    service.voteSkipJam();
    expect(service.jamVotes()).toBe(1);

    service.deleteAccount();
    const deleteReq = httpMock.expectOne('/api/profile/account');
    expect(deleteReq.request.method).toBe('DELETE');
    deleteReq.flush(null, { status: 204, statusText: 'No Content' });
    expect(service.authView()).toBe('register');

    service.setAuthView('forgot-password');
    expect(service.authView()).toBe('forgot-password');
    service.setAuthView('login');
    expect(service.authView()).toBe('login');
  });

  it('initializes and toggles theme, persisting to localStorage and applying data-theme attribute', () => {
    service.setTheme('light');
    expect(service.preferredTheme()).toBe('light');
    expect(localStorage.getItem('ribbit-theme')).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    service.setTheme('dark');
    expect(service.preferredTheme()).toBe('dark');
    expect(localStorage.getItem('ribbit-theme')).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');

    // Clean up lifecycle
    service.ngOnDestroy();
  });

  it('records track access optimistically, deduplicates within 5s, and exposes isTrackSeen()', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    const song = {
      trackId: 101,
      title: 'Luzes da Avenida',
      artist: 'Terno Rei',
      genre: 'Indie',
      time: '3:35',
      image: '',
      album: 'Gêmeos',
      year: '2022',
      match: 95,
    };

    expect(service.isTrackSeen(101)).toBe(false);
    service.recordTrackAccess(song, 'play');
    expect(service.isTrackSeen(101)).toBe(true);

    // Second call with same (trackId, source) within 5s should be deduplicated
    service.recordTrackAccess(song, 'play');

    const accessReq = httpMock.expectOne('/api/tracks/101/access');
    expect(accessReq.request.method).toBe('POST');
    expect(accessReq.request.body).toEqual({ source: 'play' });
    accessReq.flush({ access_id: 1, user_id: 7, track_id: 101, source: 'play' });

    httpMock.expectOne('/api/profile/access-history?limit=100&offset=0').flush({
      items: [],
      seen_track_ids: [101],
    });
  });

  it('restores undone track from POST /api/discovery/undo even when local undo stack is empty', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    service.undo();

    const undoReq = httpMock.expectOne('/api/discovery/undo');
    expect(undoReq.request.method).toBe('POST');
    undoReq.flush({
      success: true,
      interaction_id: 99,
      track_id: 101,
      action: 'like',
      created_at: '2026-01-01T12:00:00Z',
      track: {
        track_id: 101,
        title: 'Luzes da Avenida',
        artist: 'Terno Rei',
        album: 'Gêmeos',
        duration_seconds: 215,
        genre: 'Indie',
        release_year: 2022,
        explicit: false,
      },
    });
    httpMock.expectOne('/api/reviews/recent-interacted?limit=1000').flush([]);
    httpMock.expectOne('/api/profile/interactions').flush([]);

    expect(service.discoverySong()?.trackId).toBe(101);
    expect(service.discoverySong()?.title).toBe('Luzes da Avenida');
    expect(service.isDeckEmpty()).toBe(false);
  });

  it('triggers upgrade modal when Free user calls undo() before any local swipe', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    service.undo();

    const undoReq = httpMock.expectOne('/api/discovery/undo');
    undoReq.flush({ detail: 'Premium required' }, { status: 403, statusText: 'Forbidden' });

    expect(service.activeModal()).toBe('upgrade');
  });

  it('blocks paid plan selection (Family and Individual) for minor users', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);
    service.applyUserDto({
      ...SAMPLE_AUTH.user,
      age: 15,
    });
    service.setModal(null);

    service.initiatePlanSelection({
      planId: 3,
      name: 'Família',
      displayName: 'Ribbit Família',
      price: 'R$ 27,90',
      maxProfiles: 4,
      copy: '',
      features: [],
    });
    expect(service.activeModal()).toBeNull();
    expect(service.toast()).toContain('Somente usuários maiores de 18 anos');

    service.initiatePlanSelection({
      planId: 2,
      name: 'Individual',
      displayName: 'Ribbit Pro',
      price: 'R$ 14,90',
      maxProfiles: 1,
      copy: '',
      features: [],
    });
    expect(service.activeModal()).toBeNull();
    expect(service.toast()).toContain('Somente usuários maiores de 18 anos');
  });

  it('handles UI navigation, modals, filters, theme, toast, and logout state transitions', () => {
    service.setPage('explore');
    expect(service.activePage()).toBe('explore');

    service.setModal('upgrade');
    expect(service.activeModal()).toBe('upgrade');
    service.setModal(null);

    service.setTheme('light', false);
    expect(service.preferredTheme()).toBe('light');
    service.setTheme('dark', false);
    expect(service.preferredTheme()).toBe('dark');

    service.notify('Olá Ribbit');
    expect(service.toast()).toBe('Olá Ribbit');

    service.logout();
    expect(service.authView()).toBe('login');
    expect(service.userId()).toBeNull();
  });

  it('manages selected/blocked genres, community return song, unavailable modal, and jam active state', () => {
    const song = {
      trackId: 202,
      title: 'Test',
      artist: 'Artist',
      genre: 'Pop',
      time: '3:00',
      image: '',
      album: 'Album',
      year: '2024',
      match: 90,
    };

    service.setSelectedGenres(['Pop', 'Indie']);
    expect(service.selectedGenres()).toEqual(['Pop', 'Indie']);

    service.setBlockedGenres(['Metal']);
    expect(service.blockedGenres()).toEqual(['Metal']);

    service.openUnavailableTrackModal(song);
    expect(service.activeModal()).toBe('track-unavailable');
    service.setModal(null);

    service.openTrackDetailsModal(song);
    httpMock.expectOne('/api/reviews/track/202?sort_by=recent').flush([]);
    expect(service.activeModal()).toBe('details');
    service.setModal(null);

    expect(service.openTrackForCommunitySwipe(song)).toBe(true);
    expect(service.consumeCommunityReturnSong(song)).toEqual(song);

    service.setJamActive(true);
    expect(service.jamState().active).toBe(true);
    service.setJamActive(false);

    service.clearSearchFilters();
    service.resetPlaylistsView();
    service.clearToast();
    expect(service.toast()).toBe('');
  });

  it('handles plan/spotify prompts, favorite genres, profile name, and playlist/review mutations', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    service.promptPlanUpgrade('Recurso Pro');
    expect(service.activeModal()).toBe('upgrade');
    service.setModal(null);

    service.promptSpotifyConnection('Conecte');
    expect(service.activeModal()).toBe('spotify-connect');
    service.setModal(null);

    service.setPlan('Individual');
    expect(service.currentPlan()).toBe('Individual');

    service.setUserName('Mateus Silva');
    httpMock
      .expectOne('/api/profile/me')
      .flush({ ...SAMPLE_AUTH.user, display_name: 'Mateus Silva' });
    expect(service.userName()).toBe('Mateus Silva');

    service.saveFavoriteGenres(['Rock', 'Jazz']);
    httpMock.expectOne('/api/profile/favorite-genres').flush({
      ...SAMPLE_AUTH.user,
      favorite_genres: ['Rock', 'Jazz'],
    });
    httpMock.expectOne('/api/discovery/next').flush(SAMPLE_TRACK);
    expect(service.favoriteGenres()).toEqual(['Rock', 'Jazz']);

    service.loadCommunityFeed('recent');
    httpMock.expectOne('/api/reviews/feed?limit=20&days=1&sort_by=recent').flush([]);

    service.publishTrackReview(5, 'Ótima faixa');
    httpMock.expectOne('/api/reviews').flush({
      review_id: 300,
      user_id: 7,
      track_id: 101,
      rating: 5,
      text: 'Ótima faixa',
      likes_count: 0,
      is_deleted: false,
    });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    service.deleteTrackReview(300);
    httpMock.expectOne('/api/reviews/300').flush({ success: true });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    service.unlinkSpotifyAccount();
    httpMock.expectOne('/api/spotify/connection').flush({ ...SAMPLE_AUTH.user, spotify_id: null });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });
  });

  it('revises collection items, manages playlists/queue, and toggles spotify link', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    const song = {
      trackId: 101,
      title: 'Luzes da Avenida',
      artist: 'Terno Rei',
      genre: 'Indie',
      time: '3:35',
      image: '',
      album: 'Gêmeos',
      year: '2022',
      match: 95,
    };

    service.likedSongs.set([song]);
    service.reviseCollectionItem(song, 'like');
    httpMock.expectOne('/api/profile/interaction').flush({
      interaction_id: 1,
      user_id: 7,
      track_id: 101,
      action: 'dislike',
    });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    service.lovedSongs.set([song]);
    service.reviseCollectionItem(song, 'love');
    httpMock.expectOne('/api/profile/interaction').flush({
      interaction_id: 1,
      user_id: 7,
      track_id: 101,
      action: 'like',
    });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    service.rejectedSongs.set([song]);
    service.reviseCollectionItem(song, 'reject');
    httpMock.expectOne('/api/profile/interaction').flush({
      interaction_id: 1,
      user_id: 7,
      track_id: 101,
      action: 'like',
    });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    const pl = {
      id: '10',
      playlistId: 10,
      name: 'Mix',
      count: 1,
      duration: '3 min',
      isExported: false,
      songs: [song],
    };
    service.playlists.set([pl]);
    service.addSongToPlaylist(0, song);
    httpMock.expectOne('/api/playlists/10/swipe-add').flush({ success: true, message: 'ok' });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    service.removeTrackFromPlaylist(10, 101, 'Mix');
    httpMock.expectOne('/api/playlists/10/tracks/101').flush({ success: true, message: 'ok' });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    service.deletePlaylist(pl);
    httpMock.expectOne('/api/playlists/10').flush({ success: true, message: 'ok' });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    service.toggleSpotifyLink();
    httpMock.expectOne('/api/profile/link-spotify').flush({
      ...SAMPLE_AUTH.user,
      spotify_id: 'sp-1',
    });
    expect(service.spotifyId()).toBe('sp-1');
  });

  it('creates, joins, votes, advances, saves queue, and closes a Jam room', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    const jamStatePayload = {
      jam: {
        jam_id: 50,
        host_user_id: 7,
        room_name: 'My Jam',
        room_code: 'MYJAM50',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 2,
        superlikes_used: 0,
        skip_votes_threshold: 2,
        accumulated_duration_seconds: 0,
        deck_source: 'livre',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    };

    service.createJamRoom({ room_name: 'My Jam', duration_minutes: 60, skip_votes_threshold: 2 });
    httpMock.expectOne('/api/jams').flush(jamStatePayload.jam);
    httpMock.match('/api/jams/50/state').forEach((r) => {
      r.flush(jamStatePayload);
    });
    httpMock.match('/api/jams/50/deck?limit=30').forEach((r) => {
      r.flush({ items: [], next_cursor: null, has_more: false });
    });

    service.advanceJam();
    httpMock.expectOne('/api/jams/50/advance').flush(jamStatePayload);

    const qSong = {
      trackId: 101,
      title: 'Luzes da Avenida',
      artist: 'Terno Rei',
      genre: 'Indie',
      time: '3:35',
      image: '',
      album: 'Gêmeos',
      year: '2022',
      match: 95,
    };
    service.saveJamQueueSong(qSong);
    httpMock.expectOne('/api/jams/50/save-queue-track').flush({ success: true, message: 'ok' });
    httpMock
      .match((req) => req.url.includes('/state'))
      .forEach((r) => {
        r.flush(jamStatePayload);
      });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });

    service.closeOrLeaveJam();
    httpMock.expectOne('/api/jams/50/close').flush({
      ...jamStatePayload.jam,
      is_active: false,
    });
    httpMock
      .match((req) => req.url.includes('/state'))
      .forEach((r) => {
        r.flush(jamStatePayload);
      });
    httpMock
      .match(() => true)
      .forEach((r) => {
        r.flush([]);
      });
    expect(service.jamState().active).toBe(false);

    service.joinJamRoom('MYJAM50');
    httpMock.expectOne('/api/jams/join').flush(jamStatePayload.jam);
    httpMock
      .match((req) => req.url.includes('/state'))
      .forEach((r) => {
        r.flush(jamStatePayload);
      });
    httpMock.match('/api/jams/50/deck?limit=30').forEach((r) => {
      r.flush({ items: [], next_cursor: null, has_more: false });
    });

    service.cancelSubscription();
    httpMock.expectOne('/api/profile/plan').flush({ ...SAMPLE_AUTH.user, plan_id: 1 });
    expect(service.currentPlan()).toBe('Free');

    service.decideQueue(true);
    service.decideQueue(false);

    service.loadNextDiscoveryTrack(true, true);
    httpMock.expectOne('/api/discovery/next').flush(SAMPLE_TRACK);

    expect(service.consumePendingGoogleOAuthParams()).toBeNull();
    expect(service.openTrackForCommunitySwipe({ ...qSong, isDeleted: true })).toBe(false);

    service.applyUserDto({
      ...SAMPLE_AUTH.user,
      age: 14,
      is_admin: true,
      preferred_theme: 'light',
    });
    expect(service.isAdmin()).toBe(true);
    expect(service.preferredTheme()).toBe('light');

    service.jamState.set({ ...service.jamState(), jamId: 50, active: true });
    service.voteJamTrack(qSong, 'like');
    httpMock.expectOne('/api/jams/50/deck-vote').flush({ track_id: 101, score: 1 });
    httpMock
      .match((req) => req.url.includes('/state'))
      .forEach((r) => {
        r.flush(jamStatePayload);
      });

    service.voteJamTrack(qSong, 'reject');
    service.voteSkipJam();
    httpMock.expectOne('/api/jams/50/skip-vote').flush({ skipped: false, votes: 1, threshold: 2 });
    httpMock
      .match((req) => req.url.includes('/state'))
      .forEach((r) => {
        r.flush(jamStatePayload);
      });
  });

  it('handles backend errors gracefully on preferences, playlists, collections, and discovery', () => {
    service.completeAuthentication(SAMPLE_AUTH);
    flushInitialHydration(httpMock);

    service.refreshUserPreferences();
    httpMock.expectOne('/api/profile/blocked-genres').flush({}, { status: 500, statusText: 'Err' });
    httpMock
      .expectOne('/api/profile/favorite-genres')
      .flush({}, { status: 500, statusText: 'Err' });
    httpMock.expectOne('/api/profile/theme').flush({}, { status: 500, statusText: 'Err' });

    service.refreshPlaylists();
    httpMock.expectOne('/api/playlists').flush({}, { status: 500, statusText: 'Err' });

    service.refreshInteractedCollections();
    httpMock
      .expectOne('/api/reviews/recent-interacted?limit=1000')
      .flush({}, { status: 500, statusText: 'Err' });
    httpMock.expectOne('/api/profile/interactions').flush({}, { status: 500, statusText: 'Err' });

    service.loadNextDiscoveryTrack(true, false);
    httpMock.expectOne('/api/discovery/next').flush({}, { status: 500, statusText: 'Err' });

    service.setUserName('A');
    httpMock
      .expectOne('/api/profile/me')
      .flush({ detail: 'Invalid' }, { status: 400, statusText: 'Bad' });

    service.saveFavoriteGenres(['Pop']);
    httpMock
      .expectOne('/api/profile/favorite-genres')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.cancelSubscription();
    httpMock
      .expectOne('/api/profile/plan')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.unlinkSpotifyAccount();
    httpMock
      .expectOne('/api/spotify/connection')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.createPlaylist('Fail');
    httpMock
      .expectOne('/api/playlists/deck')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.deletePlaylist({
      id: '99',
      playlistId: 99,
      name: 'Fail',
      count: 0,
      duration: '0 min',
      isExported: false,
      songs: [],
    });
    httpMock
      .expectOne('/api/playlists/99')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.createJamRoom({ room_name: 'Fail', duration_minutes: 30, skip_votes_threshold: 2 });
    httpMock.expectOne('/api/jams').flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.joinJamRoom('BAD');
    httpMock
      .expectOne('/api/jams/join')
      .flush({ detail: 'Err' }, { status: 404, statusText: 'Not Found' });

    service.publishTrackReview(5, 'Fail');
    httpMock.expectOne('/api/reviews').flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.deleteTrackReview(999);
    httpMock
      .expectOne('/api/reviews/999')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    const plErr = {
      id: '88',
      playlistId: 88,
      name: 'ErrPl',
      count: 0,
      duration: '0 min',
      isExported: false,
      songs: [],
    };
    const songErr = {
      trackId: 101,
      title: 'T',
      artist: 'A',
      genre: 'Pop',
      time: '3:00',
      image: '',
      album: 'Al',
      year: '2024',
      match: 90,
    };
    service.playlists.set([plErr]);
    service.addSongToPlaylist(0, songErr);
    httpMock
      .expectOne('/api/playlists/88/swipe-add')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.removeTrackFromPlaylist(88, 101, 'ErrPl');
    httpMock
      .expectOne('/api/playlists/88/tracks/101')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.jamState.set({
      ...service.jamState(),
      jamId: 70,
      hostUserId: 7,
      active: true,
    });
    service.advanceJam();
    httpMock
      .expectOne('/api/jams/70/advance')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.saveJamQueueSong(songErr);
    httpMock
      .expectOne('/api/jams/70/save-queue-track')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.voteJamTrack(songErr, 'superlike');
    httpMock
      .expectOne('/api/jams/70/deck-vote')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.voteSkipJam();
    httpMock
      .expectOne('/api/jams/70/skip-vote')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    service.loadJamDeck(70);
    httpMock
      .expectOne('/api/jams/70/deck?limit=30')
      .flush({ detail: 'Err' }, { status: 500, statusText: 'Err' });

    service.closeOrLeaveJam();
    httpMock
      .expectOne('/api/jams/70/close')
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });
    httpMock.match('/api/jams/70/state').forEach((r) => {
      if (!r.cancelled) r.flush({ detail: 'Err' }, { status: 500, statusText: 'Err' });
    });

    service.refreshCatalogAndFeed();
    httpMock.expectOne('/api/tracks/search?limit=50').flush({}, { status: 500, statusText: 'Err' });
    httpMock
      .match((r) => r.url.startsWith('/api/reviews/feed'))
      .forEach((r) => {
        r.flush({}, { status: 500, statusText: 'Err' });
      });

    service.loadReviewsForTrack(songErr, 'likes');
    httpMock
      .expectOne('/api/reviews/track/101?sort_by=likes')
      .flush({}, { status: 500, statusText: 'Err' });
  });
});
