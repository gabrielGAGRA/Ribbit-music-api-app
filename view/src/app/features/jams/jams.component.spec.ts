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
    expect(state.jamState().active).toBe(false);

    component.joinJam('RIBBIT-123');
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
    expect(component.jamView()).toBe('swipe');
  });

  it('should vote to skip current track', () => {
    state.setJamActive(true);
    expect(state.jamVotes()).toBe(0);
    component.voteSkip();
    expect(state.jamVotes()).toBe(1);
  });

  it('should allow copying room code', () => {
    component.copyCode();
    expect(state.toast()).toContain('copiado');
  });

  it('should handle jam swipe actions and superlikes quota', () => {
    state.setJamActive(true);
    const initialCursor = component.jamDeckCursor();
    component.decideJamCard('like');
    expect(component.jamDeckCursor()).toBe(initialCursor + 1);

    component.decideJamCard('superlike');
    expect(component.jamSuperlikesCount()).toBe(1);
  });

  it('should allow vertical scroll on jam swipe card and stack join form on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');
    const componentStyles = readFileSync(resolve(__dirname, './jams.component.css'), 'utf8');

    expect(componentStyles).toMatch(/\.jam-swipe-card\s*\{[^}]*touch-action:\s*pan-y/);
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.join-panel form\s*\{[^}]*flex-direction:\s*column/,
    );
  });
});
