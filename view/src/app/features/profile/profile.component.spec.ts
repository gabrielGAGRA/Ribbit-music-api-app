import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProfileComponent } from './profile.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/song.service';

describe('ProfileComponent', () => {
  let component: ProfileComponent;
  let state: RibbitStateService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    component = TestBed.runInInjectionContext(() => new ProfileComponent());
  });

  it('should switch between like, love, reject, and history tabs', () => {
    expect(component['selectedTab']()).toBe('like');
    component['selectTab']('love');
    expect(component['selectedTab']()).toBe('love');
    component['selectTab']('history');
    expect(component['selectedTab']()).toBe('history');
    expect(component['activeTabLabel']()).toBe('Histórico de acessos');
  });

  it('should calculate real counts from state collections', () => {
    expect(component['likeCount']()).toBe(0);
    state.decide('love');
    expect(component['likeCount']()).toBe(1);
    expect(component['loveCount']()).toBe(1);
    state.decide('reject');
    expect(component['rejectCount']()).toBe(1);
  });

  it('should cancel subscription to free plan', () => {
    state.setPlan('Individual');
    expect(state.currentPlan()).toBe('Individual');

    component['cancelSubscription']();
    expect(state.currentPlan()).toBe('Free');
    expect(state.toast()).toContain('cancelada');
  });

  it('should set page to settings on goToSettings', () => {
    component['goToSettings']();
    expect(state.activePage()).toBe('settings');
  });

  it('should stack profile account management, collections toolbar, and dashboard columns on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');

    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.account-management\s*\{[^}]*flex-direction:\s*column/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.collection-toolbar\s*\{[^}]*flex-direction:\s*column/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.dashboard-columns\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
  });

  it('should render profile quick-link pills without trailing icons', () => {
    const template = readFileSync(resolve(__dirname, './profile.component.html'), 'utf8');
    const tagsSection = template.match(/<div class="preferences-tags">[\s\S]*?<\/div>/)?.[0] ?? '';

    expect(tagsSection).toContain('Dashboard anual');
    expect(tagsSection).not.toContain('<app-icon');
  });

  it('should list only the authenticated user reviews in userReviews()', () => {
    const songService = TestBed.inject(SongService);
    const reviewsSignal = (
      songService as unknown as {
        reviewsSignal: { set: (items: readonly Record<string, unknown>[]) => void };
      }
    ).reviewsSignal;
    state.userId.set(7);
    reviewsSignal.set([
      {
        id: 1,
        userId: 7,
        author: 'Meu Usuário',
        initials: 'MU',
        text: 'Excelente faixa!',
        likes: 3,
        rating: 5,
        age: 'agora',
        date: 100,
      },
      {
        id: 2,
        userId: 99,
        author: 'Outro Usuário',
        initials: 'OU',
        text: 'Curti bastante.',
        likes: 1,
        rating: 4,
        age: 'ontem',
        date: 90,
      },
    ]);

    expect(component['userReviews']().length).toBe(1);
    expect(component['userReviews']()[0]?.id).toBe(1);
    expect(component['userReviews']()[0]?.rating).toBe(5);
  });

  it('reloads user reviews immediately when deleteReview succeeds', () => {
    writeAuthToken('jwt-profile-token');
    const httpMock = TestBed.inject(HttpTestingController);
    const state = TestBed.inject(RibbitStateService);
    const refreshSpy = vi.spyOn(state, 'refreshCatalogAndFeed').mockImplementation(() => undefined);

    component['deleteReview']({
      id: 77,
      author: 'Eu',
      initials: 'EU',
      text: 'Teste',
      likes: 0,
      age: 'agora',
      date: 100,
    });

    const delReq = httpMock.expectOne('/api/reviews/77');
    expect(delReq.request.method).toBe('DELETE');
    delReq.flush({ success: true });

    const meReq = httpMock.expectOne('/api/reviews/me?limit=50');
    expect(meReq.request.method).toBe('GET');
    meReq.flush([]);

    expect(refreshSpy).toHaveBeenCalledOnce();
    localStorage.clear();
  });

  it('derives deduplicated historySongs from state.accessHistory and toggles historyExpanded', () => {
    state.accessHistory.set(
      Array.from({ length: 8 }, (_, idx) => ({
        access_id: idx + 1,
        user_id: 1,
        track_id: idx === 7 ? 1 : idx + 1,
        track_title: `Faixa ${idx + 1}`,
        track_artist: 'Artista Teste',
        track_genre: 'Pop',
        track_album: 'Álbum',
        track_duration_seconds: 180,
        track_cover_url: null,
        track_preview_url: null,
        track_explicit: false,
        track_is_deleted: false,
        source: 'play',
        accessed_at: '2026-11-21T12:00:00Z',
      })),
    );

    component['selectTab']('history');
    expect(component['historyCount']()).toBe(7);
    expect(component['activeTabItems']().length).toBe(6);

    component['toggleHistory']();
    expect(component['historyExpanded']()).toBe(true);
    expect(component['activeTabItems']().length).toBe(7);

    const template = readFileSync(resolve(__dirname, './profile.component.html'), 'utf8');
    expect(template).toContain('Histórico');
    expect(template).toContain('Ouvido');
  });
});
