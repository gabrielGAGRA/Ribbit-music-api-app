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
  httpMock.expectOne('/api/tracks/search?limit=50').flush([SAMPLE_TRACK]);
  httpMock.expectOne('/api/reviews/feed?days=30&limit=20').flush([]);
  httpMock.expectOne('/api/playlists').flush([]);
  httpMock.expectOne('/api/reviews/recent-interacted?limit=100').flush([]);
  httpMock.expectOne('/api/profile/interactions').flush([]);
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
    expect(service.songs().length).toBeGreaterThan(0);
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
    httpMock.expectOne('/api/reviews/recent-interacted?limit=100').flush([
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
    expect(service.isDeckEmpty()).toBe(true);

    service.undo();
    expect(service.isDeckEmpty()).toBe(false);
    expect(service.discoverySong()?.trackId).toBe(101);
    expect(service.toast()).toContain('desfeito');
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

    service.createPlaylist('Noite Indie', 45);
    const playlistReq = httpMock.expectOne('/api/playlists/deck');
    expect(playlistReq.request.method).toBe('POST');
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

    service.decideQueue(true);
    expect(service.queue().length).toBe(1);

    service.voteSkipJam();
    expect(service.jamVotes()).toBe(1);

    service.deleteAccount();
    const deleteReq = httpMock.expectOne('/api/profile/account');
    expect(deleteReq.request.method).toBe('DELETE');
    deleteReq.flush(null, { status: 204, statusText: 'No Content' });
    expect(service.authView()).toBe('register');
  });
});
