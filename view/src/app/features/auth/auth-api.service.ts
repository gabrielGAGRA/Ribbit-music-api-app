import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type {
  AuthApiResponse,
  GoogleAuthorizeUrlApiResponse,
  GoogleClientIdApiResponse,
  GoogleLoginApiRequest,
  LoginApiRequest,
  RegisterUserApiRequest,
} from '@ribbit/shared-types';

/** Executes authentication and registration HTTP calls against /api/auth. */
@Injectable({ providedIn: 'root' })
export class AuthApiService {
  private readonly http = inject(HttpClient);

  /** Authenticates an existing user with email and password. */
  login(payload: LoginApiRequest): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/api/auth/login', payload);
  }

  /** Fetches the public Google OAuth client ID configured on the backend. */
  getGoogleClientId(): Observable<GoogleClientIdApiResponse> {
    return this.http.get<GoogleClientIdApiResponse>('/api/auth/google/client-id');
  }

  /** Requests the Google OAuth 2.0 authorization redirect URL. */
  getGoogleAuthorizeUrl(): Observable<GoogleAuthorizeUrlApiResponse> {
    return this.http.get<GoogleAuthorizeUrlApiResponse>('/api/auth/google/authorize');
  }

  /** Exchanges the backend Google OAuth handoff cookie for an active user session. */
  completeGoogleOAuthSession(): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/api/auth/google/session', {});
  }

  /** Authenticates or auto-provisions a user via Google Identity Provider ID token. */
  loginWithGoogle(payload: GoogleLoginApiRequest): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/api/auth/google', payload);
  }

  /** Registers a new user account and returns its session token. */
  register(payload: RegisterUserApiRequest): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/api/auth/register', payload);
  }
}
