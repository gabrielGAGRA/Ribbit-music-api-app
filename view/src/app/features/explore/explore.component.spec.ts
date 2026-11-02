import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { ExploreComponent } from './explore.component';
import { authInterceptor } from '../../core/auth.interceptor';
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
});
