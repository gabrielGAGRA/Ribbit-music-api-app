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

  it('should keep audio paused if pause is called before play promise resolves', async () => {
    let resolvePlay!: () => void;
    const pauseSpy = vi.fn();
    const fakeAudio = {
      preload: 'metadata',
      volume: 0.7,
      duration: 30,
      currentTime: 0,
      addEventListener: vi.fn(),
      removeAttribute: vi.fn(),
      play: vi.fn(
        () =>
          new Promise<void>((resolve) => {
            resolvePlay = resolve;
          }),
      ),
      pause: pauseSpy,
    };
    const originalAudio = globalThis.Audio;
    function MockAudio() {
      return fakeAudio;
    }
    vi.stubGlobal('Audio', MockAudio);

    try {
      player.loadTrack('https://cdn.ribbit.app/preview.mp3');
      player.play();
      expect(player.isPlaying()).toBe(true);

      player.pause();
      expect(player.isPlaying()).toBe(false);
      expect(pauseSpy).toHaveBeenCalledTimes(1);

      resolvePlay();
      await Promise.resolve();

      expect(player.isPlaying()).toBe(false);
      expect(pauseSpy).toHaveBeenCalledTimes(2);
    } finally {
      vi.stubGlobal('Audio', originalAudio);
    }
  });

  it('should preserve audio element when play rejects after pause (AbortError)', async () => {
    let rejectPlay!: (reason?: unknown) => void;
    const playSpy = vi.fn(
      () =>
        new Promise<void>((_resolve, reject) => {
          rejectPlay = reject;
        }),
    );
    const pauseSpy = vi.fn();
    const fakeAudio = {
      preload: 'metadata',
      volume: 0.7,
      duration: 30,
      currentTime: 0,
      addEventListener: vi.fn(),
      removeAttribute: vi.fn(),
      play: playSpy,
      pause: pauseSpy,
    };
    const originalAudio = globalThis.Audio;
    function MockAudio() {
      return fakeAudio;
    }
    vi.stubGlobal('Audio', MockAudio);

    try {
      player.loadTrack('https://cdn.ribbit.app/preview.mp3');
      player.play();
      expect(player.isPlaying()).toBe(true);

      player.pause();
      expect(player.isPlaying()).toBe(false);

      rejectPlay(
        new DOMException('The play() request was interrupted by a call to pause()', 'AbortError'),
      );
      await Promise.resolve();

      expect(player.isPlaying()).toBe(false);
      expect(fakeAudio.removeAttribute).not.toHaveBeenCalled();

      player.play();
      expect(playSpy).toHaveBeenCalledTimes(2);
    } finally {
      vi.stubGlobal('Audio', originalAudio);
    }
  });

  it('unlocks once on a persistent HTMLAudioElement and reuses it across loadTrack calls', async () => {
    const originalAudio = globalThis.Audio;
    const playSpy = vi.fn(() => Promise.resolve());
    const pauseSpy = vi.fn();
    const audioConstructor = vi.fn();
    const instances: MockAudio[] = [];

    class MockAudio {
      src = '';
      preload = '';
      volume = 1;
      muted = false;
      duration = 30;
      currentTime = 5;
      addEventListener = vi.fn();
      removeAttribute = vi.fn();
      play = playSpy;
      pause = pauseSpy;
      constructor(src?: string) {
        audioConstructor(src);
        if (src) this.src = src;
        instances.push(this);
      }
    }

    vi.stubGlobal('Audio', MockAudio);
    try {
      player.unlock();
      await Promise.resolve();

      expect(audioConstructor).toHaveBeenCalledTimes(1);
      expect(playSpy).toHaveBeenCalledTimes(1);
      expect(pauseSpy).toHaveBeenCalledTimes(1);
      expect(instances[0]?.muted).toBe(false);
      expect(player.isPlaying()).toBe(false);

      player.loadTrack('https://example.com/track-1.mp3');
      player.play();
      await Promise.resolve();
      expect(instances[0]?.src).toBe('https://example.com/track-1.mp3');

      player.loadTrack('https://example.com/track-2.mp3');
      player.play();
      await Promise.resolve();

      expect(audioConstructor).toHaveBeenCalledTimes(1);
      expect(instances[0]?.src).toBe('https://example.com/track-2.mp3');
      expect(playSpy).toHaveBeenCalledTimes(3);
      expect(player.isPlaying()).toBe(true);
    } finally {
      vi.stubGlobal('Audio', originalAudio);
    }
  });
});
