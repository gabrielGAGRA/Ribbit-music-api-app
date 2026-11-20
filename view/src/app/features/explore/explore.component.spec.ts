import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { ExploreComponent } from './explore.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('ExploreComponent', () => {
  let component: ExploreComponent;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    component = TestBed.runInInjectionContext(() => new ExploreComponent());
  });

  it('should filter songs based on search query', () => {
    component.query.set('Bloom');
    expect(component.filteredSongs().length).toBe(1);
    expect(component.filteredSongs()[0]?.title).toBe('Bloom');

    component.query.set('Inexistente123');
    expect(component.filteredSongs().length).toBe(0);
  });

  it('should filter songs by artist filter and clear it via clearQuery', () => {
    const state = TestBed.inject(RibbitStateService);
    const firstSong = state.songs()[0]!;

    state.searchFilterArtist.set(firstSong.artist);
    expect(component.hasActiveSearch()).toBe(true);
    expect(component.filteredSongs().some((s) => s.artist === firstSong.artist)).toBe(true);

    component.clearQuery();
    expect(state.searchFilterArtist()).toBe('');
    expect(component.hasActiveSearch()).toBe(false);
  });

  it('should filter songs by start and end dates and clear them via clearQuery', () => {
    const state = TestBed.inject(RibbitStateService);
    const firstSong = state.songs()[0]!;
    const songYear = Number(firstSong.year);

    state.searchFilterStartDate.set(`${songYear}-01-01`);
    state.searchFilterEndDate.set(`${songYear}-12-31`);
    expect(component.hasActiveSearch()).toBe(true);
    expect(component.filteredSongs().every((s) => Number(s.year) === songYear)).toBe(true);

    component.clearQuery();
    expect(state.searchFilterStartDate()).toBe('');
    expect(state.searchFilterEndDate()).toBe('');
    expect(component.hasActiveSearch()).toBe(false);
  });

  it('should toggle history expansion', () => {
    expect(component.historyExpanded()).toBe(false);
    component.toggleHistory();
    expect(component.historyExpanded()).toBe(true);
  });

  it('should toggle review likes and sort reviews', () => {
    const reviewId = 1;
    expect(component.reviewLikes()[reviewId]).toBeFalsy();
    component.toggleReviewLike(reviewId);
    expect(component.reviewLikes()[reviewId]).toBe(true);

    component.reviewSort.set('likes');
    const sorted = component.sortedReviews();
    expect(sorted[0]?.id).toBe(reviewId);
  });

  it('should open track details modal via RibbitStateService', () => {
    const state = TestBed.inject(RibbitStateService);
    const firstSong = state.songs()[0]!;
    component.openSongDetails(firstSong);
    expect(state.activeModal()).toBe('details');
    expect(state.detailsTargetSong().title).toBe(firstSong.title);
  });

  it('should collapse community reviews grid on tablet and mobile viewports', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');

    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*900px\)[\s\S]*\.community-reviews\s*\{[^}]*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*600px\)[\s\S]*\.community-reviews\s*\{[^}]*minmax\(0,\s*1fr\)/,
    );
  });

  it('should call songService.likeAndSaveSearchTrack when likeAndSaveTrack is triggered', () => {
    const httpMock = TestBed.inject(HttpTestingController);
    const state = TestBed.inject(RibbitStateService);
    const song = {
      trackId: 42,
      title: 'Solar Power',
      artist: 'Lorde',
      genre: 'Indie',
      time: '3:12',
      image: 'https://example.com/solar.jpg',
      album: 'Solar Power',
      year: '2021',
      match: 95,
    };

    component.likeAndSaveTrack(song);
    const req = httpMock.expectOne('/api/reviews/42/like-and-save');
    expect(req.request.method).toBe('POST');
    req.flush({ success: true });

    expect(state.toast()).toContain('adicionada às suas curtidas');
  });

  it('should immediately execute server search on form submit / search button click', () => {
    writeAuthToken('jwt-search-token');
    const httpMock = TestBed.inject(HttpTestingController);
    component.query.set('Bloom');

    component.onSearchSubmit(new Event('submit'));

    const req = httpMock.expectOne(
      (r) => r.url === '/api/tracks/search' && r.params.get('query') === 'Bloom',
    );
    expect(req.request.method).toBe('GET');
    req.flush([
      {
        track_id: 99,
        title: 'Bloom',
        artist: 'The Paper Kites',
        genre: 'Indie',
        duration_seconds: 210,
      },
    ]);

    expect(component.filteredSongs().length).toBe(1);
    expect(component.filteredSongs()[0]?.title).toBe('Bloom');
  });

  it('should render star ratings on community review cards', () => {
    const template = readFileSync(resolve(__dirname, './explore.component.html'), 'utf8');

    expect(template).toContain('class="review-stars"');
    expect(template).toContain('review.rating');
    expect(component.displayedReviews().every((r) => typeof r.rating === 'number')).toBe(true);
  });

  it('returns empty recentSongs when no access or interaction history exists and records search access on selectSong', () => {
    const state = TestBed.inject(RibbitStateService);
    expect(component.recentSongs()).toEqual([]);

    const song = state.songs()[0];
    expect(song).toBeDefined();
    if (song && song.trackId !== undefined) {
      component.selectSong(song);
      expect(state.isTrackSeen(song.trackId)).toBe(true);
    }

    const template = readFileSync(resolve(__dirname, './explore.component.html'), 'utf8');
    expect(template).toContain('Nenhuma faixa ouvida recentemente');
    expect(template).toContain('Ouvido');
  });
});
