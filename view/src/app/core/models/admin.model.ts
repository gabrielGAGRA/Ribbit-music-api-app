import type { TrackAccessSource } from './track.model';

export interface AdminSession {
  readonly user_id: number;
  readonly email: string;
  readonly display_name: string;
  readonly is_admin: boolean;
}

export interface RegisterAdminApiRequest {
  readonly email: string;
  readonly password: string;
  readonly display_name: string;
  readonly age?: number;
  readonly birth_date?: string | null;
}

export interface TrackBlockApiResponse {
  readonly track_id: number | null;
  readonly blocked: boolean;
}

export interface TrackExplicitApiResponse {
  readonly track_id: number;
  readonly explicit: boolean;
}

export interface AdminUserPlanSummary {
  readonly user_id: number;
  readonly email: string;
  readonly display_name: string;
  readonly age: number | null;
  readonly plan_name: string;
  readonly is_admin: boolean;
}

export interface PlanBreakdownEntry {
  readonly planName: string;
  readonly userCount: number;
  readonly userPercent: number;
  readonly revenue: number;
  readonly revenuePercent: number;
  readonly isPaid: boolean;
  readonly profit: number;
  readonly marginPercent: number;
}

export interface BlockedGenreEntry {
  readonly genre: string;
  readonly count: number;
  readonly percent: number;
}

export interface FirestoreQuotaSummaryApiDto {
  readonly reads_today: number;
  readonly reads_free_limit: number;
  readonly reads_percent: number;
  readonly reads_rate_per_100k: number;
  readonly writes_today: number;
  readonly writes_free_limit: number;
  readonly writes_percent: number;
  readonly writes_rate_per_100k: number;
  readonly deletes_today: number;
  readonly deletes_free_limit: number;
  readonly deletes_percent: number;
  readonly deletes_rate_per_100k: number;
  readonly stored_bytes?: number;
  readonly stored_gib: number;
  readonly stored_free_limit_gib: number;
  readonly stored_percent: number;
  readonly egress_bytes_month?: number;
  readonly egress_gib_month: number;
  readonly egress_free_limit_gib: number;
  readonly egress_percent: number;
  readonly monthly_estimated_cost: number;
}

export interface ExecutiveDashboardApiDto {
  readonly total_users: number;
  readonly estimated_net_revenue: number;
  readonly users_by_plan: Readonly<Record<string, number>>;
  readonly revenue_by_plan: Readonly<Record<string, number>>;
  readonly profit_by_plan?: Readonly<Record<string, number>>;
  readonly paid_plans_revenue?: number;
  readonly paid_plans_profit?: number;
  readonly cost_to_revenue_percent?: number;
  readonly gross_revenue?: number;
  readonly content_cost?: number;
  readonly infrastructure_cost?: number;
  readonly total_costs?: number;
  readonly active_tracks_count?: number;
  readonly content_cost_per_track?: number;
  readonly infrastructure_fixed_cost?: number;
  readonly infrastructure_cost_per_user?: number;
  readonly firestore_usage?: FirestoreQuotaSummaryApiDto | null;
}

export interface TrackAccessRankApiDto {
  readonly track_id: number;
  readonly title: string;
  readonly artist: string;
  readonly is_deleted: boolean;
  readonly access_count: number;
}

export interface GenreAccessCountApiDto {
  readonly genre: string;
  readonly access_count: number;
}

export interface AudienceReportApiDto {
  readonly total_users: number;
  readonly total_tracks: number;
  readonly active_tracks: number;
  readonly blocked_genres: Readonly<Record<string, number>>;
  readonly total_accesses?: number;
  readonly accesses_by_track?: readonly TrackAccessRankApiDto[];
  readonly accesses_by_genre?: readonly GenreAccessCountApiDto[];
}

export interface PlatformCostSettingsApiDto {
  readonly content_cost_per_track: number;
  readonly infrastructure_fixed_cost: number;
  readonly infrastructure_cost_per_user: number;
  readonly updated_at?: string | null;
}

export interface UpdatePlatformCostsPayload {
  readonly content_cost_per_track: number;
  readonly infrastructure_fixed_cost: number;
  readonly infrastructure_cost_per_user: number;
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

export interface UpdateTrackGenreApiRequest {
  readonly genre: string;
}

export interface TrackGenreApiResponse {
  readonly track_id: number;
  readonly genre: string;
}

export interface CompactCatalogApiResponse {
  readonly new_version: number;
  readonly message: string;
}

export interface SyncCatalogVersionApiResponse {
  readonly synced: boolean;
  readonly version: number;
  readonly message: string;
}

export interface AdminTrackAccessEntry {
  readonly access_id: number;
  readonly user_id: number;
  readonly user_display_name: string;
  readonly user_email: string;
  readonly track_id: number;
  readonly track_title: string;
  readonly track_artist: string;
  readonly track_genre: string;
  readonly track_is_deleted: boolean;
  readonly source: TrackAccessSource;
  readonly accessed_at: string;
}
