import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect, beforeEach } from 'vitest';
import { ProfileComponent } from './profile.component';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { AudioPlayerService } from '../../core/audio-player.service';

describe('ProfileComponent', () => {
  let component: ProfileComponent;
  let state: RibbitStateService;
  let player: AudioPlayerService;

  beforeEach(() => {
    localStorage.clear();
    state = new RibbitStateService();
    player = new AudioPlayerService();
    component = new ProfileComponent(state, player);
  });

  it('should switch between like, love, and reject tabs', () => {
    expect(component.selectedTab()).toBe('like');
    component.selectTab('love');
    expect(component.selectedTab()).toBe('love');
  });

  it('should calculate counts for collections', () => {
    expect(component.likeCount()).toBeGreaterThan(0);
    expect(component.loveCount()).toBeGreaterThan(0);
    expect(component.rejectCount()).toBeGreaterThan(0);
  });

  it('should cancel subscription to free plan', () => {
    state.setPlan('Individual');
    expect(state.currentPlan()).toBe('Individual');

    component.cancelSubscription();
    expect(state.currentPlan()).toBe('Free');
    expect(state.toast()).toContain('cancelada');
  });

  it('should set page to settings on goToSettings', () => {
    component.goToSettings();
    expect(state.activePage()).toBe('settings');
  });

  it('should stack profile account management, collections toolbar, and dashboard columns on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');

    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.account-management\s*\{[^}]*flex-direction:\s*column/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.collection-toolbar\s*\{[^}]*flex-direction:\s*column/);
    expect(globalStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.dashboard-columns\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
  });
});
