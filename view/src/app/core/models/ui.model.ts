import type { Song } from './track.model';

export type IconName =
  | 'pond'
  | 'music'
  | 'users'
  | 'search'
  | 'user'
  | 'arrow'
  | 'arrow-left'
  | 'chevron'
  | 'chevron-left'
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
  | 'lock'
  | 'chart'
  | 'sun'
  | 'moon';

export interface NavigationItem {
  readonly id: string;
  readonly label: string;
  readonly sub: string;
  readonly icon: IconName;
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
  readonly likes: number;
  readonly superlikes: number;
  readonly totalPositive: number;
  readonly summary: string;
}

export interface RankedGenre {
  readonly genre: string;
  readonly likes: number;
  readonly superlikes: number;
  readonly dislikes: number;
  readonly totalPositive: number;
  readonly percentage: number;
  readonly rank: string;
}

export interface GenreStatApiDto {
  readonly genre: string;
  readonly likes: number;
  readonly superlikes: number;
  readonly dislikes: number;
  readonly total_positive: number;
}

export interface ArtistStatApiDto {
  readonly artist: string;
  readonly likes: number;
  readonly superlikes: number;
  readonly dislikes: number;
  readonly total_positive: number;
  readonly cover_url?: string | null;
}

export interface YearlyInteractionStatApiDto {
  readonly year: number;
  readonly likes: number;
  readonly superlikes: number;
  readonly dislikes: number;
  readonly total: number;
}

export interface MonthlyInteractionStatApiDto {
  readonly month: number;
  readonly likes: number;
  readonly superlikes: number;
  readonly dislikes: number;
  readonly total: number;
}

export interface ReleaseYearStatApiDto {
  readonly release_year: number;
  readonly likes: number;
  readonly superlikes: number;
  readonly total_positive: number;
}

export interface SourceStatApiDto {
  readonly source: string;
  readonly likes: number;
  readonly superlikes: number;
  readonly dislikes: number;
  readonly total: number;
}

export interface AnnualStatsApiDto {
  readonly user_id: number;
  readonly year?: number | null;
  readonly available_years?: readonly number[];
  readonly total_interactions?: number;
  readonly total_likes: number;
  readonly total_superlikes?: number;
  readonly total_dislikes?: number;
  readonly positive_rate?: number;
  readonly top_genres: readonly GenreStatApiDto[];
  readonly top_artists: readonly ArtistStatApiDto[];
  readonly by_interaction_year?: readonly YearlyInteractionStatApiDto[];
  readonly by_month?: readonly MonthlyInteractionStatApiDto[];
  readonly by_release_year?: readonly ReleaseYearStatApiDto[];
  readonly by_source?: readonly SourceStatApiDto[];
  readonly total_reviews?: number;
  readonly average_rating?: number;
  readonly total_playlists?: number;
  readonly total_jams_participated?: number;
}

export interface MonthlyActivityBar {
  readonly month: number;
  readonly label: string;
  readonly likes: number;
  readonly superlikes: number;
  readonly dislikes: number;
  readonly total: number;
  readonly x: number;
  readonly dislikesY: number;
  readonly dislikesHeight: number;
  readonly likesY: number;
  readonly likesHeight: number;
  readonly superlikesY: number;
  readonly superlikesHeight: number;
  readonly totalLabelY: number;
  readonly tooltip: string;
}

export interface ReleaseEraPoint {
  readonly decade: number;
  readonly label: string;
  readonly totalPositive: number;
  readonly likes: number;
  readonly superlikes: number;
  readonly percentage: number;
}

export interface InteractionSourcePoint {
  readonly source: string;
  readonly label: string;
  readonly total: number;
  readonly likes: number;
  readonly superlikes: number;
  readonly dislikes: number;
  readonly percentage: number;
}

export interface DashboardViewData {
  readonly selectedYear: number | null;
  readonly availableYears: readonly number[];
  readonly totalInteractions: number;
  readonly positiveRatePercent: number;
  readonly totalLikes: number;
  readonly totalSuperlikes: number;
  readonly totalDislikes: number;
  readonly metrics: readonly MetricItem[];
  readonly genres: readonly RankedGenre[];
  readonly artists: readonly RankedArtist[];
  readonly monthlyBars: readonly MonthlyActivityBar[];
  readonly maxMonthlyTotal: number;
  readonly releaseEras: readonly ReleaseEraPoint[];
  readonly sources: readonly InteractionSourcePoint[];
  readonly totalReviews: number;
  readonly averageRating: number;
  readonly totalPlaylists: number;
  readonly totalJamsParticipated: number;
}

export interface ActionSuccessApiDto {
  readonly success: boolean;
}
