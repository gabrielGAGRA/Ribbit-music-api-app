import { describe, expect, it } from 'vitest';
import { readInputChecked, readInputValue, readSelectValue } from './dom-event-values';

describe('dom-event-values', () => {
  it('extracts input value, checked state, and select value safely', () => {
    const input = document.createElement('input');
    input.value = 'hello';
    input.type = 'checkbox';
    input.checked = true;
    expect(readInputValue({ target: input } as unknown as Event)).toBe('hello');
    expect(readInputChecked({ target: input } as unknown as Event)).toBe(true);

    const select = document.createElement('select');
    const opt = document.createElement('option');
    opt.value = 'opt-1';
    select.appendChild(opt);
    select.value = 'opt-1';
    expect(readSelectValue({ target: select } as unknown as Event)).toBe('opt-1');
  });
});
