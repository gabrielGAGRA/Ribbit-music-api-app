import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { JamService } from './jam.service';

describe('JamService', () => {
  let service: JamService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(JamService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('creates, joins, reads state, advances, and closes a Jam', () => {
    service
      .createJam({ room_name: 'Friday Jam', duration_minutes: 60, skip_votes_threshold: 2 })
      .subscribe();
    const createReq = httpMock.expectOne('/api/jams');
    expect(createReq.request.method).toBe('POST');
    createReq.flush({ jam_id: 1, name: 'Friday Jam', room_code: 'ABC123', is_active: true });

    service.joinJam(' ABC123 ').subscribe();
    const joinReq = httpMock.expectOne('/api/jams/join');
    expect(joinReq.request.method).toBe('POST');
    expect(joinReq.request.body).toEqual({ room_code: 'ABC123' });
    joinReq.flush({ jam_id: 1, name: 'Friday Jam', room_code: 'ABC123', is_active: true });

    service.getJamState(1).subscribe();
    const stateReq = httpMock.expectOne('/api/jams/1/state');
    expect(stateReq.request.method).toBe('GET');
    stateReq.flush({ jam_id: 1, queue: [], skip_votes: 0 });

    service.advanceJam(1).subscribe();
    const advReq = httpMock.expectOne('/api/jams/1/advance');
    expect(advReq.request.method).toBe('POST');
    advReq.flush({ jam_id: 1, queue: [], skip_votes: 0 });

    service.closeJam(1).subscribe();
    const closeReq = httpMock.expectOne('/api/jams/1/close');
    expect(closeReq.request.method).toBe('POST');
    closeReq.flush({ jam_id: 1, name: 'Friday Jam', room_code: 'ABC123', is_active: false });
  });

  it('loads Jam deck, votes on tracks, votes to skip, and saves queue track', () => {
    service.getJamDeck(2, 10, 50).subscribe();
    const deckReq = httpMock.expectOne('/api/jams/2/deck?limit=10&cursor_id=50');
    expect(deckReq.request.method).toBe('GET');
    deckReq.flush({ items: [], next_cursor: null, has_more: false });

    service.voteTrack({ jamId: 2, trackId: 9, action: 'superlike' }).subscribe();
    const superReq = httpMock.expectOne('/api/jams/2/deck-vote');
    expect(superReq.request.body).toEqual({ track_id: 9, action: 'superlike', points: 2 });
    superReq.flush({ track_id: 9, score: 2 });

    service.voteTrack({ jamId: 2, trackId: 8, action: 'like' }).subscribe();
    const likeReq = httpMock.expectOne('/api/jams/2/deck-vote');
    expect(likeReq.request.body).toEqual({ track_id: 8, action: 'like', points: 1 });
    likeReq.flush({ track_id: 8, score: 1 });

    service.voteSkip(2, 9).subscribe();
    const skipReq = httpMock.expectOne('/api/jams/2/skip-vote');
    expect(skipReq.request.body).toEqual({ track_id: 9 });
    skipReq.flush({ skipped: false, votes: 1, threshold: 2 });

    service.saveQueueTrack(2, 9, 4).subscribe((ok) => {
      expect(ok).toBe(true);
    });
    const saveReq = httpMock.expectOne('/api/jams/2/save-queue-track');
    expect(saveReq.request.body).toEqual({ track_id: 9, playlist_id: 4 });
    saveReq.flush({ success: true, message: 'saved' });
  });
});
