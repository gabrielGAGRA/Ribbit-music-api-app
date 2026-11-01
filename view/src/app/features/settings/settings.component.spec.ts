import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect, beforeEach } from 'vitest';
import { SettingsComponent } from './settings.component';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('SettingsComponent', () => {
  let component: SettingsComponent;
  let state: RibbitStateService;

  beforeEach(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.clear();
    }
    state = new RibbitStateService();
    component = new SettingsComponent(state);
  });

  it('should compute user initials accurately', () => {
    state.setUserName('João Lucas');
    expect(component.userInitials()).toBe('JL');

    state.setUserName('Lucas');
    expect(component.userInitials()).toBe('LU');
  });

  it('should allow editing and saving display name', () => {
    component.startEditingName();
    expect(component.isEditingName()).toBe(true);

    component.nameDraft.set('João Silva');
    component.saveName();

    expect(state.userName()).toBe('João Silva');
    expect(component.isEditingName()).toBe(false);
  });

  it('should allow canceling name edit', () => {
    component.startEditingName();
    component.nameDraft.set('Outro Nome');
    component.cancelEditingName();

    expect(state.userName()).toBe('João Lucas');
    expect(component.isEditingName()).toBe(false);
  });

  it('should toggle spotify linking', () => {
    expect(component.isSpotifyLinked()).toBe(true);
    component.toggleSpotify();
    expect(component.isSpotifyLinked()).toBe(false);
    component.toggleSpotify();
    expect(component.isSpotifyLinked()).toBe(true);
  });

  it('should remove blocked genre', () => {
    state.setBlockedGenres(['Metal', 'Sertanejo']);
    expect(state.blockedGenres()).toContain('Metal');

    component.removeBlockedGenre('Metal');
    expect(state.blockedGenres()).not.toContain('Metal');
    expect(state.blockedGenres()).toContain('Sertanejo');
  });

  it('should cancel subscription and downgrade to Free', () => {
    state.setPlan('Plus');
    expect(state.currentPlan()).toBe('Plus');

    component.cancelSubscription();
    expect(state.currentPlan()).toBe('Free');
  });

  it('should trigger delete modal and logout', () => {
    component.openDeleteModal();
    expect(state.activeModal()).toBe('delete');

    component.logout();
    expect(state.authView()).toBe('login');
  });

  it('should make settings inputs fluid and stack plan status box on mobile', () => {
    const componentStyles = readFileSync(resolve(__dirname, './settings.component.css'), 'utf8');

    expect(componentStyles).toMatch(/\.settings-input\s*\{[^}]*font-size:\s*1rem/);
    expect(componentStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.settings-input\s*\{[^}]*min-width:\s*0/);
    expect(componentStyles).toMatch(/@media\s*\(max-width:\s*768px\)[\s\S]*\.plan-status-box\s*\{[^}]*flex-direction:\s*column/);
  });
});
