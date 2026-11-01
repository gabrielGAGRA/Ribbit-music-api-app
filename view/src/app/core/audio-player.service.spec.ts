import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { AudioPlayerService } from './audio-player.service';

describe('AudioPlayerService', () => {
  let player: AudioPlayerService;

  beforeEach(() => {
    vi.useFakeTimers();
    player = new AudioPlayerService();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should initialize with playing false and default progress/volume', () => {
    expect(player.isPlaying()).toBe(false);
    expect(player.progress()).toBe(24);
    expect(player.volume()).toBe(70);
  });

  it('should toggle playing state', () => {
    player.togglePlay();
    expect(player.isPlaying()).toBe(true);

    player.togglePlay();
    expect(player.isPlaying()).toBe(false);
  });

  it('should advance progress over time while playing', () => {
    player.play();
    expect(player.isPlaying()).toBe(true);

    const initial = player.progress();
    vi.advanceTimersByTime(1000);
    expect(player.progress()).toBeGreaterThan(initial);
  });

  it('should allow setting custom progress and volume', () => {
    player.setProgress(50);
    expect(player.progress()).toBe(50);

    player.setVolume(85);
    expect(player.volume()).toBe(85);
  });

  it('should reset progress when asked', () => {
    player.setProgress(75);
    player.resetProgress();
    expect(player.progress()).toBe(0);
  });
});
