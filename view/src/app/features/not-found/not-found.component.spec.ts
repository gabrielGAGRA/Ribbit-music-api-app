import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { NotFoundComponent } from './not-found.component';

describe('NotFoundComponent', () => {
  it('can be instantiated and has a 404 template', () => {
    const component = new NotFoundComponent();
    expect(component).toBeTruthy();
    const html = readFileSync(resolve(__dirname, './not-found.component.html'), 'utf8');
    expect(html).toContain('404');
  });
});
