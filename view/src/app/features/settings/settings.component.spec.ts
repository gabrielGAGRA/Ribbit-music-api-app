import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { SettingsComponent } from './settings.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('SettingsComponent', () => {
  let component: SettingsComponent;
  let state: RibbitStateService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    httpMock = TestBed.inject(HttpTestingController);
    state.setUserName('João Lucas');
    component = TestBed.runInInjectionContext(() => new SettingsComponent());
  });

  it('should compute user initials accurately', () => {
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

  it('should toggle spotify linking via POST /api/profile/link-spotify', () => {
    writeAuthToken('jwt-token');
    state.userId.set(9);
    expect(component.isSpotifyLinked()).toBe(false);

    component.toggleSpotify();
    const linkReq = httpMock.expectOne('/api/profile/link-spotify');
    expect(linkReq.request.method).toBe('POST');
    expect(linkReq.request.body).toEqual({ spotify_id: 'spotify_user_9' });
    linkReq.flush({
      user_id: 9,
      email: 'joao@ribbit.app',
      display_name: 'João Lucas',
      spotify_id: 'spotify_user_9',
      plan_id: 1,
      blocked_genres: [],
    });
    expect(component.isSpotifyLinked()).toBe(true);
  });

  it('should remove blocked genre', () => {
    state.blockedGenres.set(['Metal', 'Sertanejo']);
    expect(state.blockedGenres()).toContain('Metal');

    component.removeBlockedGenre('Metal');
    expect(state.blockedGenres()).not.toContain('Metal');
    expect(state.blockedGenres()).toContain('Sertanejo');
  });

  it('should cancel subscription and downgrade to Free', () => {
    state.setPlan('Individual');
    expect(state.currentPlan()).toBe('Individual');

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
    expect(componentStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.settings-input\s*\{[^}]*min-width:\s*0/,
    );
    expect(componentStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.plan-status-box\s*\{[^}]*flex-direction:\s*column/,
    );
  });
});
