import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { Song } from '@ribbit/shared-types';
import { JamsComponent } from './jams.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';

function makeSong(trackId: number, title: string, genre = 'Pop'): Song {
  return {
    trackId,
    title,
    artist: `Artista ${trackId}`,
    genre,
    time: '3:00',
    image: `cover-${trackId}.jpg`,
    album: 'Single',
    year: '2025',
    match: 90,
    durationSeconds: 180,
  };
}

describe('JamsComponent', () => {
  let component: JamsComponent;
  let state: RibbitStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    httpMock = TestBed.inject(HttpTestingController);
    component = TestBed.runInInjectionContext(() => new JamsComponent());
  });

  afterEach(() => {
    state.ngOnDestroy();
  });

  it('should join jam room via POST /api/jams/join when authenticated and switch to swipe view', () => {
    writeAuthToken('jwt-jam-token');
    state.spotifyId.set('spot_3');
    state.spotifyPremium.set(true);
    expect(state.jamState().active).toBe(false);

    component['joinJam']('RIBBIT-123');
    const joinReq = httpMock.expectOne('/api/jams/join');
    expect(joinReq.request.method).toBe('POST');
    expect(joinReq.request.body).toEqual({ room_code: 'RIBBIT-123' });
    joinReq.flush({
      jam_id: 21,
      host_user_id: 3,
      room_code: 'RIBBIT-123',
      room_name: 'Sala Indie',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
    });

    httpMock.expectOne('/api/jams/21/deck?limit=30').flush({ items: [] });
    httpMock.expectOne('/api/jams/21/state').flush({
      jam: {
        jam_id: 21,
        host_user_id: 3,
        room_code: 'RIBBIT-123',
        room_name: 'Sala Indie',
        duration_minutes: 60,
        skip_votes_threshold: 3,
        is_active: true,
        current_track_id: null,
        accumulated_duration_seconds: 0,
        superlikes_used: 0,
        max_superlikes: 5,
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });

    expect(state.jamState().active).toBe(true);
    expect(component['jamView']()).toBe('swipe');
  });

  it('should vote to skip current track', () => {
    state.setJamActive(true);
    expect(state.jamVotes()).toBe(0);
    component['voteSkip']();
    expect(state.jamVotes()).toBe(1);
  });

  it('should allow copying room code', () => {
    component['copyCode']();
    expect(state.toast()).toContain('copiado');
  });

  it('should handle jam swipe actions and superlikes quota', () => {
    state.setJamActive(true);
    state.jamDeckSongs.set([makeSong(1, 'Track 1'), makeSong(2, 'Track 2')]);
    const initialCursor = component['jamDeckCursor']();
    component['decideJamCard']('like');
    expect(component['jamDeckCursor']()).toBe(initialCursor + 1);

    component['decideJamCard']('superlike');
    expect(component['jamSuperlikesCount']()).toBe(1);
  });

  it('should disable browser touch-action on jam swipe card and stack join form on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');
    const componentStyles = readFileSync(resolve(__dirname, './jams.component.css'), 'utf8');

    expect(componentStyles).toMatch(/\.jam-swipe-card\s*\{[^}]*touch-action:\s*none/);
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.join-panel form\s*\{[^}]*flex-direction:\s*column/,
    );
  });

  it('prompts spotify connection modal when unlinked user tries to open jam modal', () => {
    state.spotifyId.set(null);
    component['openJamModal']();
    expect(state.activeModal()).toBe('spotify-connect');
    expect(state.spotifyPromptReason()).toContain('Conecte sua conta do Spotify');
  });

  it('shows warning notification when linked non-premium user tries to open jam modal', () => {
    state.spotifyId.set('spot_user_1');
    state.spotifyPremium.set(false);
    component['openJamModal']();
    expect(state.activeModal()).toBeNull();
    expect(state.toast()).toContain('Spotify Premium é necessária');
  });

  it('prompts spotify connection modal when unlinked user tries to join jam', () => {
    state.spotifyId.set(null);
    component['joinJam']('123456');
    expect(state.activeModal()).toBe('spotify-connect');
  });

  it('shows warning notification when linked non-premium user tries to join jam', () => {
    state.spotifyId.set('spot_user_1');
    state.spotifyPremium.set(false);
    component['joinJam']('123456');
    expect(state.activeModal()).toBeNull();
    expect(state.toast()).toContain('Spotify Premium é necessária');
  });

  it('should trigger advanceJam and load more deck tracks using cursor', () => {
    writeAuthToken('jwt-jam-token');
    state.jamState.set({
      jamId: 35,
      hostUserId: 1,
      active: true,
      code: 'RIBBIT-999',
      roomName: 'Sala VIP',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
    });
    state.jamDeckNextCursor.set(200);

    component['advanceJam']();
    const advReq = httpMock.expectOne('/api/jams/35/advance');
    expect(advReq.request.method).toBe('POST');
    advReq.flush({});
    httpMock.expectOne('/api/jams/35/state').flush({
      jam: {
        jam_id: 35,
        host_user_id: 1,
        room_name: 'Sala VIP',
        room_code: 'RIBBIT-999',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'livre',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });

    component['fetchMoreJamDeck']();
    const deckReq = httpMock.expectOne('/api/jams/35/deck?limit=30&cursor_id=200');
    expect(deckReq.request.method).toBe('GET');
    deckReq.flush({ items: [], next_cursor: null, has_more: false });
  });

  it('should close jam via POST /api/jams/{id}/close when host calls leaveJam()', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(10);
    state.jamState.set({
      jamId: 44,
      roomId: 44,
      hostUserId: 10,
      active: true,
      code: 'HOST-44',
      roomName: 'Minha Jam Host',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
    });

    component['leaveJam']();

    const closeReq = httpMock.expectOne('/api/jams/44/close');
    expect(closeReq.request.method).toBe('POST');
    closeReq.flush({ jam_id: 44, is_active: false });

    expect(state.jamState().active).toBe(false);
    expect(state.jamState().roomId).toBeUndefined();
    expect(state.toast()).toContain('encerrada');
  });

  it('should leave jam and reset state locally without calling closeJam when listener calls leaveJam()', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(99); // Listener, not host
    state.jamState.set({
      jamId: 55,
      roomId: 55,
      hostUserId: 10, // Host is someone else
      active: true,
      code: 'LIST-55',
      roomName: 'Sala de Outro Host',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
    });

    component['leaveJam']();

    httpMock.expectNone('/api/jams/55/close');
    expect(state.jamState().active).toBe(false);
    expect(state.jamState().roomId).toBeUndefined();
    expect(state.toast()).toContain('Você saiu da Jam');
  });

  it('preserves jamDeckCursor when navigating away and recreating JamsComponent', () => {
    state.jamState.set({
      jamId: 60,
      hostUserId: 1,
      active: true,
      code: 'PLAY-60',
      roomName: 'Playlist Jam',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
      deckSource: 'playlist',
    });
    state.jamDeckSongs.set([makeSong(101, 'Faixa 1', 'Pop'), makeSong(102, 'Faixa 2', 'Rock')]);
    state.jamDeckLoaded.set(true);

    expect(component.currentJamDeckSong()?.trackId).toBe(101);
    component['decideJamCard']('reject');
    expect(component.jamDeckCursor()).toBe(1);

    const recreated = TestBed.runInInjectionContext(() => new JamsComponent());
    expect(recreated.jamDeckCursor()).toBe(1);
    expect(recreated.currentJamDeckSong()?.trackId).toBe(102);
  });

  it('does not wrap back to start when playlist deck ends and pulls unseen catalog fallback before stopping', () => {
    state.songs.set([makeSong(101, 'Playlist 1', 'Pop'), makeSong(201, 'Extra Catalogo', 'Indie')]);
    state.jamState.set({
      jamId: 61,
      hostUserId: 1,
      active: true,
      code: 'PLAY-61',
      roomName: 'Playlist Curta',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
      deckSource: 'playlist',
    });
    state.jamDeckSongs.set([state.songs()[0]!]);
    state.jamDeckNextCursor.set(null);
    state.jamDeckLoaded.set(true);

    expect(component.currentJamDeckSong()?.trackId).toBe(101);
    component['decideJamCard']('reject');

    // Moves to unseen catalog track outside the base playlist rather than wrapping to 101
    expect(component.currentJamDeckSong()?.trackId).toBe(201);
    component['decideJamCard']('reject');

    // Once all tracks are seen, stops cleanly instead of repeating
    expect(component.currentJamDeckSong()).toBeNull();
  });

  it('resumes from saved cursor_id when rejoining the same Jam and starts fresh on a new Jam', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.spotifyId.set('spot_7');
    state.spotifyPremium.set(true);

    // Join Jam 70 for the first time
    component['joinJam']('ROOM-70');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 70,
      host_user_id: 7,
      room_code: 'ROOM-70',
      room_name: 'Sala 70',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
      deck_source: 'playlist',
      source_playlist_id: 9,
    });
    httpMock.expectOne('/api/jams/70/deck?limit=30').flush({
      items: [
        {
          track_id: 11,
          title: 'Track 11',
          artist: 'A',
          duration_seconds: 180,
          genre: 'Pop',
        },
        {
          track_id: 12,
          title: 'Track 12',
          artist: 'B',
          duration_seconds: 180,
          genre: 'Pop',
        },
      ],
      next_cursor: null,
      has_more: false,
    });
    httpMock.expectOne('/api/jams/70/state').flush({
      jam: {
        jam_id: 70,
        host_user_id: 7,
        room_name: 'Sala 70',
        room_code: 'ROOM-70',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });

    // Reject Track 11 (only saved locally because no backend reject endpoint exists)
    component['decideJamCard']('reject');
    expect(component.currentJamDeckSong()?.trackId).toBe(12);

    // Rejoin Jam 70 -> must pass cursor_id=11 to resume from Track 12
    component['joinJam']('ROOM-70');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 70,
      host_user_id: 7,
      room_code: 'ROOM-70',
      room_name: 'Sala 70',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
      deck_source: 'playlist',
      source_playlist_id: 9,
    });
    const resumeReq = httpMock.expectOne('/api/jams/70/deck?limit=30&cursor_id=11');
    resumeReq.flush({
      items: [
        {
          track_id: 12,
          title: 'Track 12',
          artist: 'B',
          duration_seconds: 180,
          genre: 'Pop',
        },
      ],
      next_cursor: null,
      has_more: false,
    });
    httpMock.expectOne('/api/jams/70/state').flush({
      jam: {
        jam_id: 70,
        host_user_id: 7,
        room_name: 'Sala 70',
        room_code: 'ROOM-70',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });
    expect(component.currentJamDeckSong()?.trackId).toBe(12);

    // Joining a different Jam (71) starts without cursor_id
    component['joinJam']('ROOM-71');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 71,
      host_user_id: 7,
      room_code: 'ROOM-71',
      room_name: 'Sala 71',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
      deck_source: 'playlist',
      source_playlist_id: 9,
    });
    httpMock.expectOne('/api/jams/71/deck?limit=30').flush({
      items: [
        {
          track_id: 11,
          title: 'Track 11',
          artist: 'A',
          duration_seconds: 180,
          genre: 'Pop',
        },
      ],
      next_cursor: null,
      has_more: false,
    });
    httpMock.expectOne('/api/jams/71/state').flush({
      jam: {
        jam_id: 71,
        host_user_id: 7,
        room_name: 'Sala 71',
        room_code: 'ROOM-71',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });
    expect(component.currentJamDeckSong()?.trackId).toBe(11);
  });

  it('prevents duplicate concurrent fetchMoreJamDeck calls and deduplicates appended tracks', () => {
    state.jamState.set({
      jamId: 80,
      hostUserId: 1,
      active: true,
      code: 'PAG-80',
      roomName: 'Paginated Jam',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
      deckSource: 'playlist',
    });
    state.jamDeckSongs.set([makeSong(1, 'S1')]);
    state.jamDeckNextCursor.set(1);

    component['fetchMoreJamDeck']();
    component['fetchMoreJamDeck']();

    const deckReqs = httpMock.match('/api/jams/80/deck?limit=30&cursor_id=1');
    expect(deckReqs).toHaveLength(1);
    deckReqs[0]!.flush({
      items: [
        { track_id: 1, title: 'S1', artist: 'A', duration_seconds: 180, genre: 'Pop' },
        { track_id: 2, title: 'S2', artist: 'B', duration_seconds: 180, genre: 'Pop' },
      ],
      next_cursor: null,
      has_more: false,
    });

    expect(state.jamDeckSongs().map((song) => song.trackId)).toEqual([1, 2]);
  });

  it('clears jamDeckNextCursor on pagination error so deck falls back instead of wedging', () => {
    state.songs.set([makeSong(1, 'S1'), makeSong(2, 'Fallback S2')]);
    state.jamState.set({
      jamId: 81,
      hostUserId: 1,
      active: true,
      code: 'ERR-81',
      roomName: 'Error Recovery Jam',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
      deckSource: 'playlist',
    });
    state.jamDeckSongs.set([makeSong(1, 'S1')]);
    state.jamDeckNextCursor.set(1);

    component['fetchMoreJamDeck']();
    const deckReq = httpMock.expectOne('/api/jams/81/deck?limit=30&cursor_id=1');
    deckReq.flush({ detail: 'Internal error' }, { status: 500, statusText: 'Server Error' });

    expect(state.jamDeckLoading()).toBe(false);
    expect(state.jamDeckNextCursor()).toBeNull();

    component['decideJamCard']('reject');
    expect(component.currentJamDeckSong()?.trackId).toBe(2);
  });

  it('ignores stale in-flight deck response when switching to another Jam room', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.spotifyId.set('spot_7');
    state.spotifyPremium.set(true);

    component['joinJam']('OLD-70');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 70,
      host_user_id: 7,
      room_code: 'OLD-70',
      room_name: 'Old Jam',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
    });
    const oldDeckReq = httpMock.expectOne('/api/jams/70/deck?limit=30');
    httpMock.expectOne('/api/jams/70/state').flush({
      jam: {
        jam_id: 70,
        host_user_id: 7,
        room_name: 'Old Jam',
        room_code: 'OLD-70',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });

    // Switch to Jam 71 before Jam 70's deck responds
    component['joinJam']('NEW-71');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 71,
      host_user_id: 7,
      room_code: 'NEW-71',
      room_name: 'New Jam',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
    });
    const newDeckReq = httpMock.expectOne('/api/jams/71/deck?limit=30');
    httpMock.expectOne('/api/jams/71/state').flush({
      jam: {
        jam_id: 71,
        host_user_id: 7,
        room_name: 'New Jam',
        room_code: 'NEW-71',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });

    newDeckReq.flush({
      items: [
        { track_id: 900, title: 'New Track', artist: 'B', duration_seconds: 180, genre: 'Pop' },
      ],
      next_cursor: null,
      has_more: false,
    });
    expect(oldDeckReq.cancelled).toBe(true);
    expect(state.jamDeckSongs().map((song) => song.trackId)).toEqual([900]);
  });

  it('rolls back superlikesCount, cursor, and does not persist track when deck-vote API fails', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.jamState.set({
      jamId: 82,
      hostUserId: 7,
      active: true,
      code: 'VOTE-82',
      roomName: 'Vote Rollback Jam',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
      superlikesCount: 0,
      superlikesLimit: 5,
      deckSource: 'playlist',
    });
    state.jamDeckSongs.set([makeSong(55, 'Fail Track'), makeSong(56, 'Next Track')]);

    component['decideJamCard']('superlike');
    expect(component['jamSuperlikesCount']()).toBe(1);
    expect(component.jamDeckCursor()).toBe(1);

    const voteReq = httpMock.expectOne('/api/jams/82/deck-vote');
    voteReq.flush(
      { detail: 'Superlike limit reached for this Jam session.' },
      { status: 400, statusText: 'Bad Request' },
    );

    expect(component['jamSuperlikesCount']()).toBe(0);
    expect(component.jamDeckCursor()).toBe(0);
    expect(component.currentJamDeckSong()?.trackId).toBe(55);
    expect(state.jamSeenTrackIds().has(55)).toBe(false);
    expect(localStorage.getItem('ribbit:jam_deck:7:82')).toBeNull();
  });

  it('skips blockedGenres and unlinked tracks without trackId in authenticated Jam fallback', () => {
    writeAuthToken('jwt-jam-token');
    state.blockedGenres.set(['Metal']);
    state.songs.set([
      { ...makeSong(1, 'Unlinked'), trackId: undefined },
      makeSong(2, 'Heavy Track', 'Metal'),
      makeSong(3, 'Allowed Indie', 'Indie'),
    ]);
    state.jamState.set({
      jamId: 83,
      hostUserId: 1,
      active: true,
      code: 'FLT-83',
      roomName: 'Filtered Fallback Jam',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
      deckSource: 'playlist',
    });
    state.jamDeckSongs.set([]);
    state.jamDeckNextCursor.set(null);
    state.jamDeckLoaded.set(true);

    expect(component.currentJamDeckSong()?.trackId).toBe(3);
  });

  it('keeps unconfirmed track out of localStorage and recovers cursor when an interleaved swipe occurs before vote fails', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.jamState.set({
      jamId: 84,
      hostUserId: 7,
      active: true,
      code: 'INT-84',
      roomName: 'Interleaved Jam',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
      superlikesCount: 0,
      superlikesLimit: 5,
      deckSource: 'playlist',
    });
    state.jamDeckSongs.set([
      makeSong(55, 'Pending Fail'),
      makeSong(56, 'Confirmed Reject'),
      makeSong(57, 'Third Song'),
    ]);

    component['decideJamCard']('superlike');
    const vote55Req = httpMock.expectOne('/api/jams/84/deck-vote');

    component['decideJamCard']('reject');
    const savedBeforeFailure = JSON.parse(localStorage.getItem('ribbit:jam_deck:7:84') ?? '{}');
    expect(savedBeforeFailure.seenTrackIds).toEqual([56]);
    expect(savedBeforeFailure.cursorTrackId).toBeUndefined();

    vote55Req.flush(
      { detail: 'Superlike limit reached for this Jam session.' },
      { status: 400, statusText: 'Bad Request' },
    );

    expect(component['jamSuperlikesCount']()).toBe(0);
    expect(component.currentJamDeckSong()?.trackId).toBe(55);
    expect(state.jamSeenTrackIds().has(55)).toBe(false);
    expect(state.jamSeenTrackIds().has(56)).toBe(true);

    // Retry with like on 55 -> advances cleanly past already-rejected 56 to 57
    component['decideJamCard']('like');
    httpMock.expectOne('/api/jams/84/deck-vote').flush({
      jam_queue_id: 1,
      jam_id: 84,
      track_id: 55,
      vote_points: 1,
    });
    const stateReqs = httpMock.match('/api/jams/84/state');
    expect(stateReqs).toHaveLength(2);
    expect(stateReqs[0]!.cancelled).toBe(true);
    stateReqs[1]!.flush({
      jam: {
        jam_id: 84,
        host_user_id: 7,
        room_name: 'Interleaved Jam',
        room_code: 'INT-84',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });
    expect(component.currentJamDeckSong()?.trackId).toBe(57);
  });

  it('preserves pending optimistic superlikesCount when a stale state poll arrives mid-vote', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.spotifyId.set('spot_7');
    state.spotifyPremium.set(true);

    component['joinJam']('POLL-85');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 85,
      host_user_id: 7,
      room_code: 'POLL-85',
      room_name: 'Poll Jam',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 1,
      deck_source: 'playlist',
    });
    httpMock.expectOne('/api/jams/85/deck?limit=30').flush({
      items: [
        { track_id: 10, title: 'S10', artist: 'A', duration_seconds: 180, genre: 'Pop' },
        { track_id: 11, title: 'S11', artist: 'B', duration_seconds: 180, genre: 'Pop' },
      ],
      next_cursor: null,
      has_more: false,
    });
    const initialStateReq = httpMock.expectOne('/api/jams/85/state');

    component['decideJamCard']('superlike');
    expect(component['jamSuperlikesCount']()).toBe(1);
    const voteReq = httpMock.expectOne('/api/jams/85/deck-vote');

    // Stale poll returns superlikes_used: 0 while superlike request is in flight
    initialStateReq.flush({
      jam: {
        jam_id: 85,
        host_user_id: 7,
        room_name: 'Poll Jam',
        room_code: 'POLL-85',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 1,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });
    expect(component['jamSuperlikesCount']()).toBe(1);

    // Vote fails -> pending count clears and superlikesCount rolls back to 0
    voteReq.flush({ detail: 'Limit reached' }, { status: 400, statusText: 'Bad Request' });
    expect(component['jamSuperlikesCount']()).toBe(0);
  });

  it('does not wipe new Jam or bleed stale vote responses when host closes and immediately joins another Jam', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.spotifyId.set('spot_7');
    state.spotifyPremium.set(true);
    state.jamState.set({
      jamId: 90,
      roomId: 90,
      hostUserId: 7,
      active: true,
      code: 'OLD-90',
      roomName: 'Old Host Jam',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
    });
    state.jamDeckSongs.set([makeSong(301, 'Old Song')]);

    component['decideJamCard']('like');
    const oldVoteReq = httpMock.expectOne('/api/jams/90/deck-vote');

    component['leaveJam']();
    const closeReq = httpMock.expectOne('/api/jams/90/close');
    expect(state.jamState().active).toBe(false);

    component['joinJam']('NEW-91');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 91,
      host_user_id: 7,
      room_code: 'NEW-91',
      room_name: 'New Host Jam',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
    });
    httpMock.expectOne('/api/jams/91/deck?limit=30').flush({
      items: [
        { track_id: 401, title: 'New Song', artist: 'B', duration_seconds: 180, genre: 'Pop' },
      ],
      next_cursor: null,
      has_more: false,
    });
    httpMock.expectOne('/api/jams/91/state').flush({
      jam: {
        jam_id: 91,
        host_user_id: 7,
        room_name: 'New Host Jam',
        room_code: 'NEW-91',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'livre',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });

    // Old close and old vote complete after switching to Jam 91
    closeReq.flush({ jam_id: 90, is_active: false });
    oldVoteReq.flush({ jam_queue_id: 1, jam_id: 90, track_id: 301, vote_points: 1 });

    httpMock.expectNone('/api/jams/90/state');
    expect(state.jamState().jamId).toBe(91);
    expect(state.jamState().active).toBe(true);
    expect(state.jamDeckSongs().map((song) => song.trackId)).toEqual([401]);
  });

  it('does not advance cursorTrackId past an earlier failed vote when a later vote succeeds out of order', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.spotifyId.set('spot_7');
    state.spotifyPremium.set(true);

    component['joinJam']('ORD-92');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 92,
      host_user_id: 7,
      room_code: 'ORD-92',
      room_name: 'Out of Order Votes',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
      deck_source: 'playlist',
    });
    httpMock.expectOne('/api/jams/92/deck?limit=30').flush({
      items: [
        { track_id: 55, title: 'S55', artist: 'A', duration_seconds: 180, genre: 'Pop' },
        { track_id: 56, title: 'S56', artist: 'B', duration_seconds: 180, genre: 'Pop' },
        { track_id: 57, title: 'S57', artist: 'C', duration_seconds: 180, genre: 'Pop' },
      ],
      next_cursor: null,
      has_more: false,
    });
    httpMock.expectOne('/api/jams/92/state').flush({
      jam: {
        jam_id: 92,
        host_user_id: 7,
        room_name: 'Out of Order Votes',
        room_code: 'ORD-92',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });

    // Two concurrent votes in flight
    component['decideJamCard']('like'); // 55
    component['decideJamCard']('like'); // 56
    const voteReqs = httpMock.match('/api/jams/92/deck-vote');
    expect(voteReqs).toHaveLength(2);

    // 55 fails first, then 56 succeeds
    voteReqs[0]!.flush({ detail: 'Temporary error' }, { status: 500, statusText: 'Server Error' });
    voteReqs[1]!.flush({ jam_queue_id: 2, jam_id: 92, track_id: 56, vote_points: 1 });
    httpMock.expectOne('/api/jams/92/state').flush({
      jam: {
        jam_id: 92,
        host_user_id: 7,
        room_name: 'Out of Order Votes',
        room_code: 'ORD-92',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });

    const saved = JSON.parse(localStorage.getItem('ribbit:jam_deck:7:92') ?? '{}');
    expect(saved.cursorTrackId).toBeUndefined();
    expect(saved.seenTrackIds).toEqual([56]);

    // Rejoining does not pass cursor_id=56 and still surfaces unvoted 55
    component['joinJam']('ORD-92');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 92,
      host_user_id: 7,
      room_code: 'ORD-92',
      room_name: 'Out of Order Votes',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 5,
      deck_source: 'playlist',
    });
    httpMock.expectOne('/api/jams/92/deck?limit=30').flush({
      items: [
        { track_id: 55, title: 'S55', artist: 'A', duration_seconds: 180, genre: 'Pop' },
        { track_id: 56, title: 'S56', artist: 'B', duration_seconds: 180, genre: 'Pop' },
        { track_id: 57, title: 'S57', artist: 'C', duration_seconds: 180, genre: 'Pop' },
      ],
      next_cursor: null,
      has_more: false,
    });
    httpMock.expectOne('/api/jams/92/state').flush({
      jam: {
        jam_id: 92,
        host_user_id: 7,
        room_name: 'Out of Order Votes',
        room_code: 'ORD-92',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 0,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'playlist',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });
    expect(component.currentJamDeckSong()?.trackId).toBe(55);
  });

  it('keeps superlikesCount clamped at server limit when poll reports 5/5 before failing superlike rolls back', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.spotifyId.set('spot_7');
    state.spotifyPremium.set(true);

    component['joinJam']('CAP-93');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 93,
      host_user_id: 7,
      room_code: 'CAP-93',
      room_name: 'Cap Jam',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 4,
      max_superlikes: 5,
    });
    httpMock.expectOne('/api/jams/93/deck?limit=30').flush({
      items: [{ track_id: 10, title: 'S10', artist: 'A', duration_seconds: 180, genre: 'Pop' }],
      next_cursor: null,
      has_more: false,
    });
    const pollReq = httpMock.expectOne('/api/jams/93/state');

    component['decideJamCard']('superlike');
    expect(component['jamSuperlikesCount']()).toBe(5);
    const voteReq = httpMock.expectOne('/api/jams/93/deck-vote');

    // Another user exhausted the 5th superlike on the server
    pollReq.flush({
      jam: {
        jam_id: 93,
        host_user_id: 7,
        room_name: 'Cap Jam',
        room_code: 'CAP-93',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 5,
        superlikes_used: 5,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'livre',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });
    expect(component['jamSuperlikesCount']()).toBe(5);

    voteReq.flush(
      { detail: 'Superlike limit reached' },
      { status: 400, statusText: 'Bad Request' },
    );
    expect(component['jamSuperlikesCount']()).toBe(5);
  });

  it('cancels stale pre-vote state poll when superlike succeeds so quota is not clobbered', () => {
    writeAuthToken('jwt-jam-token');
    state.userId.set(7);
    state.spotifyId.set('spot_7');
    state.spotifyPremium.set(true);

    component['joinJam']('SEQ-94');
    httpMock.expectOne('/api/jams/join').flush({
      jam_id: 94,
      host_user_id: 7,
      room_code: 'SEQ-94',
      room_name: 'Seq Jam',
      duration_minutes: 60,
      skip_votes_threshold: 3,
      is_active: true,
      current_track_id: null,
      accumulated_duration_seconds: 0,
      superlikes_used: 0,
      max_superlikes: 1,
    });
    httpMock.expectOne('/api/jams/94/deck?limit=30').flush({
      items: [{ track_id: 10, title: 'S10', artist: 'A', duration_seconds: 180, genre: 'Pop' }],
      next_cursor: null,
      has_more: false,
    });
    const stalePollReq = httpMock.expectOne('/api/jams/94/state');

    component['decideJamCard']('superlike');
    const voteReq = httpMock.expectOne('/api/jams/94/deck-vote');
    voteReq.flush({ jam_queue_id: 1, jam_id: 94, track_id: 10, vote_points: 2 });

    expect(stalePollReq.cancelled).toBe(true);
    const freshPollReq = httpMock.expectOne('/api/jams/94/state');
    freshPollReq.flush({
      jam: {
        jam_id: 94,
        host_user_id: 7,
        room_name: 'Seq Jam',
        room_code: 'SEQ-94',
        is_active: true,
        duration_minutes: 60,
        max_superlikes: 1,
        superlikes_used: 1,
        skip_votes_threshold: 3,
        accumulated_duration_seconds: 0,
        deck_source: 'livre',
      },
      current_track: null,
      queue: [],
      skip_votes: 0,
    });
    expect(component['jamSuperlikesCount']()).toBe(1);
  });

  it('switches jam views, handles drag lifecycle, and likes/loves current track', () => {
    component['selectJamView']('room');
    expect(component['jamView']()).toBe('room');
    component['selectJamView']('swipe');
    expect(component['jamView']()).toBe('swipe');

    component['cancelJamCardDrag']();
    component['finishJamCardDrag']();

    component['likeCurrent']();
    const song = {
      trackId: 99,
      title: 'Jam Track',
      artist: 'DJ',
      genre: 'House',
      time: '3:00',
      image: '',
      album: 'Club',
      year: '2024',
      match: 90,
    };
    component['loveTrack'](song);
    expect(state.toast()).toBeTruthy();

    component['startJamCardDrag']({
      clientX: 10,
      clientY: 20,
      pointerId: 1,
      target: document.createElement('div'),
      currentTarget: null,
    } as unknown as PointerEvent);
    component['moveJamCardDrag']({ clientX: 80, clientY: 25 } as unknown as PointerEvent);
    component['finishJamCardDrag']();
    component['cancelJamCardDrag']();

    state.spotifyId.set('sp-1');
    state.spotifyPremium.set(true);
    component['openJamModal']();
    expect(state.activeModal()).toBe('jam');
    state.setModal(null);
  });

  it('should compute jamDurationProgressPercent from accumulated, active, and queued tracks and bind progressbar', () => {
    state.jamState.set({
      ...state.jamState(),
      active: true,
      durationHours: 1,
      durationMinutes: 0,
      accumulatedMinutes: 3,
      queueItems: [],
    });
    expect(component['jamAccumulatedMinutes']()).toBe(3);
    expect(component['jamDurationProgressPercent']()).toBe(5);

    state.jamState.set({
      ...state.jamState(),
      durationHours: 1,
      durationMinutes: 0,
      accumulatedMinutes: 3,
      currentTrack: makeSong(10, 'Playing Track'),
      queueItems: [{ song: makeSong(11, 'Queued Track'), votePoints: 2 }],
    });
    expect(component['jamAccumulatedMinutes']()).toBe(9);
    expect(component['jamDurationProgressPercent']()).toBe(15);

    state.jamState.set({
      ...state.jamState(),
      durationHours: 1,
      durationMinutes: 0,
      accumulatedMinutes: 90,
      queueItems: [],
    });
    expect(component['jamDurationProgressPercent']()).toBe(100);

    state.jamState.set({
      ...state.jamState(),
      durationHours: 0,
      durationMinutes: 0,
      accumulatedMinutes: 5,
      queueItems: [],
    });
    expect(component['jamDurationProgressPercent']()).toBe(0);

    const html = readFileSync(resolve(import.meta.dirname, 'jams.component.html'), 'utf8');
    expect(html).toContain('[appWidthPercent]="jamDurationProgressPercent()"');
    expect(html).toContain('role="progressbar"');
  });
});
