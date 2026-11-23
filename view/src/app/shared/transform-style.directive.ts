import { Directive, ElementRef, effect, inject, input } from '@angular/core';

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
