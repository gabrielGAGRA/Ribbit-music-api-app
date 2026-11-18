import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type {
  ActionSuccessApiDto,
  AddFamilyMemberApiRequest,
  InteractionApiDto,
  SpotifyAuthorizeUrlApiResponse,
  SpotifyConnectCallbackApiRequest,
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

  /** Links a Spotify identifier on the user's profile. */
  linkSpotify(spotifyId: string): Observable<UserApiDto> {
    return this.http.post<UserApiDto>('/api/profile/link-spotify', {
      spotify_id: spotifyId,
    });
  }

  /** Unlinks the user's Spotify account and clears OAuth tokens. */
  unlinkSpotify(): Observable<UserApiDto> {
    return this.http.delete<UserApiDto>('/api/spotify/connection');
  }

  /** Fetches the signed Spotify OAuth 2.0 authorization URL from GET /api/spotify/authorize. */
  getSpotifyAuthorizeUrl(): Observable<SpotifyAuthorizeUrlApiResponse> {
    return this.http.get<SpotifyAuthorizeUrlApiResponse>('/api/spotify/authorize');
  }

  /** Exchanges the Spotify OAuth authorization code and state token via POST /api/spotify/callback. */
  connectSpotifyCallback(payload: SpotifyConnectCallbackApiRequest): Observable<UserApiDto> {
    return this.http.post<UserApiDto>('/api/spotify/callback', payload);
  }

  /** Deletes the authenticated user's account and associated data. */
  deleteAccount(): Observable<ActionSuccessApiDto> {
    return this.http.delete<ActionSuccessApiDto>('/api/profile/account');
  }

  /** Lists user swipe interactions, optionally filtered by category. */
  listHistory(category?: SwipeApiAction): Observable<readonly InteractionApiDto[]> {
    const params = category ? new HttpParams().set('category', category) : new HttpParams();
    return this.http.get<readonly InteractionApiDto[]>('/api/profile/interactions', { params });
  }

  /** Revises an existing track swipe interaction (requires paid plan). */
  changeInteraction(options: {
    readonly trackId: number;
    readonly newAction: SwipeApiAction;
  }): Observable<InteractionApiDto> {
    return this.http.put<InteractionApiDto>('/api/profile/interaction', {
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

  /** Gets preferred theme ('light' | 'dark') for user profile. */
  getTheme(): Observable<string> {
    return this.http.get<string>('/api/profile/theme');
  }

  /** Updates preferred theme ('light' | 'dark') for user profile. */
  updateTheme(theme: 'light' | 'dark'): Observable<UserApiDto> {
    return this.http.put<UserApiDto>('/api/profile/theme', {
      preferred_theme: theme,
    });
  }

  /** Gets favorite genres for user profile. */
  getFavoriteGenres(): Observable<readonly string[]> {
    return this.http.get<readonly string[]>('/api/profile/favorite-genres');
  }

  /** Updates favorite genres for user profile. */
  updateFavoriteGenres(favoriteGenres: readonly string[]): Observable<UserApiDto> {
    return this.http.put<UserApiDto>('/api/profile/favorite-genres', {
      favorite_genres: [...favoriteGenres],
    });
  }

  /** Lists dependent user profiles enrolled in the authenticated user's family plan. */
  listFamilyMembers(): Observable<UserApiDto[]> {
    return this.http.get<UserApiDto[]>('/api/profile/family/members');
  }

  /** Adds or registers a dependent user to the authenticated user's family plan. */
  addFamilyMember(payload: AddFamilyMemberApiRequest): Observable<UserApiDto> {
    return this.http.post<UserApiDto>('/api/profile/family/members', payload);
  }

  /** Removes a dependent user profile from the authenticated user's family plan. */
  removeFamilyMember(memberId: number): Observable<UserApiDto> {
    return this.http.delete<UserApiDto>(`/api/profile/family/members/${memberId}`);
  }

  /** Updates blocked genres for a dependent account in the family plan. */
  updateFamilyMemberBlockedGenres(
    memberId: number,
    blockedGenres: readonly string[],
  ): Observable<UserApiDto> {
    return this.http.put<UserApiDto>(`/api/profile/family/members/${memberId}/blocked-genres`, {
      blocked_genres: [...blockedGenres],
    });
  }
}
