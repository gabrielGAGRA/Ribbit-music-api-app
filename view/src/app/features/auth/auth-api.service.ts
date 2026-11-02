import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';
import type {
  AuthApiResponse,
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

  /** Registers a new user account and returns its session token. */
  register(payload: RegisterUserApiRequest): Observable<AuthApiResponse> {
    return this.http.post<AuthApiResponse>('/api/auth/register', payload);
  }
}
