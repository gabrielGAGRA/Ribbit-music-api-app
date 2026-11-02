import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type {
  ActionSuccessApiDto,
  InteractionApiDto,
  SwipeApiAction,
  UserApiDto,
  UserProfileApiDto,
} from '@ribbit/shared-types';

/** Communicates with /api/profile endpoints for user profile, history, and preferences. */
@Injectable({ providedIn: 'root' })
export class ProfileApiService {
  private readonly http = inject(HttpClient);

  /** Fetches the authenticated user's profile, active plan, and recent interactions. */
  getProfile(): Observable<UserProfileApiDto> {
    return this.http.get<UserProfileApiDto>('/api/profile/me');
  }

  /** Updates display name or password credentials for the authenticated user. */
  updateProfile(options: {
    readonly displayName?: string;
    readonly newPassword?: string;
    readonly currentPassword?: string;
  }): Observable<UserApiDto> {
    return this.http.put<UserApiDto>('/api/profile/me', {
      display_name: options.displayName,
      new_password: options.newPassword,
      current_password: options.currentPassword,
    });
  }

  /** Links or unlinks a Spotify identifier on the user's profile. */
  linkSpotify(userId: number, spotifyId: string): Observable<UserApiDto> {
    return this.http.post<UserApiDto>('/api/profile/link-spotify', {
      user_id: userId,
      spotify_id: spotifyId,
    });
  }

  /** Deletes the authenticated user's account and associated data. */
  deleteAccount(): Observable<ActionSuccessApiDto> {
    return this.http.delete<ActionSuccessApiDto>('/api/profile/account');
  }

  /** Lists user swipe interactions, optionally filtered by category. */
  listHistory(category?: SwipeApiAction): Observable<readonly InteractionApiDto[]> {
    const params = category ? new HttpParams().set('category', category) : new HttpParams();
    return this.http.get<readonly InteractionApiDto[]>('/api/profile/history', { params });
  }

  /** Revises an existing track swipe interaction (requires paid plan). */
  changeInteraction(options: {
    readonly userId: number;
    readonly trackId: number;
    readonly newAction: SwipeApiAction;
  }): Observable<InteractionApiDto> {
    return this.http.put<InteractionApiDto>('/api/profile/interaction', {
      user_id: options.userId,
      track_id: options.trackId,
      new_action: options.newAction,
    });
  }

  /** Lists genres blocked by the authenticated user. */
  listBlockedGenres(): Observable<readonly string[]> {
    return this.http.get<readonly string[]>('/api/profile/blocked-genres');
  }

  /** Updates genres blocked from discovery and playlists (requires paid plan). */
  updateBlockedGenres(blockedGenres: readonly string[]): Observable<UserApiDto> {
    return this.http.put<UserApiDto>('/api/profile/blocked-genres', {
      blocked_genres: [...blockedGenres],
    });
  }
}
