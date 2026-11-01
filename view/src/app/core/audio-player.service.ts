import { Injectable, signal, OnDestroy } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class AudioPlayerService implements OnDestroy {
  readonly isPlaying = signal<boolean>(false);
  readonly progress = signal<number>(24);
  readonly volume = signal<number>(70);

  private intervalId: ReturnType<typeof setInterval> | null = null;

  play(): void {
    if (this.isPlaying()) return;
    this.isPlaying.set(true);
    this.startTicker();
  }

  pause(): void {
    if (!this.isPlaying()) return;
    this.isPlaying.set(false);
    this.stopTicker();
  }

  togglePlay(): void {
    if (this.isPlaying()) {
      this.pause();
    } else {
      this.play();
    }
  }

  setProgress(val: number): void {
    const clamped = Math.max(0, Math.min(100, val));
    this.progress.set(clamped);
  }

  resetProgress(): void {
    this.progress.set(0);
  }

  setVolume(val: number): void {
    const clamped = Math.max(0, Math.min(100, val));
    this.volume.set(clamped);
  }

  ngOnDestroy(): void {
    this.stopTicker();
  }

  private startTicker(): void {
    this.stopTicker();
    this.intervalId = setInterval(() => {
      this.progress.update((current) => (current >= 100 ? 0 : current + 0.4));
    }, 1000);
  }

  private stopTicker(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }
}
