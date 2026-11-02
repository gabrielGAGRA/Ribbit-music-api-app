export type IconName =
  | 'pond'
  | 'music'
  | 'users'
  | 'search'
  | 'user'
  | 'arrow'
  | 'chevron'
  | 'heart'
  | 'star'
  | 'close'
  | 'undo'
  | 'play'
  | 'pause'
  | 'filter'
  | 'bell'
  | 'plus'
  | 'clock'
  | 'headphones'
  | 'settings'
  | 'logout'
  | 'sparkles'
  | 'volume'
  | 'check'
  | 'send'
  | 'globe'
  | 'repeat'
  | 'sliders'
  | 'shield'
  | 'chart';

export type DecisionKind = 'like' | 'love' | 'reject';

export type SwipeApiAction = 'like' | 'superlike' | 'dislike';

export interface Decision {
  readonly index: number;
  readonly kind: DecisionKind;
  readonly trackId?: number;
}

export interface Song {
  readonly trackId?: number;
  readonly title: string;
  readonly artist: string;
  readonly genre: string;
  readonly time: string;
  readonly image: string;
  readonly album: string;
  readonly year: string;
  readonly match: number;
  readonly previewUrl?: string;
  readonly country?: string;
  readonly explicit?: boolean;
  readonly durationSeconds?: number;
}

export interface CommunityReview {
  readonly id: number;
  readonly author: string;
  readonly initials: string;
  readonly text: string;
  readonly likes: number;
  readonly age: string;
  readonly date: number;
  readonly userId?: number;
  readonly trackId?: number;
  readonly rating?: number;
  readonly songTitle?: string;
  readonly songArtist?: string;
  readonly songImage?: string;
}

export type ReferenceSource = 'curtidas' | 'amadas' | 'playlists' | 'livre';

export interface Playlist {
  readonly id?: string;
  readonly playlistId?: number;
  readonly name: string;
  readonly count: number;
  readonly duration: string;
  readonly description?: string;
  readonly isExported?: boolean;
  readonly spotifyPlaylistId?: string;
  readonly songs?: readonly Song[];
}

export interface NavigationItem {
  readonly id: string;
  readonly label: string;
  readonly sub: string;
  readonly icon: IconName;
}

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

export interface JamQueueTrack {
  readonly song: Song;
  readonly votePoints: number;
}

export interface JamState {
  readonly jamId?: number;
  readonly hostUserId?: number;
  readonly active: boolean;
  readonly code: string;
  readonly roomName: string;
  readonly votes: number;
  readonly voteThreshold: number;
  readonly durationHours: number;
  readonly durationMinutes: number;
  readonly accumulatedMinutes?: number;
  readonly superlikesCount?: number;
  readonly superlikesLimit?: number;
  readonly currentTrack?: Song;
  readonly queueItems?: readonly JamQueueTrack[];
}

export interface MetricItem {
  readonly value: string;
  readonly label: string;
  readonly detail: string;
  readonly icon: IconName;
}

export interface RankedArtist {
  readonly song: Song;
  readonly rank: string;
  readonly time: string;
}

export interface RankedGenre {
  readonly genre: string;
  readonly percentage: number;
  readonly rank: string;
}

// --- Backend Wire DTOs (snake_case from FastAPI) ---

export interface RegisterUserApiRequest {
  readonly email: string;
  readonly password: string;
  readonly display_name: string;
  readonly age?: number;
  readonly plan_id?: number | null;
  readonly birth_date?: string | null;
}

export interface LoginApiRequest {
  readonly email: string;
  readonly password: string;
}

export interface UserApiDto {
  readonly user_id: number;
  readonly email: string;
  readonly display_name: string;
  readonly age: number;
  readonly plan_id: number;
  readonly birth_date?: string | null;
  readonly spotify_id?: string | null;
  readonly primary_account_id?: number | null;
  readonly blocked_genres?: readonly string[] | null;
  readonly is_admin: boolean;
  readonly created_at?: string | null;
}

export interface AuthApiResponse {
  readonly access_token: string;
  readonly token_type: string;
  readonly user: UserApiDto;
}

