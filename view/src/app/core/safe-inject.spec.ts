import { InjectionToken } from '@angular/core';
import { describe, expect, it } from 'vitest';
import { safeInject } from './safe-inject';

const TEST_TOKEN = new InjectionToken<string>('TEST_TOKEN');

describe('safeInject', () => {
  it('returns fallback when called outside an injection context', () => {
    expect(safeInject(TEST_TOKEN, 'fallback-value')).toBe('fallback-value');
  });
});
