import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DiscoverComponent } from './discover.component';
import { AudioPlayerService } from '../../core/audio-player.service';
import { authInterceptor } from '../../core/auth.interceptor';
import { RibbitStateService } from '../../core/ribbit-state.service';

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
    player = TestBed.inject(AudioPlayerService);
    component = TestBed.runInInjectionContext(() => new DiscoverComponent());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should initialize and display current song', () => {
    expect(component.currentSong()).toBeDefined();
    expect(component.currentSong().title).toBe('Bloom');
  });

  it('should trigger like, love, and reject decisions after animation', () => {
    component.handleDecision('like');
    vi.advanceTimersByTime(300);

    expect(state.history().length).toBe(1);
    expect(state.history()[0]?.kind).toBe('like');
  });

  it('should toggle audio playback', () => {
    expect(player.isPlaying()).toBe(false);
    component.togglePlay();
    expect(player.isPlaying()).toBe(true);
    component.togglePlay();
    expect(player.isPlaying()).toBe(false);
  });

  it('should handle mode selection', () => {
    component.selectMode('Por Referência');
    expect(state.mode()).toBe('Por Referência');
  });

  it('should guarantee strictly mutually exclusive activeDragAction', () => {
    component.drag.set({ x: 10, y: -15 });
    expect(component.activeDragAction()).toBeNull();

    component.drag.set({ x: 90, y: -70 });
    expect(component.activeDragAction()).toBe('like');

    component.drag.set({ x: 60, y: -90 });
    expect(component.activeDragAction()).toBe('love');

    component.drag.set({ x: -85, y: -60 });
    expect(component.activeDragAction()).toBe('reject');

    component.drag.set({ x: 0, y: 70 });
    expect(component.activeDragAction()).toBeNull();
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
});
