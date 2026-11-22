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
  readonly averageRating?: number | null;
  readonly reviewCount?: number;
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
  readonly average_rating?: number | null;
  readonly review_count?: number;
}

export interface InteractionApiDto {
  readonly interaction_id: number;
  readonly user_id: number;
  readonly track_id: number;
  readonly action: string;
  readonly created_at?: string | null;
}

export interface UndoInteractionApiDto {
  readonly success: boolean;
  readonly interaction_id: number;
  readonly track_id: number;
  readonly action: string;
  readonly created_at: string;
  readonly track?: TrackApiDto | null;
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
  readonly author_name?: string | null;
  readonly track_title?: string | null;
  readonly track_artist?: string | null;
  readonly track_image?: string | null;
}

export interface RecentInteractedTrackApiDto {
  readonly interaction: InteractionApiDto;
  readonly track: TrackApiDto;
}

export type TrackAccessSource =
  | 'swipe'
  | 'play'
  | 'details'
  | 'search'
  | 'playlist'
  | 'profile'
  | 'jam';

export interface TrackAccessHistoryItem {
  readonly access_id: number;
  readonly user_id: number;
  readonly track_id: number;
  readonly track_title: string;
  readonly track_artist: string;
  readonly track_genre: string;
  readonly track_album?: string | null;
  readonly track_duration_seconds: number;
  readonly track_cover_url?: string | null;
  readonly track_preview_url?: string | null;
  readonly track_explicit: boolean;
  readonly source: TrackAccessSource;
  readonly accessed_at: string;
}

export interface UserAccessHistoryApiDto {
  readonly items: readonly TrackAccessHistoryItem[];
  readonly seen_track_ids: readonly number[];
}

export interface RecordTrackAccessApiDto {
  readonly access_id?: number | null;
  readonly user_id: number;
  readonly track_id: number;
  readonly source: TrackAccessSource;
  readonly accessed_at?: string | null;
}
