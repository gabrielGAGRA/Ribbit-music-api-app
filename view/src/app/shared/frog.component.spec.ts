import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { FrogComponent } from './frog.component';

describe('FrogComponent', () => {
  it('computes default svgClass and isMouthOpen', () => {
    const component = TestBed.runInInjectionContext(() => new FrogComponent());
    expect(component['svgClass']()).toBe('frog mood-idle');
    expect(component['isMouthOpen']()).toBe(false);
  });
});
