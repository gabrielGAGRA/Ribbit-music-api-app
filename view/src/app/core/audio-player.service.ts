import type { OnDestroy } from '@angular/core';
import { Injectable, signal } from '@angular/core';

/** Controls track preview playback using HTML5 Audio with automatic 30s visual ticker fallback. */
@Injectable({ providedIn: 'root' })
export class AudioPlayerService implements OnDestroy {
  readonly isPlaying = signal<boolean>(false);
  readonly progress = signal<number>(24);
  readonly volume = signal<number>(70);
  readonly activePreviewUrl = signal<string | null>(null);
  readonly usingRealAudio = signal<boolean>(false);

  private static readonly SILENT_WAV_DATA_URI =
    'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';

  private intervalId: ReturnType<typeof setInterval> | null = null;
  private audioElement: HTMLAudioElement | null = null;
  private unlocked = false;
  private isUnlocking = false;

  /**
   * Unlocks audio playback on a persistent HTMLAudioElement inside a user gesture
   * so subsequent programmatic track transitions (e.g. after swipe animations) play audio.
   */
  unlock(): void {
    if (
      this.unlocked ||
      (this.isPlaying() && this.usingRealAudio()) ||
      typeof Audio === 'undefined'
    ) {
      return;
    }
    if (!this.audioElement) {
      this.attachAudioElement(AudioPlayerService.SILENT_WAV_DATA_URI);
    }
    const audio = this.audioElement;
    if (!audio) return;

    this.isUnlocking = true;
    audio.muted = true;
    try {
      const playPromise = audio.play();
      if (playPromise && typeof playPromise.then === 'function') {
        playPromise.then(
          () => {
            this.unlocked = true;
            if (this.isUnlocking && this.audioElement === audio) {
              audio.pause();
              audio.currentTime = 0;
              audio.muted = false;
              this.isUnlocking = false;
            }
          },
          () => {
            if (this.isUnlocking && this.audioElement === audio) {
              audio.muted = false;
              this.isUnlocking = false;
            }
          },
        );
      } else {
        this.unlocked = true;
        audio.muted = false;
        this.isUnlocking = false;
      }
    } catch {
      audio.muted = false;
      this.isUnlocking = false;
    }
  }

  /** Configures a new track preview URL and resets playback progress. */
  loadTrack(previewUrl?: string): void {
    const wasPlaying = this.isPlaying();
    this.pause();
    this.isUnlocking = false;
    this.progress.set(0);

    if (!previewUrl || typeof Audio === 'undefined') {
      if (this.audioElement && !this.unlocked) {
        this.disposeAudioElement();
      } else if (this.audioElement) {
        this.audioElement.removeAttribute('src');
      }
      this.activePreviewUrl.set(null);
      this.usingRealAudio.set(false);
      return;
    }

    this.activePreviewUrl.set(previewUrl);
    if (this.audioElement) {
      this.audioElement.muted = false;
      this.audioElement.volume = this.volume() / 100;
      this.audioElement.src = previewUrl;
    } else {
      this.attachAudioElement(previewUrl);
    }
    if (wasPlaying) {
      this.play();
    }
  }

  /** Starts audio preview playback or falls back to the 30s visual ticker. */
  play(previewUrl?: string): void {
    if (previewUrl !== undefined && previewUrl !== this.activePreviewUrl()) {
      this.loadTrack(previewUrl);
    }
    if (this.isPlaying()) return;
    this.isPlaying.set(true);

    if (this.audioElement) {
      this.tryPlayAudioElement();
      return;
    }
    this.startTicker();
  }

  /** Pauses active audio or visual ticker playback. */
  pause(): void {
    this.isPlaying.set(false);
    if (this.audioElement) {
      this.audioElement.pause();
    }
    this.stopTicker();
  }

  /** Toggles between play and pause states. */
  togglePlay(): void {
    if (this.isPlaying()) {
      this.pause();
    } else {
      this.play();
    }
  }

  /** Seeks playback progress between 0 and 100%. */
  setProgress(val: number): void {
    const clamped = Math.max(0, Math.min(100, val));
    this.progress.set(clamped);
    if (
      this.audioElement &&
      this.usingRealAudio() &&
      Number.isFinite(this.audioElement.duration) &&
      this.audioElement.duration > 0
    ) {
      this.audioElement.currentTime = (clamped / 100) * this.audioElement.duration;
    }
  }

  /** Resets progress back to the start of the track. */
  resetProgress(): void {
    this.setProgress(0);
  }

  /** Adjusts output volume between 0 and 100%. */
  setVolume(val: number): void {
    const clamped = Math.max(0, Math.min(100, val));
    this.volume.set(clamped);
    if (this.audioElement) {
      this.audioElement.volume = clamped / 100;
    }
  }

  ngOnDestroy(): void {
    this.stopTicker();
    this.disposeAudioElement();
  }

  private attachAudioElement(previewUrl: string): void {
    try {
      const audio = new Audio(previewUrl);
      audio.preload = 'metadata';
      audio.volume = this.volume() / 100;
      audio.addEventListener('timeupdate', () => {
        if (this.audioElement !== audio || this.isUnlocking) return;
        if (Number.isFinite(audio.duration) && audio.duration > 0) {
          this.progress.set(Math.min(100, (audio.currentTime / audio.duration) * 100));
        }
      });
      audio.addEventListener('ended', () => {
        if (this.audioElement !== audio || this.isUnlocking) return;
        this.isPlaying.set(false);
        this.progress.set(0);
      });
      audio.addEventListener('error', () => {
        if (this.audioElement !== audio || this.isUnlocking) return;
        this.fallbackToTicker();
      });
      this.audioElement = audio;
    } catch {
      // Browser environment without working HTMLAudioElement falls back to visual ticker
      this.audioElement = null;
      this.usingRealAudio.set(false);
    }
  }

  private tryPlayAudioElement(): void {
    const audio = this.audioElement;
    if (!audio) {
      this.startTicker();
      return;
    }
    this.isUnlocking = false;
    audio.muted = false;
    try {
      const playPromise = audio.play();
      if (playPromise && typeof playPromise.then === 'function') {
        playPromise.then(
          () => {
            if (this.audioElement !== audio || !this.isPlaying()) {
              audio.pause();
              return;
            }
            this.unlocked = true;
            this.usingRealAudio.set(true);
            this.stopTicker();
          },
          () => {
            if (this.audioElement !== audio || !this.isPlaying()) {
              return;
            }
            this.fallbackToTicker();
          },
        );
      } else {
        this.fallbackToTicker();
      }
    } catch {
      // Synchronous NotSupportedError in headless/test DOM falls back to visual ticker
      this.fallbackToTicker();
    }
  }

  private fallbackToTicker(): void {
    this.disposeAudioElement();
    this.usingRealAudio.set(false);
    if (this.isPlaying()) {
      this.startTicker();
    }
  }

  private disposeAudioElement(): void {
    if (this.audioElement) {
      try {
        this.audioElement.pause();
        this.audioElement.removeAttribute('src');
      } catch {
        // Ignore cleanup errors on detached media elements
      }
      this.audioElement = null;
    }
    this.usingRealAudio.set(false);
  }

  private startTicker(): void {
    this.stopTicker();
    this.intervalId = setInterval(() => {
      this.progress.update((current) => (current >= 100 ? 0 : Math.min(100, current + 3.33)));
    }, 1000);
  }

  private stopTicker(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }
}
