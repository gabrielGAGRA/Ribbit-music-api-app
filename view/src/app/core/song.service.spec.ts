import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { SongService } from './song.service';

describe('SongService', () => {
  let service: SongService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SongService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('forwards minRating and sortBy in searchSongs without overwriting songsSignal', () => {
    const initialSongs = service.songs();

    service
      .searchSongs({
        query: 'Queen',
        minRating: 4,
        sortBy: 'rating_desc',
      })
      .subscribe((songs) => {
        expect(songs.length).toBe(1);
        expect(songs[0]?.averageRating).toBe(4.5);
        expect(songs[0]?.reviewCount).toBe(2);
      });

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/tracks/search' &&
        r.params.get('query') === 'Queen' &&
        r.params.get('min_rating') === '4' &&
        r.params.get('sort_by') === 'rating_desc',
    );
    expect(req.request.method).toBe('GET');
    req.flush([
      {
        track_id: 1,
        title: 'Bohemian Rhapsody',
        artist: 'Queen',
        duration_seconds: 354,
        genre: 'Rock',
        explicit: false,
        is_deleted: false,
        average_rating: 4.5,
        review_count: 2,
      },
    ]);

    expect(service.songs()).toBe(initialSongs);
    httpMock.verify();
  });

  it('loads community feed with default days=1 and forwards sortBy', () => {
    service.loadCommunityFeed({ sortBy: 'rating_asc', limit: 15 }).subscribe((reviews) => {
      expect(reviews.length).toBe(0);
    });

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/reviews/feed' &&
        r.params.get('limit') === '15' &&
        r.params.get('days') === '1' &&
        r.params.get('sort_by') === 'rating_asc',
    );
    expect(req.request.method).toBe('GET');
    req.flush([]);
    httpMock.verify();
  });

  it('forwards sortBy in getTrackReviews', () => {
    service.getTrackReviews({ trackId: 42, sortBy: 'rating_desc' }).subscribe();

    const req = httpMock.expectOne(
      (r) => r.url === '/api/reviews/track/42' && r.params.get('sort_by') === 'rating_desc',
    );
    expect(req.request.method).toBe('GET');
    req.flush([]);
    httpMock.verify();
  });
});