export interface PlanApiDto {
  readonly plan_id: number;
  readonly name: string;
  readonly monthly_price: number;
  readonly max_profiles: number;
}

export interface TrackApiDto {
  readonly track_id: number;
  readonly title: string;
  readonly artist: string;
  readonly duration_seconds: number;
  readonly genre: string;
  readonly spotify_id?: string | null;
  readonly album?: string | null;
  readonly country?: string | null;
  readonly release_year?: number | null;
  readonly cover_url?: string | null;
  readonly itunes_preview_url?: string | null;
  readonly explicit: boolean;
  readonly is_deleted: boolean;
}

export interface InteractionApiDto {
  readonly interaction_id: number;
  readonly user_id: number;
  readonly track_id: number;
  readonly action: string;
  readonly created_at?: string | null;
}

export interface UserProfileApiDto {
  readonly user: UserApiDto;
  readonly plan: PlanApiDto;
  readonly recent_interactions: readonly InteractionApiDto[];
}

export interface AnnualStatsApiDto {
  readonly user_id: number;
  readonly estimated_listening_hours: number;
  readonly total_likes: number;
  readonly top_genres: readonly string[];
  readonly top_artists: readonly string[];
}

export interface PlaylistApiDto {
  readonly playlist_id: number;
  readonly user_id: number;
  readonly name: string;
  readonly description?: string | null;
  readonly spotify_playlist_id?: string | null;
  readonly is_exported: boolean;
  readonly tracks: readonly TrackApiDto[];
  readonly max_duration_seconds?: number | null;
  readonly deck_filters?: string | null;
  readonly total_duration_seconds: number;
}

export interface DeckPlaylistApiRequest {
  readonly name: string;
  readonly duration_minutes?: number | null;
  readonly genre?: string | null;
  readonly year?: number | null;
  readonly artist?: string | null;
  readonly country?: string | null;
  readonly description?: string | null;
}

export interface PaginatedTracksApiDto {
  readonly items: readonly TrackApiDto[];
  readonly next_cursor?: number | null;
  readonly has_more: boolean;
}

export interface ReviewApiDto {
  readonly review_id?: number | null;
  readonly user_id: number;
  readonly track_id: number;
  readonly rating: number;
  readonly text?: string | null;
  readonly likes_count: number;
  readonly is_deleted: boolean;
  readonly created_at?: string | null;
}

export interface RecentInteractedTrackApiDto {
  readonly interaction: InteractionApiDto;
  readonly track: TrackApiDto;
}

export interface CreateJamApiRequest {
  readonly room_name: string;
  readonly duration_minutes: number;
  readonly max_superlikes?: number;
  readonly skip_votes_threshold: number;
  readonly deck_source?: string;
  readonly source_playlist_id?: number | null;
}

export interface JamQueueItemApiDto {
  readonly jam_queue_id?: number | null;
  readonly jam_id: number;
  readonly track_id: number;
  readonly vote_points: number;
}

export interface JamApiDto {
  readonly jam_id?: number | null;
  readonly host_user_id: number;
  readonly room_name: string;
  readonly room_code: string;
  readonly is_active: boolean;
  readonly current_track_id?: number | null;
  readonly duration_minutes: number;
  readonly max_superlikes: number;
  readonly superlikes_used: number;
  readonly skip_votes_threshold: number;
  readonly accumulated_duration_seconds: number;
  readonly deck_source: string;
  readonly source_playlist_id?: number | null;
}

export interface JamStateApiDto {
  readonly jam: JamApiDto;
  readonly current_track?: TrackApiDto | null;
  readonly queue: readonly JamQueueItemApiDto[];
  readonly skip_votes: number;
}

export interface SkipVoteApiDto {
  readonly jam_id: number;
  readonly track_id: number;
  readonly votes: number;
  readonly threshold: number;
  readonly advanced: boolean;
  readonly is_active: boolean;
  readonly success: boolean;
}

export interface ActionSuccessApiDto {
  readonly success: boolean;
}

// Legacy aliases preserved for backward compatibility
export type CadastroUsuarioRequest = RegisterUserApiRequest;
export type LoginRequest = LoginApiRequest;
export type UsuarioResponse = UserApiDto;

