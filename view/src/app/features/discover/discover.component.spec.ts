import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { DiscoverComponent } from './discover.component';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { AudioPlayerService } from '../../core/audio-player.service';

describe('DiscoverComponent', () => {
  let component: DiscoverComponent;
  let state: RibbitStateService;
  let player: AudioPlayerService;

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    state = new RibbitStateService();
    player = new AudioPlayerService();
    component = new DiscoverComponent(state, player);
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
    expect(state.history()[0].kind).toBe('like');
  });

  it('should toggle audio playback', () => {
    expect(player.isPlaying()).toBe(false);
    component.togglePlay();
    expect(player.isPlaying()).toBe(true);
  });

  it('should handle mode selection', () => {
    component.selectMode('Por Referência');
    expect(state.mode()).toBe('Por Referência');
  });

  it('should guarantee strictly mutually exclusive activeDragAction', () => {
    // Negligible drag below threshold
    component.drag.set({ x: 10, y: -15 });
    expect(component.activeDragAction()).toBeNull();

    // Diagonal drag where horizontal dominates right (like)
    component.drag.set({ x: 90, y: -70 });
    expect(component.activeDragAction()).toBe('like');

    // Diagonal drag where vertical dominates up (love)
    component.drag.set({ x: 60, y: -90 });
    expect(component.activeDragAction()).toBe('love');

    // Diagonal drag where horizontal dominates left (reject)
    component.drag.set({ x: -85, y: -60 });
    expect(component.activeDragAction()).toBe('reject');

    // Drag downwards
    component.drag.set({ x: 0, y: 70 });
    expect(component.activeDragAction()).toBeNull();
  });

  it('should define responsive mobile rules for discovery toolbar, deck card, and swipe controls', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');

    expect(globalStyles).toMatch(/\.empty-card\s*\{[^}]*display:\s*flex/);
    expect(globalStyles).toMatch(/\.album-lettering\s*\{[^}]*pointer-events:\s*none/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.discovery-toolbar\s*\{[^}]*flex-wrap:\s*wrap/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.discovery-card[^{]*\{[^}]*clamp\(/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*480px\)[\s\S]*\.swipe-controls\s*\{[^}]*gap:/);
  });
});
