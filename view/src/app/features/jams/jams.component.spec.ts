import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { JamsComponent } from './jams.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';

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
    const initialCursor = component['jamDeckCursor']();
    component['decideJamCard']('like');
    expect(component['jamDeckCursor']()).toBe(initialCursor + 1);

    component['decideJamCard']('superlike');
    expect(component['jamSuperlikesCount']()).toBe(1);
  });

  it('should allow vertical scroll on jam swipe card and stack join form on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');
    const componentStyles = readFileSync(resolve(__dirname, './jams.component.css'), 'utf8');

    expect(componentStyles).toMatch(/\.jam-swipe-card\s*\{[^}]*touch-action:\s*pan-y/);
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
});
