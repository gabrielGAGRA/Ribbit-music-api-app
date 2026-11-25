import { describe, expect, it } from 'vitest';
import {
  readFirstSelectedFile,
  readInputChecked,
  readInputValue,
  readSelectValue,
} from './dom-event-values';

describe('dom-event-values', () => {
  it('extracts input value, checked state, file, and select value safely', () => {
    const input = document.createElement('input');
    input.value = 'hello';
    input.type = 'checkbox';
    input.checked = true;
    expect(readInputValue({ target: input } as unknown as Event)).toBe('hello');
    expect(readInputValue({ target: null } as unknown as Event)).toBe('');
    expect(readInputChecked({ target: input } as unknown as Event)).toBe(true);
    expect(readFirstSelectedFile({ target: null } as unknown as Event)).toBeNull();
    expect(readFirstSelectedFile({ target: { files: [] } } as unknown as Event)).toBeNull();

    const select = document.createElement('select');
    const opt = document.createElement('option');
    opt.value = 'opt-1';
    select.appendChild(opt);
    select.value = 'opt-1';
    expect(readSelectValue({ target: select } as unknown as Event)).toBe('opt-1');
  });
});
