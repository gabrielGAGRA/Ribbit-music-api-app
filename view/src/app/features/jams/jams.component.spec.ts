import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect, beforeEach } from 'vitest';
import { JamsComponent } from './jams.component';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('JamsComponent', () => {
  let component: JamsComponent;
  let state: RibbitStateService;

  beforeEach(() => {
    localStorage.clear();
    state = new RibbitStateService();
    component = new JamsComponent(state);
  });

  it('should join jam room when submitting code and switch to swipe view', () => {
    expect(state.jamState().active).toBe(false);
    component.joinJam('RIBBIT-123');
    expect(state.jamState().active).toBe(true);
    expect(component.jamView()).toBe('swipe');
  });

  it('should vote to skip current track', () => {
    state.setJamActive(true);
    expect(state.jamVotes()).toBe(0);
    component.voteSkip();
    expect(state.jamVotes()).toBe(1);
  });

  it('should allow copying room code', () => {
    component.copyCode();
    expect(state.toast()).toContain('copiado');
  });

  it('should handle jam swipe actions and superlikes quota', () => {
    state.setJamActive(true);
    const initialCursor = component.jamDeckCursor();
    component.decideJamCard('like');
    expect(component.jamDeckCursor()).toBe(initialCursor + 1);

    component.decideJamCard('superlike');
    expect(component.jamSuperlikesCount()).toBe(1);
  });

  it('should allow vertical scroll on jam swipe card and stack join form on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');
    const componentStyles = readFileSync(resolve(__dirname, './jams.component.css'), 'utf8');

    expect(componentStyles).toMatch(/\.jam-swipe-card\s*\{[^}]*touch-action:\s*pan-y/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.join-panel form\s*\{[^}]*flex-direction:\s*column/);
  });
});
