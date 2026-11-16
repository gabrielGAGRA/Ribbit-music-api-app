import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AdminModerationComponent } from './admin-moderation.component';
import { AdminStateService } from './admin-state.service';

describe('AdminModerationComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('searches active tracks, toggles explicit/+18, blocks/restores tracks, and deletes reviews', () => {
    const state = TestBed.inject(AdminStateService);
    const component = TestBed.runInInjectionContext(() => new AdminModerationComponent());

    expect(component['formatDuration'](218)).toBe('3:38');
    expect(component['searchedActiveTracks']().length).toBe(5);

    component['trackQuery'].set('Boogarins');
    expect(component['searchedActiveTracks']().length).toBe(1);

    const targetTrack = component['searchedActiveTracks']()[0]!;
    expect(targetTrack.explicit).toBe(false);
    component['toggleExplicit'](targetTrack);
    const explicitReq = httpMock.expectOne('/api/admin/tracks/107/explicit');
    expect(explicitReq.request.method).toBe('PUT');
    expect(explicitReq.request.body).toEqual({ explicit: true });
    explicitReq.flush({ track_id: 107, explicit: true });
    expect(state.activeTracks().find((item) => item.track_id === 107)?.explicit).toBe(true);

    component['blockTrack'](107);
    const blockReq = httpMock.expectOne('/api/admin/tracks/107/block');
    expect(blockReq.request.method).toBe('PUT');
    expect(blockReq.request.body).toEqual({ blocked: true });
    blockReq.flush({ track_id: 107, blocked: true });
    expect(component['blockedTracks']().some((item) => item.track_id === 107)).toBe(true);

    component['selectTab']('blocked');
    component['restoreTrack'](107);
    const restoreReq = httpMock.expectOne('/api/admin/tracks/107/block');
    expect(restoreReq.request.method).toBe('PUT');
    expect(restoreReq.request.body).toEqual({ blocked: false });
    restoreReq.flush({ track_id: 107, blocked: false });
    expect(component['blockedTracks']().some((item) => item.track_id === 107)).toBe(false);

    component['selectTab']('reviews');
    const reviewCount = component['topReviews']().length;
    component['removeReview'](502);
    const deleteReviewReq = httpMock.expectOne('/api/reviews/502');
    expect(deleteReviewReq.request.method).toBe('DELETE');
    deleteReviewReq.flush({ success: true });
    expect(component['topReviews']().length).toBe(reviewCount - 1);
    expect(state.isUsingLocalFallback()).toBe(false);
  });

  it('updates track genre and compacts/synchronizes catalog', () => {
    const state = TestBed.inject(AdminStateService);
    const component = TestBed.runInInjectionContext(() => new AdminModerationComponent());

    const track = state.activeTracks()[0]!;
    component['startEditingGenre'](track);
    expect(component['editingTrackId']()).toBe(track.track_id);
    expect(component['editGenreDraft']()).toBe(track.genre);

    component['editGenreDraft'].set('Rock Clássico');
    component['saveGenre'](track.track_id);

    const genreReq = httpMock.expectOne(`/api/admin/tracks/${track.track_id}/genre`);
    expect(genreReq.request.method).toBe('PUT');
    expect(genreReq.request.body).toEqual({ genre: 'Rock Clássico' });
    genreReq.flush({ track_id: track.track_id, genre: 'Rock Clássico' });

    expect(component['editingTrackId']()).toBeNull();
    expect(state.activeTracks().find((t) => t.track_id === track.track_id)?.genre).toBe(
      'Rock Clássico',
    );

    component['compactCatalog']();
    const compactReq = httpMock.expectOne('/api/admin/catalog/compact');
    expect(compactReq.request.method).toBe('POST');
    compactReq.flush({
      new_version: 10,
      message: 'Catálogo compactado com sucesso (Delta Tables).',
    });
    expect(component['catalogActionStatus']()).toContain('compactado com sucesso');

    component['syncCatalog']();
    const syncReq = httpMock.expectOne('/api/admin/catalog/sync?force=false');
    expect(syncReq.request.method).toBe('POST');
    syncReq.flush({
      synced: true,
      version: 10,
      message: 'Catálogo sincronizado com sucesso.',
    });
    expect(component['catalogActionStatus']()).toContain('sincronizado com sucesso');
  });
});