// --- Admin Console Contracts (/api/admin/*) ---

export interface AdminAccount {
  readonly user_id: number;
  readonly email: string;
  readonly password: string;
  readonly display_name: string;
  readonly age: number;
  readonly plan_id: number;
  readonly is_admin: boolean;
  readonly primary_account_id?: number;
  readonly blocked_genres: readonly string[];
  readonly created_at: string;
}

export interface AdminSession {
  readonly user_id: number;
  readonly email: string;
  readonly display_name: string;
  readonly is_admin: boolean;
}

export interface AdminUserPlanSummary {
  readonly user_id: number;
  readonly email: string;
  readonly display_name: string;
  readonly age: number;
  readonly plan_name: string;
  readonly is_admin: boolean;
}

export interface PlanBreakdownEntry {
  readonly planName: string;
  readonly userCount: number;
  readonly userPercent: number;
  readonly revenue: number;
  readonly revenuePercent: number;
}

export interface BlockedGenreEntry {
  readonly genre: string;
  readonly count: number;
  readonly percent: number;
}

export interface ExecutiveDashboardApiDto {
  readonly total_users: number;
  readonly estimated_net_revenue: number;
  readonly users_by_plan: Readonly<Record<string, number>>;
  readonly revenue_by_plan: Readonly<Record<string, number>>;
}

export interface AudienceReportApiDto {
  readonly total_users: number;
  readonly total_tracks: number;
  readonly active_tracks: number;
  readonly blocked_genres: Readonly<Record<string, number>>;
}

export interface UpdateAdminPlanPayload {
  readonly new_name?: string;
  readonly new_price?: number;
  readonly max_profiles?: number;
}

export interface AdminModerationReview {
  readonly review_id: number;
  readonly user_id: number;
  readonly author_name: string;
  readonly track_id: number;
  readonly track_title: string;
  readonly track_artist: string;
  readonly rating: number;
  readonly text: string;
  readonly likes_count: number;
  readonly created_at: string;
  readonly is_deleted: boolean;
}

// --- Admin Console Contracts (/api/admin/*) ---

export interface AdminAccount {
  readonly user_id: number;
  readonly email: string;
  readonly password: string;
  readonly display_name: string;
  readonly age: number;
  readonly plan_id: number;
  readonly is_admin: boolean;
  readonly primary_account_id?: number;
  readonly blocked_genres: readonly string[];
  readonly created_at: string;
}

export interface AdminSession {
  readonly user_id: number;
  readonly email: string;
  readonly display_name: string;
  readonly is_admin: boolean;
}

export interface AdminUserPlanSummary {
  readonly user_id: number;
  readonly email: string;
  readonly display_name: string;
  readonly age: number;
  readonly plan_name: string;
  readonly is_admin: boolean;
}

export interface PlanBreakdownEntry {
  readonly planName: string;
  readonly userCount: number;
  readonly userPercent: number;
  readonly revenue: number;
  readonly revenuePercent: number;
}

export interface BlockedGenreEntry {
  readonly genre: string;
  readonly count: number;
  readonly percent: number;
}

export interface ExecutiveDashboardApiDto {
  readonly total_users: number;
  readonly estimated_net_revenue: number;
  readonly users_by_plan: Readonly<Record<string, number>>;
  readonly revenue_by_plan: Readonly<Record<string, number>>;
}

export interface AudienceReportApiDto {
  readonly total_users: number;
  readonly total_tracks: number;
  readonly active_tracks: number;
  readonly blocked_genres: Readonly<Record<string, number>>;
}

export interface UpdateAdminPlanPayload {
  readonly new_name?: string;
  readonly new_price?: number;
  readonly max_profiles?: number;
}

export interface AdminModerationReview {
  readonly review_id: number;
  readonly user_id: number;
  readonly author_name: string;
  readonly track_id: number;
  readonly track_title: string;
  readonly track_artist: string;
  readonly rating: number;
  readonly text: string;
  readonly likes_count: number;
  readonly created_at: string;
  readonly is_deleted: boolean;
}
