import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ProfileApiService } from './profile-api.service';

describe('ProfileApiService', () => {
  let service: ProfileApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ProfileApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('loads interactions from the canonical profile endpoint', () => {
    service.listHistory('like').subscribe();

    const request = httpMock.expectOne('/api/profile/interactions?category=like');
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });

  it('links Spotify using the authenticated session instead of a body user ID', () => {
    service.linkSpotify('spotify-user').subscribe();

    const request = httpMock.expectOne('/api/profile/link-spotify');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ spotify_id: 'spotify-user' });
    request.flush({
      user_id: 7,
      email: 'user@ribbit.app',
      display_name: 'User',
      age: 26,
      plan_id: 1,
      is_admin: false,
    });
  });

  it('revises interactions without sending a user ID in the body', () => {
    service.changeInteraction({ trackId: 7, newAction: 'like' }).subscribe();

    const request = httpMock.expectOne('/api/profile/interaction');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ track_id: 7, new_action: 'like' });
    request.flush({
      interaction_id: 1,
      user_id: 7,
      track_id: 7,
      action: 'like',
    });
  });

  it('lists, adds, and removes family members via /api/profile/family/members', () => {
    service.listFamilyMembers().subscribe((members) => {
      expect(members.length).toBe(1);
      expect(members[0]?.email).toBe('dependent@ribbit.app');
    });

    const listReq = httpMock.expectOne('/api/profile/family/members');
    expect(listReq.request.method).toBe('GET');
    listReq.flush([
      {
        user_id: 20,
        email: 'dependent@ribbit.app',
        display_name: 'Dep',
        age: 18,
        plan_id: 3,
        is_admin: false,
      },
    ]);

    service
      .addFamilyMember({ email: 'newdep@ribbit.app', display_name: 'New Dep' })
      .subscribe((res) => {
        expect(res.user_id).toBe(21);
      });

    const addReq = httpMock.expectOne('/api/profile/family/members');
    expect(addReq.request.method).toBe('POST');
    expect(addReq.request.body).toEqual({
      email: 'newdep@ribbit.app',
      display_name: 'New Dep',
    });
    addReq.flush({
      user_id: 21,
      email: 'newdep@ribbit.app',
      display_name: 'New Dep',
      age: 20,
      plan_id: 3,
      is_admin: false,
    });

    service.removeFamilyMember(21).subscribe((res) => {
      expect(res.user_id).toBe(21);
    });

    const deleteReq = httpMock.expectOne('/api/profile/family/members/21');
    expect(deleteReq.request.method).toBe('DELETE');
    deleteReq.flush({
      user_id: 21,
      email: 'newdep@ribbit.app',
      display_name: 'New Dep',
      age: 20,
      plan_id: 3,
      is_admin: false,
    });

    service
      .updateFamilyMemberParentalControls(21, {
        blocked_genres: ['Metal'],
        blocked_artists: ['Eminem'],
      })
      .subscribe((res) => {
        expect(res.blocked_genres).toEqual(['metal']);
        expect(res.blocked_artists).toEqual(['eminem']);
      });

    const controlsReq = httpMock.expectOne('/api/profile/family/members/21/parental-controls');
    expect(controlsReq.request.method).toBe('PUT');
    expect(controlsReq.request.body).toEqual({
      blocked_genres: ['Metal'],
      blocked_artists: ['Eminem'],
    });
    controlsReq.flush({
      user_id: 21,
      email: 'newdep@ribbit.app',
      display_name: 'New Dep',
      age: 20,
      plan_id: 3,
      blocked_genres: ['metal'],
      blocked_artists: ['eminem'],
      is_admin: false,
    });
  });

  it('fetches Spotify authorize URL and exchanges OAuth callback code', () => {
    service.getSpotifyAuthorizeUrl().subscribe((res) => {
      expect(res.authorization_url).toContain('accounts.spotify.com/authorize');
    });

    const authReq = httpMock.expectOne('/api/spotify/authorize');
    expect(authReq.request.method).toBe('GET');
    authReq.flush({
      authorization_url: 'https://accounts.spotify.com/authorize?client_id=abc&state=xyz',
    });

    service
      .connectSpotifyCallback({ code: 'auth-code-123', state: 'signed-state' })
      .subscribe((u) => {
        expect(u.spotify_id).toBe('spotify_real_id');
        expect(u.spotify_premium).toBe(true);
      });

    const callbackReq = httpMock.expectOne('/api/spotify/callback');
    expect(callbackReq.request.method).toBe('POST');
    expect(callbackReq.request.body).toEqual({
      code: 'auth-code-123',
      state: 'signed-state',
    });
    callbackReq.flush({
      user_id: 7,
      email: 'user@ribbit.app',
      display_name: 'User',
      age: 26,
      plan_id: 1,
      spotify_id: 'spotify_real_id',
      spotify_premium: true,
      is_admin: false,
    });
  });
});
