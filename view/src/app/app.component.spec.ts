import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
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
  let player: AudioPlayerService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    state = TestBed.inject(RibbitStateService);
    player = TestBed.inject(AudioPlayerService);
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

  it('should toggle persistent player playback', () => {
    expect(player.isPlaying()).toBe(false);
    component.togglePlayback();
    expect(player.isPlaying()).toBe(true);
  });

  it('should expose mobile topbar brand and mini-player progress bar in shell template and styles', () => {
    const template = readFileSync(resolve(__dirname, './app.component.html'), 'utf8');
    const globalStyles = readFileSync(resolve(__dirname, '../styles.css'), 'utf8');

    expect(template).toContain('topbar-brand');
    expect(template).toContain('breadcrumb-prefix');
    expect(template).toContain('player-mobile-progress');

    expect(globalStyles).toContain('100dvh');
    expect(globalStyles).toMatch(/\.breadcrumb\s*>\s*span:last-child\s*\{[^}]*color:\s*#c5ccda/);
    const toastKeyframes = globalStyles.match(
      /@keyframes\s+toast-in\s*\{\s*from\s*\{[^}]*\}\s*to\s*\{[^}]*\}\s*\}/,
    )?.[0];
    expect(toastKeyframes).toBeDefined();
    expect(toastKeyframes).toContain('translate(-50%, 14px)');
    expect(toastKeyframes).not.toContain('bottom:');
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.topbar-brand\s*\{[^}]*align-self:\s*center/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.player\s*\{[\s\S]*left:\s*0/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*768px\)[\s\S]*\.player-volume\s*\{[\s\S]*display:\s*none/,
    );
  });
});
