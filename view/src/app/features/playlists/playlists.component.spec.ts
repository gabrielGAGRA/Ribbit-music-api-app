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

  it('should trigger modal to create playlist', () => {
    component.openCreateModal();
    expect(state.activeModal()).toBe('playlist');
  });

  it('should toggle swipe mode and handle deck candidates', () => {
    expect(component.isSwipeMode()).toBe(false);
    component.toggleSwipeMode();
    expect(component.isSwipeMode()).toBe(true);
    expect(component.deckCandidates().length).toBeGreaterThan(0);
  });

  it('should play playlist and individual tracks', () => {
    component.openPlaylistView({
      id: '1',
      name: 'Chill',
      count: 1,
      duration: '3 min',
      songs: [
        {
          ...state.songs()[0]!,
          title: 'Song 1',
        },
      ],
    });
    component.playPlaylist();
    expect(state.toast()).toContain('Reproduzindo "Song 1"');
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
    expect(state.spotifyPromptReason()).toBe(
      'Conecte sua conta do Spotify para exportar playlists.',
    );
  });

  it('should allow vertical page scroll on playlist swipe card and stack playlist grid on mobile', () => {
    const globalStyles = readFileSync(resolve(__dirname, '../../../styles.css'), 'utf8');
    const componentStyles = readFileSync(resolve(__dirname, './playlists.component.css'), 'utf8');

    expect(componentStyles).toMatch(/\.playlist-swipe-card\s*\{[^}]*touch-action:\s*pan-y/);
    expect(componentStyles).toMatch(
      /\.playlists-grid[\s\S]*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(globalStyles).toMatch(
      /@media\s*\(max-width:\s*480px\)[\s\S]*\.playlist-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
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

  it('should respect empty tracks when backend deck returns empty list', () => {
    writeAuthToken('jwt-token');
    component.selectedPlaylist.set({
      id: '20',
      playlistId: 20,
      name: 'Vazia',
      count: 0,
      duration: '0 min',
      songs: [],
    });

    component.loadPlaylistDeck();
    const req = httpMock.expectOne('/api/playlists/20/deck?limit=25');
    req.flush({ items: [], next_cursor: null, has_more: false });

    expect(component.deckCandidates().length).toBe(0);
    expect(component.activeTrack()).toBeNull();
  });

  it('should upload playlist cover image on file select', () => {
    writeAuthToken('jwt-token');
    component.selectedPlaylist.set({
      id: '20',
      playlistId: 20,
      name: 'Vazia',
      count: 0,
      duration: '0 min',
      songs: [],
    });

    const file = new File(['image-bytes'], 'cover.jpg', { type: 'image/jpeg' });
    const dummyEvent = {
      target: {
        files: [file],
      },
    } as unknown as Event;

    component.onCoverFileSelected(dummyEvent);
    expect(component.isUploadingCover()).toBe(true);

    const uploadReq = httpMock.expectOne('/api/playlists/20/image');
    expect(uploadReq.request.method).toBe('PUT');
    uploadReq.flush({
      playlist_id: 20,
      user_id: 1,
      name: 'Vazia',
      description: null,
      max_duration_seconds: null,
      is_exported: false,
      spotify_playlist_id: null,
      total_duration_seconds: 0,
      cover_image_url: '/api/playlists/20/image',
      tracks: [],
    });

    expect(component.isUploadingCover()).toBe(false);
    expect(component.selectedPlaylist()?.coverImageUrl).toBe('/api/playlists/20/image');
    expect(state.toast()).toContain('Capa da playlist atualizada');
  });

  it('should add track to playlist via swipe-add and advance deck cursor in swipe mode', () => {
    writeAuthToken('jwt-token');
    component.selectedPlaylist.set({
      id: '25',
      playlistId: 25,
      name: 'Vibes',
      count: 0,
      duration: '0 min',
      coverImageUrl: '/api/playlists/25/image',
      songs: [],
    });
    component.deckCandidates.set([
      {
        trackId: 101,
        title: 'Song A',
        artist: 'Artist A',
        genre: 'Indie',
        time: '3:30',
        image: 'img-a',
        album: 'Album A',
        year: '2023',
        match: 95,
      },
      {
        trackId: 102,
        title: 'Song B',
        artist: 'Artist B',
        genre: 'Rock',
        time: '4:00',
        image: 'img-b',
        album: 'Album B',
        year: '2022',
        match: 90,
      },
    ]);
    component.deckCursor.set(0);

    expect(component.currentDeckTrack()?.title).toBe('Song A');
    expect(component.selectedPlaylist()?.coverImageUrl).toBe('/api/playlists/25/image');

    // Swipe right (like)
    component.swipeDeckTrack('like');

    const addReq = httpMock.expectOne('/api/playlists/25/swipe-add');
    expect(addReq.request.method).toBe('POST');
    expect(addReq.request.body).toEqual({ track_id: 101, action: 'like' });
    addReq.flush({ success: true, message: 'Track added' });

    httpMock.expectOne('/api/playlists').flush([]);

    expect(component.deckCursor()).toBe(1);
    expect(component.currentDeckTrack()?.title).toBe('Song B');
    expect(component.selectedPlaylist()?.count).toBe(1);
    expect(component.selectedPlaylist()?.songs?.[0]?.trackId).toBe(101);
  });

  it('should advance deck cursor on swipe dislike without adding track to playlist', () => {
    writeAuthToken('jwt-token');
    component.selectedPlaylist.set({
      id: '25',
      playlistId: 25,
      name: 'Vibes',
      count: 0,
      duration: '0 min',
      songs: [],
    });
    component.deckCandidates.set([
      {
        trackId: 101,
        title: 'Song A',
        artist: 'Artist A',
        genre: 'Indie',
        time: '3:30',
        image: 'img-a',
        album: 'Album A',
        year: '2023',
        match: 95,
      },
    ]);
    component.deckCursor.set(0);

    component.swipeDeckTrack('dislike');

    httpMock.expectNone('/api/playlists/25/swipe-add');
    expect(component.deckCursor()).toBe(1);
    expect(component.currentDeckTrack()).toBeNull();
  });

  it('should export playlist to Spotify using exportPlaylist method', () => {
    writeAuthToken('jwt-token');
    state.spotifyId.set('spotify_user_test');
    component.exportPlaylist(50, 'Minha Playlist Especial');
    expect(component.isExportingSpotify()).toBe(true);

    const exportReq = httpMock.expectOne('/api/playlists/50/export-spotify');
    expect(exportReq.request.method).toBe('POST');
    exportReq.flush({
      playlist_id: 50,
      user_id: 1,
      name: 'Minha Playlist Especial',
      description: null,
      max_duration_seconds: null,
      is_exported: true,
      spotify_playlist_id: 'sp_50',
      total_duration_seconds: 0,
      tracks: [],
    });

    expect(component.isExportingSpotify()).toBe(false);
    expect(state.toast()).toContain('exportada com sucesso');
  });

  it('should reset selected playlist back to all playlists when state.resetPlaylistsView is triggered', () => {
    component.openPlaylistView('Dias de sol');
    expect(component.selectedPlaylist()?.name).toBe('Dias de sol');

    state.resetPlaylistsView();
    TestBed.flushEffects();

    expect(component.selectedPlaylist()).toBeNull();
    expect(component.isSwipeMode()).toBe(false);
  });

  it('should render Discover-style swipe card without green action buttons below library playlist cards', () => {
    const template = readFileSync(resolve(__dirname, './playlists.component.html'), 'utf8');

    expect(template).toContain('class="discovery-stage"');
    expect(template).toContain('class="discovery-card playlist-swipe-card"');
    expect(template).toContain('class="swipe-controls"');
    expect(template).not.toContain('playlist-card-actions');
    expect(template).not.toContain('quick-spotify-btn');
  });
});
