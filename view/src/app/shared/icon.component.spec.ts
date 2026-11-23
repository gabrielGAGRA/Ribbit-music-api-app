import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { IconComponent } from './icon.component';

describe('IconComponent', () => {
  it('initializes with default size 20 and empty className', () => {
    const component = TestBed.runInInjectionContext(() => new IconComponent());
    expect(component.size()).toBe(20);
    expect(component.className()).toBe('');
  });
});
