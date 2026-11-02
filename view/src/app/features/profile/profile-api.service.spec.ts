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
});
