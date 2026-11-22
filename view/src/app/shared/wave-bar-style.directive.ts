import { Directive, ElementRef, effect, inject, input } from '@angular/core';

/** Applies procedural height and animation delay to audio visualizer waveform bars. */
@Directive({
  selector: '[appWaveBarIndex]',
  standalone: true,
})
export class WaveBarStyleDirective {
  private readonly elementRef = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly appWaveBarIndex = input.required<number>();

  constructor() {
    effect(() => {
      const idx = this.appWaveBarIndex();
      const heightPx = 8 + ((idx * 17 + idx * idx * 3) % 27);
      this.elementRef.nativeElement.style.height = `${heightPx}px`;
      this.elementRef.nativeElement.style.animationDelay = `${idx * 25}ms`;
    });
  }
}
