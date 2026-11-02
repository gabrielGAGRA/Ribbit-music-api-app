import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AudioPlayerService } from './audio-player.service';

describe('AudioPlayerService', () => {
  let player: AudioPlayerService;

  beforeEach(() => {
    vi.useFakeTimers();
    player = new AudioPlayerService();
  });

  afterEach(() => {
    player.ngOnDestroy();
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

  it('should advance progress over time while playing via ticker fallback', () => {
    player.play();
    expect(player.isPlaying()).toBe(true);

    const initial = player.progress();
    vi.advanceTimersByTime(1000);
    expect(player.progress()).toBeGreaterThan(initial);
  });

  it('should fall back gracefully to visual ticker when HTMLAudioElement play rejects', async () => {
    player.loadTrack('https://cdn.ribbit.app/broken-preview.m4a');
    player.play();
    await Promise.resolve();

    expect(player.isPlaying()).toBe(true);
    vi.advanceTimersByTime(1000);
    expect(player.progress()).toBeGreaterThan(0);
  });

  it('should allow setting custom progress, volume, and resetting progress', () => {
    player.setProgress(50);
    expect(player.progress()).toBe(50);

    player.setVolume(85);
    expect(player.volume()).toBe(85);

    player.resetProgress();
    expect(player.progress()).toBe(0);
  });
});
