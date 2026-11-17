import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { AppComponent } from './app.component';
import { AudioPlayerService } from './core/audio-player.service';
import { authInterceptor } from './core/auth.interceptor';
import { RibbitStateService } from './core/ribbit-state.service';

describe('AppComponent', () => {
  let component: AppComponent;
  let state: RibbitStateService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    component = TestBed.runInInjectionContext(() => new AppComponent());
  });

  it('should initialize with discover page and require login when unauthenticated', () => {
    expect(state.activePage()).toBe('discover');
    expect(state.authView()).toBe('login');
  });

  it('should navigate to different pages including profile and settings', () => {
    component.changePage('playlists');
    expect(state.activePage()).toBe('playlists');

    component.changePage('profile');
    expect(state.activePage()).toBe('profile');
    expect(component.breadcrumbLabel()).toBe('Meu perfil');
    expect(component.isNavItemActive('profile')).toBe(true);

    component.changePage('settings');
    expect(state.activePage()).toBe('settings');
    expect(component.breadcrumbLabel()).toBe('Configurações');
  });

  it('should use The Pond for Jams and Comunidade for Explore while keeping Descoberta distinct', () => {
    component.changePage('discover');
    expect(component.breadcrumbLabel()).toBe('Descoberta');
    expect(component.currentHeading().eyebrow).not.toBe('THE POND');

    component.changePage('jams');
    expect(component.breadcrumbLabel()).toBe('Jams');
    expect(component.currentHeading().eyebrow).toBe('THE POND');

    component.changePage('explore');
    expect(component.breadcrumbLabel()).toBe('Comunidade');
    expect(component.currentHeading().eyebrow).toBe('COMUNIDADE');
  });

  it('should signal playlists view reset when clicking playlists in the sidebar', () => {
    const before = state.playlistsViewReset();
    component.changePage('playlists');
    expect(state.playlistsViewReset()).toBe(before + 1);
  });

  it('should compute user initials and real library counts accurately', () => {
    state.setUserName('João Lucas');
    expect(component.userInitials()).toBe('JL');
    expect(component.likedCount()).toBe(0);
    expect(component.lovedCount()).toBe(0);
    expect(component.rejectedCount()).toBe(0);

    state.decide('love');
    expect(component.likedCount()).toBe(1);
    expect(component.lovedCount()).toBe(1);
  });

  it('should compute recent discoveries based on liked songs', () => {
    expect(component.recentDiscoveries().length).toBeGreaterThan(0);
    state.decide('like');
    expect(component.recentDiscoveries().length).toBeGreaterThan(0);
  });

  it('should reflect jam active and roomId state for sidebar promotion', () => {
    expect(state.jamState().roomId).toBeUndefined();
    expect(state.jamState().active).toBe(false);

    state.jamState.set({
      jamId: 77,
      roomId: 77,
      active: true,
      code: 'JAM-77',
      roomName: 'Minha Sala',
      votes: 0,
      voteThreshold: 3,
      durationHours: 1,
      durationMinutes: 0,
    });

    expect(state.jamState().roomId).toBe(77);
    expect(state.jamState().active).toBe(true);
  });

  it('should map /callback and /settings query URLs to the settings active page', () => {
    expect(component.resolveActivePageFromUrl('/callback?code=abc&state=xyz')).toBe('settings');
    expect(component.resolveActivePageFromUrl('/settings?code=abc&state=xyz')).toBe('settings');
    expect(component.resolveActivePageFromUrl('/playlists#section')).toBe('playlists');
    expect(component.resolveActivePageFromUrl('/')).toBe('discover');
  });

  it('should pause playing audio when transitioning between screens', () => {
    const player = TestBed.inject(AudioPlayerService);
    player.play();
    expect(player.isPlaying()).toBe(true);

    component.changePage('explore');
    TestBed.flushEffects();

    expect(player.isPlaying()).toBe(false);
  });
});
