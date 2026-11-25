import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PlaylistService } from './playlist.service';

describe('PlaylistService', () => {
  let service: PlaylistService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PlaylistService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    vi.restoreAllMocks();
  });

  it('lists playlists and loads relative cover image blobs', () => {
    const createObjectUrlSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-cover');

    service.getPlaylists().subscribe();
    const listReq = httpMock.expectOne('/api/playlists');
    expect(listReq.request.method).toBe('GET');
    listReq.flush([
      {
        playlist_id: 10,
        user_id: 1,
        name: 'Roadtrip',
        is_exported: false,
        total_duration_seconds: 180,
        cover_image_url: '/api/playlists/10/image',
        tracks: [],
      },
    ]);

    expect(service.playlists()).toHaveLength(1);
    const imgReq = httpMock.expectOne('/api/playlists/10/image');
    expect(imgReq.request.method).toBe('GET');
    imgReq.flush(new Blob(['img'], { type: 'image/png' }));

    expect(createObjectUrlSpy).toHaveBeenCalled();
    expect(service.getCoverBlobUrl(10)).toBe('blob:mock-cover');

    service.setCoverBlobUrl(10, 'blob:updated');
    expect(service.getCoverBlobUrl(10)).toBe('blob:updated');
  });

  it('loads a single playlist by ID and creates a contextual deck playlist', () => {
    service.getPlaylistById(5).subscribe((pl) => {
      expect(pl.playlistId).toBe(5);
    });
    const getReq = httpMock.expectOne('/api/playlists/5');
    expect(getReq.request.method).toBe('GET');
    getReq.flush({
      playlist_id: 5,
      user_id: 1,
      name: 'Focus',
      is_exported: false,
      total_duration_seconds: 0,
      tracks: [],
    });

    service
      .createDeckPlaylist({
        name: 'Chill Mix',
        duration_minutes: 30,
        genre: 'Lo-Fi',
        reference_playlist_id: 5,
      })
      .subscribe();
    const postReq = httpMock.expectOne('/api/playlists/deck');
    expect(postReq.request.method).toBe('POST');
    expect(postReq.request.body).toEqual({
      name: 'Chill Mix',
      duration_minutes: 30,
      genre: 'Lo-Fi',
      source_playlist_id: 5,
    });
    postReq.flush({
      playlist_id: 11,
      user_id: 1,
      name: 'Chill Mix',
      is_exported: false,
      total_duration_seconds: 0,
      tracks: [],
    });

    expect(service.playlists()[0]?.playlistId).toBe(11);
  });

  it('uploads playlist image, fetches deck, adds/removes tracks, deletes, and exports to Spotify', () => {
    const file = new File(['abc'], 'cover.png', { type: 'image/png' });
    service.uploadPlaylistImage(11, file).subscribe();
    const uploadReq = httpMock.expectOne('/api/playlists/11/image');
    expect(uploadReq.request.method).toBe('PUT');
    expect(uploadReq.request.headers.get('Content-Type')).toBe('image/png');
    uploadReq.flush({
      playlist_id: 11,
      user_id: 1,
      name: 'Chill Mix',
      is_exported: false,
      total_duration_seconds: 0,
      tracks: [],
    });

    service.getPlaylistDeck(11, 15, 99).subscribe();
    const deckReq = httpMock.expectOne('/api/playlists/11/deck?limit=15&cursor_id=99');
    expect(deckReq.request.method).toBe('GET');
    deckReq.flush({ items: [], next_cursor: null, has_more: false });

    service.addTrackToPlaylist(11, 42, 'superlike').subscribe((ok) => {
      expect(ok).toBe(true);
    });
    const addReq = httpMock.expectOne('/api/playlists/11/swipe-add');
    expect(addReq.request.method).toBe('POST');
    expect(addReq.request.body).toEqual({ track_id: 42, action: 'superlike' });
    addReq.flush({ success: true, message: 'ok' });

    service.removeTrackFromPlaylist(11, 42).subscribe((ok) => {
      expect(ok).toBe(true);
    });
    const rmReq = httpMock.expectOne('/api/playlists/11/tracks/42');
    expect(rmReq.request.method).toBe('DELETE');
    rmReq.flush({ success: true, message: 'removed' });

    let exportResult: { success: boolean; spotifyUrl: string } | undefined;
    service.exportToSpotify(11, 'Chill Mix').subscribe((res) => {
      exportResult = res;
    });
    const expReq = httpMock.expectOne('/api/playlists/11/export-spotify');
    expect(expReq.request.method).toBe('POST');
    expReq.flush({
      playlist_id: 11,
      user_id: 1,
      name: 'Chill Mix',
      is_exported: true,
      spotify_playlist_id: 'sp-123',
      total_duration_seconds: 0,
      tracks: [],
    });
    expect(exportResult?.success).toBe(true);
    expect(exportResult?.spotifyUrl).toBe('https://open.spotify.com/playlist/sp-123');

    service.deletePlaylist(11).subscribe((ok) => {
      expect(ok).toBe(true);
    });
    const delReq = httpMock.expectOne('/api/playlists/11');
    expect(delReq.request.method).toBe('DELETE');
    delReq.flush({ success: true, message: 'deleted' });
    expect(service.playlists().some((p) => p.playlistId === 11)).toBe(false);
  });
});
