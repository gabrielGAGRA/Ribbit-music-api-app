import { Directive, ElementRef, effect, inject, input } from '@angular/core';

/** Sets dynamic percentage width on progress fill bars without inline template style bindings. */
@Directive({
  selector: '[appWidthPercent]',
  standalone: true,
})
export class WidthPercentDirective {
  private readonly elementRef = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly appWidthPercent = input.required<number>();

  constructor() {
    effect(() => {
      const clamped = Math.max(0, Math.min(100, this.appWidthPercent()));
      this.elementRef.nativeElement.style.width = `${clamped}%`;
    });
  }
}

/** Applies computed CSS transform strings for swipeable cards without inline template style bindings. */
@Directive({
  selector: '[appTransform]',
  standalone: true,
})
export class TransformStyleDirective {
  private readonly elementRef = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly appTransform = input.required<string>();

  constructor() {
    effect(() => {
      this.elementRef.nativeElement.style.transform = this.appTransform();
    });
  }
}

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
