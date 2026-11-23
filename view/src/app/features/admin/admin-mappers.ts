import type {
  AdminTrackAccessEntry as AdminTrackAccessEntryApiDto,
  AdminUserPlanSummary as AdminUserPlanSummaryApiDto,
  AudienceReportApiDto,
  ExecutiveDashboardApiDto,
  GenreAccessCountApiDto,
  PlanApiDto,
  PlatformCostSettingsApiDto,
  ReviewApiDto,
  TrackAccessRankApiDto,
  TrackAccessSource,
  TrackApiDto,
  UserApiDto,
} from '@ribbit/shared-types';

export interface AdminSession {
  readonly userId: number;
  readonly email: string;
  readonly displayName: string;
  readonly isAdmin: boolean;
}

export interface AdminUserPlanSummary {
  readonly userId: number;
  readonly email: string;
  readonly displayName: string;
  readonly age: number | null;
  readonly planName: string;
  readonly isAdmin: boolean;
}

export interface AdminAdministrator {
  readonly userId: number;
  readonly email: string;
  readonly displayName: string;
  readonly age: number | null;
  readonly isAdmin: boolean;
}

export interface AdminPlanItem {
  readonly planId: number;
  readonly name: string;
  readonly monthlyPrice: number;
  readonly maxProfiles: number;
}

export interface ExecutiveDashboard {
  readonly totalUsers: number;
  readonly estimatedNetRevenue: number;
  readonly usersByPlan: Readonly<Record<string, number>>;
  readonly revenueByPlan: Readonly<Record<string, number>>;
  readonly grossRevenue: number;
  readonly contentCost: number;
  readonly infrastructureCost: number;
  readonly totalCosts: number;
  readonly activeTracksCount: number;
  readonly contentCostPerTrack: number;
  readonly infrastructureFixedCost: number;
  readonly infrastructureCostPerUser: number;
}

export interface TrackAccessRank {
  readonly trackId: number;
  readonly title: string;
  readonly artist: string;
  readonly isDeleted: boolean;
  readonly accessCount: number;
}

export interface GenreAccessCount {
  readonly genre: string;
  readonly accessCount: number;
}

export interface AudienceReport {
  readonly totalUsers: number;
  readonly totalTracks: number;
  readonly activeTracks: number;
  readonly blockedGenres: Readonly<Record<string, number>>;
  readonly totalAccesses: number;
  readonly accessesByTrack: readonly TrackAccessRank[];
  readonly accessesByGenre: readonly GenreAccessCount[];
}

export interface PlatformCostSettings {
  readonly contentCostPerTrack: number;
  readonly infrastructureFixedCost: number;
  readonly infrastructureCostPerUser: number;
  readonly updatedAt: string | null;
}

export interface AdminModerationReview {
  readonly reviewId: number;
  readonly userId: number;
  readonly authorName: string;
  readonly trackId: number;
  readonly trackTitle: string;
  readonly trackArtist: string;
  readonly rating: number;
  readonly text: string;
  readonly likesCount: number;
  readonly createdAt: string;
  readonly isDeleted: boolean;
}

export interface AdminTrackAccessEntry {
  readonly accessId: number;
  readonly userId: number;
  readonly userDisplayName: string;
  readonly userEmail: string;
  readonly trackId: number;
  readonly trackTitle: string;
  readonly trackArtist: string;
  readonly trackGenre: string;
  readonly trackIsDeleted: boolean;
  readonly source: TrackAccessSource;
  readonly accessedAt: string;
}

export interface AdminTrackApiDto extends TrackApiDto {
  readonly likes_count?: number;
  readonly dislikes_count?: number;
  readonly superlikes_count?: number;
  readonly average_rating?: number | null;
  readonly review_count?: number;
}

export interface AdminTrackItem {
  readonly trackId: number;
  readonly title: string;
  readonly artist: string;
  readonly album: string | null;
  readonly genre: string;
  readonly durationSeconds: number;
  readonly releaseYear: number | null;
  readonly explicit: boolean;
  readonly isDeleted: boolean;
  readonly likesCount: number;
  readonly dislikesCount: number;
  readonly superlikesCount: number;
  readonly averageRating: number | null;
  readonly reviewCount: number;
}

export function mapAdminPlanDto(dto: PlanApiDto): AdminPlanItem {
  return {
    planId: dto.plan_id,
    name: dto.name,
    monthlyPrice: dto.monthly_price,
    maxProfiles: dto.max_profiles,
  };
}

export function mapAdminUserPlanSummaryDto(dto: AdminUserPlanSummaryApiDto): AdminUserPlanSummary {
  return {
    userId: dto.user_id,
    email: dto.email,
    displayName: dto.display_name,
    age: dto.age,
    planName: dto.plan_name,
    isAdmin: dto.is_admin,
  };
}

export function mapAdminAdministratorDto(dto: UserApiDto): AdminAdministrator {
  return {
    userId: dto.user_id,
    email: dto.email,
    displayName: dto.display_name,
    age: dto.age ?? null,
    isAdmin: dto.is_admin,
  };
}

