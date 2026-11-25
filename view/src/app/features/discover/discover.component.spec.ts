import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Song } from '@ribbit/shared-types';
import { DiscoverComponent } from './discover.component';
import { AudioPlayerService } from '../../core/audio-player.service';
import { authInterceptor } from '../../core/auth.interceptor';
import { RibbitStateService } from '../../core/ribbit-state.service';

const TEST_SONG: Song = {
  trackId: 1,
  title: 'Bloom',
  artist: 'Odesza',
  genre: 'Electronic',
  time: '3:15',
  image: 'https://example.com/bloom.jpg',
  album: 'In Return',
  year: '2014',
  match: 95,
};

describe('DiscoverComponent', () => {
  let component: DiscoverComponent;
  let state: RibbitStateService;
  let player: AudioPlayerService;

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    state.songs.set([TEST_SONG]);
    player = TestBed.inject(AudioPlayerService);
    component = TestBed.runInInjectionContext(() => new DiscoverComponent());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should initialize and display current song', () => {
    expect(component['currentSong']()).toBeDefined();
    expect(component['currentSong']().title).toBe('Bloom');
  });

  it('should trigger like, love, and reject decisions after animation', () => {
    component['submitDecision']('like');
    vi.advanceTimersByTime(300);

    expect(state.history().length).toBe(1);
    expect(state.history()[0]?.kind).toBe('like');
  });

  it('should toggle audio playback', () => {
    expect(player.isPlaying()).toBe(false);
    component['togglePlay']();
    expect(player.isPlaying()).toBe(true);
    component['togglePlay']();
    expect(player.isPlaying()).toBe(false);
  });

  it('should guarantee strictly mutually exclusive activeDragAction', () => {
    component['drag'].set({ x: 10, y: -15 });
    expect(component['activeDragAction']()).toBeNull();

    component['drag'].set({ x: 90, y: -70 });
    expect(component['activeDragAction']()).toBe('like');

    component['drag'].set({ x: 60, y: -90 });
    expect(component['activeDragAction']()).toBe('love');

    component['drag'].set({ x: -85, y: -60 });
    expect(component['activeDragAction']()).toBe('reject');

    component['drag'].set({ x: 0, y: 70 });
    expect(component['activeDragAction']()).toBeNull();
  });

  it('should define responsive mobile rules for discovery toolbar, deck card, and swipe controls', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');

    expect(globalStyles).toMatch(/\.empty-card\s*\{[^}]*display:\s*flex/);
    expect(globalStyles).not.toMatch(/\.album-lettering/);
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.discovery-toolbar\s*\{[^}]*flex-wrap:\s*wrap/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.discovery-card[^{]*\{[^}]*clamp\(/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*480px\)[\s\S]*\.swipe-controls\s*\{[^}]*gap:/,
    );
  });

  it('should not render overlay lettering with song and artist over the album artwork', () => {
    const template = readFileSync(resolve(__dirname, './discover.component.html'), 'utf8');

    expect(template).not.toContain('album-lettering');
    expect(template).not.toContain('name="sparkles"');
    expect(template).toContain('class="track-heading"');
  });

  it('should enforce full-width sizing on discovery stage and card containers to prevent horizontal flex collapse', () => {
    const discoverStyles = readFileSync(resolve(__dirname, './discover.component.css'), 'utf8');
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');

    expect(discoverStyles).toMatch(/:host\s*\{[^}]*(?:^|[;\s{])width:\s*100%/);
    expect(discoverStyles).toMatch(/\.discover-deck-column\s*\{[^}]*(?:^|[;\s{])width:\s*100%/);
    expect(discoverStyles).toMatch(
      /\.discover-deck-column\s+\.discovery-stage\s*\{[^}]*(?:^|[;\s{])width:\s*100%/,
    );
    expect(discoverStyles).toMatch(
      /@media\s*\(max-width:\s*1000px\)\s*\{\s*\.discover-layout\s*\{[^}]*display:\s*flex/,
    );
    expect(globalStyles).toMatch(/\.discovery-stage\s*\{[^}]*(?:^|[;\s{])width:\s*100%/);
    expect(globalStyles).toMatch(/\.discovery-card\s*\{[^}]*(?:^|[;\s{])width:\s*100%/);
    expect(globalStyles).toMatch(/\.empty-card\s*\{[^}]*(?:^|[;\s{])width:\s*100%/);
    expect(globalStyles).toMatch(/\.track-heading\s*>\s*div\s*\{[^}]*min-width:\s*0[^}]*flex:\s*1/);
    expect(globalStyles).toMatch(/\.track-heading\s+h2\s*\{[^}]*text-overflow:\s*ellipsis/);
    expect(globalStyles).toMatch(/\.track-heading\s+p\s*\{[^}]*text-overflow:\s*ellipsis/);
    expect(globalStyles).toMatch(/\.preview-play\s*\{[^}]*flex-shrink:\s*0/);
  });

  it('should render loading spinner markup and styles for song loading state', () => {
    const template = readFileSync(resolve(__dirname, './discover.component.html'), 'utf8');
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');

    expect(template).toContain('state.isLoadingDiscovery()');
    expect(template).toContain('class="vinyl-spinner"');
    expect(globalStyles).toContain('.vinyl-spinner');
    expect(globalStyles).toContain('@media (prefers-reduced-motion: reduce)');
  });

  it('returns to community explore and opens track reviews modal after swiping a community track', () => {
    const communitySong: Song = {
      trackId: 55,
      title: 'Community Pick',
      artist: 'Artist',
      genre: 'Rock',
      time: '3:00',
      image: 'https://example.com/community.jpg',
      album: 'Single',
      year: '2023',
      match: 91,
      previewUrl: 'https://audio.itunes.apple.com/preview.m4a',
    };
    state.openTrackForCommunitySwipe(communitySong);
    expect(state.activePage()).toBe('discover');
    expect(state.pendingCommunityReturnSong()).toEqual(communitySong);

    component['submitDecision']('like');
    vi.advanceTimersByTime(300);

    expect(state.history().some((entry) => entry.trackId === 55 && entry.kind === 'like')).toBe(
      true,
    );
    expect(state.pendingCommunityReturnSong()).toBeNull();
    expect(state.activePage()).toBe('explore');
    expect(state.activeModal()).toBe('details');
    expect(state.detailsTargetSong()).toEqual(communitySong);
    expect(player.isPlaying()).toBe(false);
  });

  it('stays on discover without opening reviews modal after a regular swipe', () => {
    state.setPage('discover');
    expect(state.pendingCommunityReturnSong()).toBeNull();

    component['submitDecision']('like');
    vi.advanceTimersByTime(300);

    expect(state.activePage()).toBe('discover');
    expect(state.activeModal()).toBeNull();
  });
});

describe('DiscoverComponent DOM', () => {
  let state: RibbitStateService;
  let player: AudioPlayerService;

  beforeEach(() => {
    localStorage.clear();
    const html = readFileSync(resolve(__dirname, './discover.component.html'), 'utf8');
    TestBed.overrideComponent(DiscoverComponent, {
      set: {
        template: html,
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [],
        imports: [],
        schemas: [NO_ERRORS_SCHEMA],
      },
    });
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    state.songs.set([TEST_SONG]);
    player = TestBed.inject(AudioPlayerService);
  });

  it('should not start card drag when pointerdown targets SVG icon inside preview play button', () => {
    const fixture = TestBed.createComponent(DiscoverComponent);
    fixture.detectChanges();

    const instance = fixture.componentInstance;
    instance['togglePlay']();
    expect(player.isPlaying()).toBe(true);
    fixture.detectChanges();

    const root = fixture.nativeElement;
    if (!(root instanceof HTMLElement)) {
      throw new TypeError('Expected root element');
    }
    const card = root.querySelector('.discovery-card');
    const playButton = root.querySelector('.preview-play');
    if (!(card instanceof HTMLElement) || !(playButton instanceof HTMLButtonElement)) {
      throw new Error('Expected discovery card and play button');
    }

    const iconHost = playButton.querySelector('app-icon') ?? playButton;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    svg.appendChild(rect);
    iconHost.appendChild(svg);

    const setPointerCaptureSpy = vi.fn();
    Object.defineProperty(card, 'setPointerCapture', {
      value: setPointerCaptureSpy,
      configurable: true,
    });

    rect.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, cancelable: true }));
    expect(instance['isDragging']()).toBe(false);
    expect(setPointerCaptureSpy).not.toHaveBeenCalled();

    playButton.click();
    expect(player.isPlaying()).toBe(false);
  });
});
