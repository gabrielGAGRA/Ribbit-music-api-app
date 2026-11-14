import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { PlaylistsComponent } from './playlists.component';
import { authInterceptor } from '../../core/auth.interceptor';
import { writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';

describe('PlaylistsComponent', () => {
  let component: PlaylistsComponent;
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
    component = TestBed.runInInjectionContext(() => new PlaylistsComponent());
  });

  it('should switch between playlists and queue tabs', () => {
    expect(component.currentTab()).toBe('playlists');
    component.selectTab('queue');
    expect(component.currentTab()).toBe('queue');
  });

  it('should add song to queue when approving', () => {
    component.selectTab('queue');
    component.decideQueue(true);
    expect(state.queue().length).toBe(1);
  });

  it('should toggle queue swipe card preview playback', () => {
    component.selectTab('queue');
    component.toggleQueueCardPlay();
    expect(component.currentTab()).toBe('queue');
  });

  it('should trigger modal to create playlist or save queue', () => {
    component.openCreateModal();
    expect(state.activeModal()).toBe('playlist');

    component.openSaveQueueModal();
    expect(state.activeModal()).toBe('save-queue');
  });

  it('should open and close dedicated playlist view', () => {
    expect(component.selectedPlaylist()).toBeNull();
    component.openPlaylistView('Dias de sol');
    expect(component.selectedPlaylist()?.name).toBe('Dias de sol');

    component.closePlaylistView();
    expect(component.selectedPlaylist()).toBeNull();
  });

  it('should trigger spotify export via POST /api/playlists/{id}/export-spotify', () => {
    writeAuthToken('jwt-token');
    state.spotifyId.set('spotify_user_test');
    component.openPlaylistView({
      id: '10',
      playlistId: 10,
      name: 'Dias de sol',
      count: 1,
      duration: '4 min',
      songs: [],
    });
    const fetchReq = httpMock.expectOne('/api/playlists/10');
    fetchReq.flush({
      playlist_id: 10,
      user_id: 1,
      name: 'Dias de sol',
      description: null,
      max_duration_seconds: 1800,
      is_exported: false,
      spotify_playlist_id: null,
      total_duration_seconds: 0,
      tracks: [],
    });

    component.exportCurrentToSpotify();
    expect(component.isExportingSpotify()).toBe(true);

    const exportReq = httpMock.expectOne('/api/playlists/10/export-spotify');
    expect(exportReq.request.method).toBe('POST');
    exportReq.flush({
      playlist_id: 10,
      user_id: 1,
      name: 'Dias de sol',
      description: null,
      max_duration_seconds: 1800,
      is_exported: true,
      spotify_playlist_id: 'sp_10',
      total_duration_seconds: 0,
      tracks: [],
    });
    expect(component.isExportingSpotify()).toBe(false);
    expect(state.toast()).toContain('Spotify');
  });

  it('prompts spotify connection modal when unlinked user tries to export playlist', () => {
    writeAuthToken('jwt-token');
    state.spotifyId.set(null);
    component.openPlaylistView({
      id: '10',
      playlistId: 10,
      name: 'Dias de sol',
      count: 1,
      duration: '4 min',
      songs: [],
    });
    httpMock.expectOne('/api/playlists/10').flush({
      playlist_id: 10,
      user_id: 1,
      name: 'Dias de sol',
      description: null,
      max_duration_seconds: 1800,
      is_exported: false,
      spotify_playlist_id: null,
      total_duration_seconds: 0,
      tracks: [],
    });

    component.exportCurrentToSpotify();
    expect(component.isExportingSpotify()).toBe(false);
    expect(state.activeModal()).toBe('spotify-connect');
    expect(state.spotifyPromptReason()).toContain('Conecte sua conta do Spotify');
    httpMock.expectNone('/api/playlists/10/export-spotify');
  });

  it('allows non-premium spotify users to export playlist without error', () => {
    writeAuthToken('jwt-token');
    state.spotifyId.set('spotify_free_user');
    state.spotifyPremium.set(false);
    component.openPlaylistView({
      id: '10',
      playlistId: 10,
      name: 'Dias de sol',
      count: 1,
      duration: '4 min',
      songs: [],
    });
    httpMock.expectOne('/api/playlists/10').flush({
      playlist_id: 10,
      user_id: 1,
      name: 'Dias de sol',
      description: null,
      max_duration_seconds: 1800,
      is_exported: false,
      spotify_playlist_id: null,
      total_duration_seconds: 0,
      tracks: [],
    });

    component.exportCurrentToSpotify();
    const exportReq = httpMock.expectOne('/api/playlists/10/export-spotify');
    exportReq.flush({
      playlist_id: 10,
      user_id: 1,
      name: 'Dias de sol',
      description: null,
      max_duration_seconds: 1800,
      is_exported: true,
      spotify_playlist_id: 'sp_free_10',
      total_duration_seconds: 0,
      tracks: [],
    });
    expect(component.isExportingSpotify()).toBe(false);
    expect(state.toast()).toContain('Spotify');
  });

  it('prompts spotify connection modal when export API returns SpotifyConnectionRequiredError', () => {
    writeAuthToken('jwt-token');
    state.spotifyId.set('spotify_stale_user');
    component.openPlaylistView({
      id: '10',
      playlistId: 10,
      name: 'Dias de sol',
      count: 1,
      duration: '4 min',
      songs: [],
    });
    httpMock.expectOne('/api/playlists/10').flush({
      playlist_id: 10,
      user_id: 1,
      name: 'Dias de sol',
      description: null,
      max_duration_seconds: 1800,
      is_exported: false,
      spotify_playlist_id: null,
      total_duration_seconds: 0,
      tracks: [],
    });

    component.exportCurrentToSpotify();
    const exportReq = httpMock.expectOne('/api/playlists/10/export-spotify');
    exportReq.flush(
      {
        error: 'SpotifyConnectionRequiredError',
        message: 'Conecte sua conta do Spotify para exportar playlists.',
        details: { rule_name: 'spotify_connection_required' },
      },
      { status: 403, statusText: 'Forbidden' },
    );
    expect(component.isExportingSpotify()).toBe(false);
    expect(state.activeModal()).toBe('spotify-connect');
    expect(state.spotifyPromptReason()).toBe('Conecte sua conta do Spotify para exportar playlists.');
  });

  it('should toggle viewing all songs in the last queue', () => {
    expect(component.showLastQueueDetails()).toBe(false);
    component.toggleLastQueueDetails();
    expect(component.showLastQueueDetails()).toBe(true);
    component.toggleLastQueueDetails();
    expect(component.showLastQueueDetails()).toBe(false);
  });

  it('should allow vertical page scroll on queue swipe card and stack playlist grid on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');
    const componentStyles = readFileSync(resolve(__dirname, './playlists.component.css'), 'utf8');

    expect(globalStyles).toMatch(/\.queue-swipe-card\s*\{[^}]*touch-action:\s*pan-y/);
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*480px\)[\s\S]*\.playlist-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*480px\)[\s\S]*\.playlist-hub-tabs\s+button\s*\{/,
    );
    expect(componentStyles).toMatch(
      /@media\s*\(hover:\s*none\)[\s\S]*\.hero-play-badge\s*\{[^}]*opacity:\s*1/,
    );
    expect(componentStyles.lastIndexOf('.hero-play-badge')).toBeGreaterThan(
      componentStyles.indexOf('.hero-cover:hover .hero-play-badge'),
    );
    expect(componentStyles.indexOf('@media (max-width: 680px)')).toBeGreaterThan(
      componentStyles.indexOf('.song-duration {'),
    );
  });
});