export function mapAdminTrackDto(dto: AdminTrackApiDto): AdminTrackItem {
  return {
    trackId: dto.track_id,
    title: dto.title,
    artist: dto.artist,
    album: dto.album ?? null,
    genre: dto.genre,
    durationSeconds: dto.duration_seconds,
    releaseYear: dto.release_year ?? null,
    explicit: dto.explicit,
    isDeleted: dto.is_deleted ?? false,
    likesCount: dto.likes_count ?? 0,
    dislikesCount: dto.dislikes_count ?? 0,
    superlikesCount: dto.superlikes_count ?? 0,
    averageRating: dto.average_rating ?? null,
    reviewCount: dto.review_count ?? 0,
  };
}

export function mapExecutiveDashboardDto(dto: ExecutiveDashboardApiDto): ExecutiveDashboard {
  const planRevenueSum = Object.values(dto.revenue_by_plan).reduce((sum, value) => sum + value, 0);
  return {
    totalUsers: dto.total_users,
    estimatedNetRevenue: dto.estimated_net_revenue,
    usersByPlan: dto.users_by_plan,
    revenueByPlan: dto.revenue_by_plan,
    grossRevenue: dto.gross_revenue ?? planRevenueSum,
    contentCost: dto.content_cost ?? 0,
    infrastructureCost: dto.infrastructure_cost ?? 0,
    totalCosts: dto.total_costs ?? 0,
    activeTracksCount: dto.active_tracks_count ?? 0,
    contentCostPerTrack: dto.content_cost_per_track ?? 0.04,
    infrastructureFixedCost: dto.infrastructure_fixed_cost ?? 10,
    infrastructureCostPerUser: dto.infrastructure_cost_per_user ?? 0.5,
  };
}

function mapTrackAccessRankDto(dto: TrackAccessRankApiDto): TrackAccessRank {
  return {
    trackId: dto.track_id,
    title: dto.title,
    artist: dto.artist,
    isDeleted: dto.is_deleted,
    accessCount: dto.access_count,
  };
}

function mapGenreAccessCountDto(dto: GenreAccessCountApiDto): GenreAccessCount {
  return {
    genre: dto.genre,
    accessCount: dto.access_count,
  };
}

export function mapAudienceReportDto(dto: AudienceReportApiDto): AudienceReport {
  return {
    totalUsers: dto.total_users,
    totalTracks: dto.total_tracks,
    activeTracks: dto.active_tracks,
    blockedGenres: dto.blocked_genres,
    totalAccesses: dto.total_accesses ?? 0,
    accessesByTrack: (dto.accesses_by_track ?? []).map((item) => mapTrackAccessRankDto(item)),
    accessesByGenre: (dto.accesses_by_genre ?? []).map((item) => mapGenreAccessCountDto(item)),
  };
}

export function mapPlatformCostSettingsDto(dto: PlatformCostSettingsApiDto): PlatformCostSettings {
  return {
    contentCostPerTrack: dto.content_cost_per_track,
    infrastructureFixedCost: dto.infrastructure_fixed_cost,
    infrastructureCostPerUser: dto.infrastructure_cost_per_user,
    updatedAt: dto.updated_at ?? null,
  };
}

export function mapAdminTrackAccessEntryDto(
  dto: AdminTrackAccessEntryApiDto,
): AdminTrackAccessEntry {
  return {
    accessId: dto.access_id,
    userId: dto.user_id,
    userDisplayName: dto.user_display_name,
    userEmail: dto.user_email,
    trackId: dto.track_id,
    trackTitle: dto.track_title,
    trackArtist: dto.track_artist,
    trackGenre: dto.track_genre,
    trackIsDeleted: dto.track_is_deleted,
    source: dto.source,
    accessedAt: dto.accessed_at,
  };
}

function resolveReviewAuthorName(
  dto: ReviewApiDto,
  author: AdminUserPlanSummary | undefined,
): string {
  return dto.author_name ?? author?.displayName ?? `Usuário #${dto.user_id}`;
}

export function mapAdminModerationReviewDto(
  dto: ReviewApiDto,
  index: number,
  userById: ReadonlyMap<number, AdminUserPlanSummary>,
  trackById: ReadonlyMap<number, AdminTrackItem>,
): AdminModerationReview {
  const author = userById.get(dto.user_id);
  const track = trackById.get(dto.track_id);
  return {
    reviewId: dto.review_id ?? index + 1,
    userId: dto.user_id,
    authorName: resolveReviewAuthorName(dto, author),
    trackId: dto.track_id,
    trackTitle: dto.track_title ?? track?.title ?? `Faixa #${dto.track_id}`,
    trackArtist: dto.track_artist ?? track?.artist ?? 'Artista do Catálogo',
    rating: dto.rating,
    text: dto.text ?? '',
    likesCount: dto.likes_count,
    createdAt: dto.created_at ?? '',
    isDeleted: dto.is_deleted,
  };
}
