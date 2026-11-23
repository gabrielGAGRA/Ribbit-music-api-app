import { Directive, ElementRef, effect, inject, input } from '@angular/core';

/** Sets dynamic percentage width on progress fill bars without inline template style bindings. */
@Directive({
  selector: '[appWidthPercent]',
  standalone: true,
})
export class WidthPercentDirective {
  private readonly elementRef = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly appWidthPercent = input<number>(0);

  constructor() {
    effect(() => {
      const clamped = Math.max(0, Math.min(100, this.appWidthPercent()));
      this.elementRef.nativeElement.style.width = `${clamped}%`;
    });
  }
}
