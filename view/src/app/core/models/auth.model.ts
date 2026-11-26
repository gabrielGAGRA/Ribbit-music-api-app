import type { InteractionApiDto } from './track.model';

export interface SubscriptionPlan {
  readonly planId?: number;
  readonly name: string;
  readonly displayName: string;
  readonly price: string;
  readonly monthlyPrice?: number;
  readonly maxProfiles?: number;
  readonly copy: string;
  readonly features: readonly string[];
  readonly featured?: boolean;
}

export interface RegisterUserApiRequest {
  readonly email: string;
  readonly password: string;
  readonly display_name: string;
  readonly age?: number;
  readonly plan_id?: number | null;
  readonly birth_date?: string | null;
  readonly preferred_theme?: 'light' | 'dark';
  readonly favorite_genres?: readonly string[];
}

export interface LoginApiRequest {
  readonly email: string;
  readonly password: string;
}

export interface GoogleLoginApiRequest {
  readonly id_token: string;
}

export interface GoogleClientIdApiResponse {
  readonly client_id: string | null;
}

export interface GoogleAuthorizeUrlApiResponse {
  readonly authorization_url: string;
}

export interface UserApiDto {
  readonly user_id: number;
  readonly email: string;
  readonly display_name: string;
  readonly age?: number | null;
  readonly plan_id: number;
  readonly birth_date?: string | null;
  readonly spotify_id?: string | null;
  readonly spotify_premium?: boolean | null;
  readonly primary_account_id?: number | null;
  readonly blocked_genres?: readonly string[] | null;
  readonly blocked_artists?: readonly string[] | null;
  readonly preferred_theme?: string;
  readonly favorite_genres?: readonly string[];
  readonly is_admin: boolean;
  readonly created_at?: string | null;
}

export interface FamilyMember {
  readonly userId: number;
  readonly email: string;
  readonly displayName: string;
  readonly age: number | null;
  readonly planId: number;
  readonly birthDate: string | null;
  readonly primaryAccountId: number | null;
  readonly blockedGenres: readonly string[];
  readonly blockedArtists: readonly string[];
  readonly isAdmin: boolean;
}

export interface AuthApiResponse {
  readonly access_token: string;
  readonly token_type: string;
  readonly user: UserApiDto;
}

export interface SpotifyAuthorizeUrlApiResponse {
  readonly authorization_url: string;
}

export interface SpotifyConnectCallbackApiRequest {
  readonly code: string;
  readonly state: string;
}

export interface PlanApiDto {
  readonly plan_id: number;
  readonly name: string;
  readonly monthly_price: number;
  readonly max_profiles: number;
}

export interface UserProfileApiDto {
  readonly user: UserApiDto;
  readonly plan: PlanApiDto;
  readonly recent_interactions: readonly InteractionApiDto[];
}

export interface AddFamilyMemberApiRequest {
  readonly dependent_user_id?: number | null;
  readonly email?: string | null;
  readonly password?: string | null;
  readonly display_name?: string | null;
  readonly birth_date?: string | null;
  readonly age?: number | null;
}

export interface UpdateMemberParentalControlsApiRequest {
  readonly blocked_genres: readonly string[];
  readonly blocked_artists?: readonly string[];
}

// Legacy aliases preserved for backward compatibility
export type CadastroUsuarioRequest = RegisterUserApiRequest;
export type LoginRequest = LoginApiRequest;
export type UsuarioResponse = UserApiDto;
