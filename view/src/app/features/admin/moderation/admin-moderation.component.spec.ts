import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AdminModerationComponent } from './admin-moderation.component';
import { AdminStateService } from '../admin-state.service';

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

  function hydrateWithSampleData(state: AdminStateService): void {
    state.hydrateFromBackend();
    httpMock.expectOne('/api/admin/plans').flush([]);
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 2,
      estimated_net_revenue: 0,
      users_by_plan: {},
      revenue_by_plan: {},
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 2,
      total_tracks: 2,
      active_tracks: 2,
      blocked_genres: {},
    });
    httpMock.expectOne('/api/admin/users').flush([]);
    httpMock.expectOne('/api/admin/administrators').flush([]);
    httpMock.expectOne('/api/admin/tracks?limit=100').flush([
      {
        track_id: 101,
        title: 'Bohemian Rhapsody',
        artist: 'Queen',
        duration_seconds: 354,
        genre: 'Rock',
        explicit: false,
        is_deleted: false,
      },
      {
        track_id: 107,
        title: 'Horizonte Azul',
        artist: 'Boogarins',
        duration_seconds: 264,
        genre: 'Psicodélico',
        explicit: false,
        is_deleted: false,
      },
    ]);
    httpMock.expectOne('/api/admin/blocked-tracks').flush([]);
    httpMock.expectOne('/api/admin/reviews').flush([
      {
        review_id: 502,
        user_id: 8,
        track_id: 101,
        rating: 2,
        text: 'Avaliação reportada',
        likes_count: 31,
        is_deleted: false,
        author_name: 'Ouvinte',
        track_title: 'Bohemian Rhapsody',
        track_artist: 'Queen',
      },
    ]);
  }

  it('searches active tracks, toggles explicit/+18, blocks/restores tracks, and deletes reviews', () => {
    const state = TestBed.inject(AdminStateService);
    hydrateWithSampleData(state);
    const component = TestBed.runInInjectionContext(() => new AdminModerationComponent());

    expect(component['formatDuration'](218)).toBe('3:38');
    expect(component['searchedActiveTracks']().length).toBe(2);

    component['trackQuery'].set('Boogarins');
    component['searchTracks']('Boogarins');
    const searchReq = httpMock.expectOne('/api/admin/tracks?limit=100&query=Boogarins');
    expect(searchReq.request.method).toBe('GET');
    searchReq.flush([
      {
        track_id: 107,
        title: 'Horizonte Azul',
        artist: 'Boogarins',
        duration_seconds: 264,
        genre: 'Psicodélico',
        explicit: false,
        is_deleted: false,
      },
    ]);
    expect(component['searchedActiveTracks']().length).toBe(1);

    const targetTrack = component['searchedActiveTracks']()[0]!;
    expect(targetTrack.explicit).toBe(false);
    component['toggleExplicit'](targetTrack);
    const explicitReq = httpMock.expectOne('/api/admin/tracks/107/explicit');
    expect(explicitReq.request.method).toBe('PUT');
    expect(explicitReq.request.body).toEqual({ explicit: true });
    explicitReq.flush({ track_id: 107, explicit: true });
    expect(state.activeTracks().find((item) => item.trackId === 107)?.explicit).toBe(true);

    component['blockTrack'](107);
    const blockReq = httpMock.expectOne('/api/admin/tracks/107/block');
    expect(blockReq.request.method).toBe('PUT');
    expect(blockReq.request.body).toEqual({ blocked: true });
    blockReq.flush({ track_id: 107, blocked: true });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 2,
      total_tracks: 2,
      active_tracks: 1,
      blocked_genres: {},
    });
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 2,
      estimated_net_revenue: 100,
      users_by_plan: {},
      revenue_by_plan: {},
    });
    expect(component['blockedTracks']().some((item) => item.trackId === 107)).toBe(true);

    component['selectTab']('blocked');
    component['restoreTrack'](107);
    const restoreReq = httpMock.expectOne('/api/admin/tracks/107/block');
    expect(restoreReq.request.method).toBe('PUT');
    expect(restoreReq.request.body).toEqual({ blocked: false });
    restoreReq.flush({ track_id: 107, blocked: false });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 2,
      total_tracks: 2,
      active_tracks: 2,
      blocked_genres: {},
    });
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 2,
      estimated_net_revenue: 100,
      users_by_plan: {},
      revenue_by_plan: {},
    });
    expect(component['blockedTracks']().some((item) => item.trackId === 107)).toBe(false);

    component['selectTab']('reviews');
    const reviewCount = component['topReviews']().length;
    component['removeReview'](502);
    const deleteReviewReq = httpMock.expectOne('/api/admin/reviews/502');
    expect(deleteReviewReq.request.method).toBe('DELETE');
    deleteReviewReq.flush({ success: true });
    expect(component['topReviews']().length).toBe(reviewCount - 1);
  });

  it('updates track genre and compacts/synchronizes catalog', () => {
    const state = TestBed.inject(AdminStateService);
    hydrateWithSampleData(state);
    const component = TestBed.runInInjectionContext(() => new AdminModerationComponent());

    const track = state.activeTracks()[0]!;
    component['startEditingGenre'](track);
    expect(component['editingTrackId']()).toBe(track.trackId);
    expect(component['editGenreDraft']()).toBe(track.genre);

    component['editGenreDraft'].set('Rock Clássico');
    component['saveGenre'](track.trackId);

    const genreReq = httpMock.expectOne(`/api/admin/tracks/${track.trackId}/genre`);
    expect(genreReq.request.method).toBe('PUT');
    expect(genreReq.request.body).toEqual({ genre: 'Rock Clássico' });
    genreReq.flush({ track_id: track.trackId, genre: 'Rock Clássico' });

    expect(component['editingTrackId']()).toBeNull();
    expect(state.activeTracks().find((t) => t.trackId === track.trackId)?.genre).toBe(
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
      synced: false,
      version: 10,
      message: 'Catálogo sincronizado com sucesso.',
    });
    expect(component['catalogActionStatus']()).toContain('sincronizado com sucesso');
    component.ngOnDestroy();
  });

  it('cancels stale in-flight catalog searches and resets filtered list when re-entering moderation', () => {
    const state = TestBed.inject(AdminStateService);
    hydrateWithSampleData(state);
    const component = TestBed.runInInjectionContext(() => new AdminModerationComponent());
    component.ngOnInit();

    component['searchTracks']('a');
    const firstReq = httpMock.expectOne('/api/admin/tracks?limit=100&query=a');

    component['searchTracks']('Boogarins');
    expect(firstReq.cancelled).toBe(true);

    const secondReq = httpMock.expectOne('/api/admin/tracks?limit=100&query=Boogarins');
    secondReq.flush([
      {
        track_id: 107,
        title: 'Horizonte Azul',
        artist: 'Boogarins',
        duration_seconds: 264,
        genre: 'Psicodélico',
        explicit: false,
        is_deleted: false,
      },
    ]);
    expect(component['searchedActiveTracks']().length).toBe(1);
    expect(state.lastCatalogQuery()).toBe('Boogarins');
    component.ngOnDestroy();

    const reopened = TestBed.runInInjectionContext(() => new AdminModerationComponent());
    reopened.ngOnInit();
    const resetReq = httpMock.expectOne('/api/admin/tracks?limit=100');
    resetReq.flush([
      {
        track_id: 101,
        title: 'Bohemian Rhapsody',
        artist: 'Queen',
        duration_seconds: 354,
        genre: 'Rock',
        explicit: false,
        is_deleted: false,
      },
      {
        track_id: 107,
        title: 'Horizonte Azul',
        artist: 'Boogarins',
        duration_seconds: 264,
        genre: 'Psicodélico',
        explicit: false,
        is_deleted: false,
      },
    ]);
    expect(reopened['searchedActiveTracks']().length).toBe(2);
    expect(state.lastCatalogQuery()).toBe('');
    reopened.ngOnDestroy();
  });

  it('filters by title and artist, shows external candidates, adds one to delta table, and filters by dislikes', () => {
    const component = TestBed.runInInjectionContext(() => new AdminModerationComponent());
    component.ngOnInit();

    component['toggleCreateTrackForm']();
    expect(component['showCreateTrackForm']()).toBe(true);

    component['newTrackTitle'].set('Neon Pulse');
    component['newTrackArtist'].set('Synth Unit');
    component['searchExternalTracks'](new Event('submit'));

    const searchExternalReq = httpMock.expectOne(
      '/api/admin/tracks/external-search?limit=10&title=Neon%20Pulse&artist=Synth%20Unit',
    );
    expect(searchExternalReq.request.method).toBe('GET');
    searchExternalReq.flush([
      {
        title: 'Neon Pulse',
        artist: 'Synth Unit',
        duration_seconds: 210,
        genre: 'Electronic',
        spotify_id: 'sp-neon',
        album: null,
        country: null,
        release_year: 2024,
        cover_url: 'https://example.com/neon.jpg',
        itunes_preview_url: null,
        explicit: false,
        already_in_catalog: false,
      },
    ]);

    expect(component['externalCandidates']().length).toBe(1);
    const candidate = component['externalCandidates']()[0]!;
    component['addCandidateToDelta'](candidate);

    const postReq = httpMock.expectOne('/api/admin/tracks');
    expect(postReq.request.method).toBe('POST');
    expect(postReq.request.body).toEqual({
      title: 'Neon Pulse',
      artist: 'Synth Unit',
      genre: 'Electronic',
      duration_seconds: 210,
      release_year: 2024,
      cover_url: 'https://example.com/neon.jpg',
      spotify_id: 'sp-neon',
      explicit: false,
    });
    postReq.flush({
      track_id: 999,
      title: 'Neon Pulse',
      artist: 'Synth Unit',
      duration_seconds: 210,
      genre: 'Electronic',
      explicit: false,
      is_deleted: false,
      likes_count: 0,
      dislikes_count: 0,
      superlikes_count: 0,
    });
    httpMock.expectOne('/api/admin/audience').flush({
      total_users: 10,
      total_tracks: 21,
      active_tracks: 21,
      blocked_genres: {},
    });
    httpMock.expectOne('/api/admin/dashboard').flush({
      total_users: 10,
      estimated_net_revenue: 100,
      users_by_plan: {},
      revenue_by_plan: {},
    });

    expect(component['externalCandidates']()[0]?.alreadyInCatalog).toBe(true);
    const adminState = TestBed.inject(AdminStateService);
    expect(adminState.activeTracks().some((t) => t.trackId === 999)).toBe(true);

    component['updateCatalogSort']({
      target: { value: 'dislikes_desc' },
    } as unknown as Event);
    const sortReq = httpMock.expectOne('/api/admin/tracks?limit=100&sort_by=dislikes_desc');
    sortReq.flush([]);

    component['toggleOnlyDisliked']();
    const dislikeReq = httpMock.expectOne(
      '/api/admin/tracks?limit=100&sort_by=dislikes_desc&min_dislikes=1',
    );
    dislikeReq.flush([]);
    component.ngOnDestroy();
  });

  it('formats track duration, manages genre editing cancellation, and renders star arrays', () => {
    const state = TestBed.inject(AdminStateService);
    hydrateWithSampleData(state);
    const component = TestBed.runInInjectionContext(() => new AdminModerationComponent());

    expect(component['formatDuration'](185)).toBe('3:05');
    expect(component['starArray'](4)).toEqual([0, 1, 2, 3]);

    const track = state.activeTracks()[0]!;
    component['startEditingGenre'](track);
    const input = document.createElement('input');
    input.value = 'Jazz';
    component['updateGenreDraft']({ target: input } as unknown as Event);
    expect(component['editGenreDraft']()).toBe('Jazz');
    component['cancelEditingGenre']();
    expect(component['editingTrackId']()).toBeNull();

    component['updateTrackQuery']({ target: input } as unknown as Event);
    expect(component['trackQuery']()).toBe('Jazz');

    component['editGenreDraft'].set('');
    component['saveGenre'](track.trackId);

    component['toggleExplicit'](track);
    httpMock
      .expectOne(`/api/admin/tracks/${track.trackId}/explicit`)
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });
    expect(component['moderationError']()).toBeTruthy();

    component['blockTrack'](track.trackId);
    httpMock
      .expectOne(`/api/admin/tracks/${track.trackId}/block`)
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    component['restoreTrack'](track.trackId);
    httpMock
      .expectOne(`/api/admin/tracks/${track.trackId}/block`)
      .flush({ detail: 'Err' }, { status: 400, statusText: 'Bad' });

    component.ngOnDestroy();
  });
});
