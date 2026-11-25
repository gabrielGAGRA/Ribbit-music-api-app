import type {
  AdminTrackAccessEntry as AdminTrackAccessEntryApiDto,
  AdminUserPlanSummary as AdminUserPlanSummaryApiDto,
  AudienceReportApiDto,
  ExecutiveDashboardApiDto,
  FirestoreQuotaSummaryApiDto,
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

export interface FirestoreQuotaSummary {
  readonly readsToday: number;
  readonly readsFreeLimit: number;
  readonly readsPercent: number;
  readonly readsRatePer100k: number;
  readonly writesToday: number;
  readonly writesFreeLimit: number;
  readonly writesPercent: number;
  readonly writesRatePer100k: number;
  readonly deletesToday: number;
  readonly deletesFreeLimit: number;
  readonly deletesPercent: number;
  readonly deletesRatePer100k: number;
  readonly storedBytes: number;
  readonly storedGib: number;
  readonly storedFreeLimitGib: number;
  readonly storedPercent: number;
  readonly egressBytesMonth: number;
  readonly egressGibMonth: number;
  readonly egressFreeLimitGib: number;
  readonly egressPercent: number;
  readonly monthlyEstimatedCost: number;
}

export interface ExecutiveDashboard {
  readonly totalUsers: number;
  readonly estimatedNetRevenue: number;
  readonly usersByPlan: Readonly<Record<string, number>>;
  readonly revenueByPlan: Readonly<Record<string, number>>;
  readonly profitByPlan: Readonly<Record<string, number>>;
  readonly paidPlansRevenue: number;
  readonly paidPlansProfit: number;
  readonly costToRevenuePercent: number;
  readonly grossRevenue: number;
  readonly contentCost: number;
  readonly infrastructureCost: number;
  readonly totalCosts: number;
  readonly activeTracksCount: number;
  readonly contentCostPerTrack: number;
  readonly infrastructureFixedCost: number;
  readonly infrastructureCostPerUser: number;
  readonly firestoreUsage: FirestoreQuotaSummary;
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

export const DEFAULT_FIRESTORE_QUOTA: FirestoreQuotaSummary = {
  readsToday: 0,
  readsFreeLimit: 50_000,
  readsPercent: 0,
  readsRatePer100k: 0.06,
  writesToday: 0,
  writesFreeLimit: 20_000,
  writesPercent: 0,
  writesRatePer100k: 0.18,
  deletesToday: 0,
  deletesFreeLimit: 20_000,
  deletesPercent: 0,
  deletesRatePer100k: 0.02,
  storedBytes: 0,
  storedGib: 0,
  storedFreeLimitGib: 1,
  storedPercent: 0,
  egressBytesMonth: 0,
  egressGibMonth: 0,
  egressFreeLimitGib: 10,
  egressPercent: 0,
  monthlyEstimatedCost: 0,
};

function resolveBytesFromGib(bytes: number | undefined, gib: number): number {
  if (bytes !== undefined) return bytes;
  return gib > 0 ? Math.round(gib * 1024 ** 3) : 0;
}

function mapFirestoreQuotaSummaryDto(
  dto: FirestoreQuotaSummaryApiDto | null | undefined,
): FirestoreQuotaSummary {
  if (!dto) return DEFAULT_FIRESTORE_QUOTA;
  return {
    readsToday: dto.reads_today,
    readsFreeLimit: dto.reads_free_limit,
    readsPercent: dto.reads_percent,
    readsRatePer100k: dto.reads_rate_per_100k,
    writesToday: dto.writes_today,
    writesFreeLimit: dto.writes_free_limit,
    writesPercent: dto.writes_percent,
    writesRatePer100k: dto.writes_rate_per_100k,
    deletesToday: dto.deletes_today,
    deletesFreeLimit: dto.deletes_free_limit,
    deletesPercent: dto.deletes_percent,
    deletesRatePer100k: dto.deletes_rate_per_100k,
    storedBytes: resolveBytesFromGib(dto.stored_bytes, dto.stored_gib),
    storedGib: dto.stored_gib,
    storedFreeLimitGib: dto.stored_free_limit_gib,
    storedPercent: dto.stored_percent,
    egressBytesMonth: resolveBytesFromGib(dto.egress_bytes_month, dto.egress_gib_month),
    egressGibMonth: dto.egress_gib_month,
    egressFreeLimitGib: dto.egress_free_limit_gib,
    egressPercent: dto.egress_percent,
    monthlyEstimatedCost: dto.monthly_estimated_cost,
  };
}

function computeCostToRevenuePercent(grossRevenue: number, totalCosts: number): number {
  if (grossRevenue > 0) return Math.round((totalCosts / grossRevenue) * 1000) / 10;
  return totalCosts > 0 ? 100 : 0;
}

function mapDashboardCostFields(
  dto: ExecutiveDashboardApiDto,
  grossRevenue: number,
  totalCosts: number,
): Pick<
  ExecutiveDashboard,
  | 'contentCost'
  | 'infrastructureCost'
  | 'totalCosts'
  | 'activeTracksCount'
  | 'contentCostPerTrack'
  | 'infrastructureFixedCost'
  | 'infrastructureCostPerUser'
  | 'costToRevenuePercent'
> {
  return {
    contentCost: dto.content_cost ?? 0,
    infrastructureCost: dto.infrastructure_cost ?? 0,
    totalCosts,
    activeTracksCount: dto.active_tracks_count ?? 0,
    contentCostPerTrack: dto.content_cost_per_track ?? 0.04,
    infrastructureFixedCost: dto.infrastructure_fixed_cost ?? 25,
    infrastructureCostPerUser: dto.infrastructure_cost_per_user ?? 0,
    costToRevenuePercent:
      dto.cost_to_revenue_percent ?? computeCostToRevenuePercent(grossRevenue, totalCosts),
  };
}

export function mapExecutiveDashboardDto(dto: ExecutiveDashboardApiDto): ExecutiveDashboard {
  const planRevenueSum = Object.values(dto.revenue_by_plan).reduce((sum, value) => sum + value, 0);
  const grossRevenue = dto.gross_revenue ?? planRevenueSum;
  const totalCosts = dto.total_costs ?? 0;
  return {
    totalUsers: dto.total_users,
    estimatedNetRevenue: dto.estimated_net_revenue,
    usersByPlan: dto.users_by_plan,
    revenueByPlan: dto.revenue_by_plan,
    profitByPlan: dto.profit_by_plan ?? {},
    paidPlansRevenue: dto.paid_plans_revenue ?? grossRevenue,
    paidPlansProfit: dto.paid_plans_profit ?? Math.round((grossRevenue - totalCosts) * 100) / 100,
    grossRevenue,
    ...mapDashboardCostFields(dto, grossRevenue, totalCosts),
    firestoreUsage: mapFirestoreQuotaSummaryDto(dto.firestore_usage),
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
