import { ElementRef, provideZonelessChangeDetection, Renderer2 } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';
import { WaveBarStyleDirective } from './wave-bar-style.directive';

describe('WaveBarStyleDirective', () => {
  it('can be instantiated in an injection context', () => {
    const el = document.createElement('div');
    const renderer = { setStyle: vi.fn() } as unknown as Renderer2;
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        { provide: ElementRef, useValue: new ElementRef(el) },
        { provide: Renderer2, useValue: renderer },
      ],
    });
    const directive = TestBed.runInInjectionContext(() => new WaveBarStyleDirective());
    expect(directive).toBeTruthy();
  });
});
