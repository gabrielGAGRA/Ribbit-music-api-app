import type { Song, TrackApiDto } from './track.model';

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
  readonly referencePlaylistId?: number | null;
  readonly sourcePlaylistId?: number | null;
  readonly referencePlaylistName?: string | null;
  readonly startDate?: string | null;
  readonly endDate?: string | null;
  readonly coverImageUrl?: string | null;
  readonly maxDurationSeconds?: number | null;
  readonly deckFilters?: string | null;
  readonly songs?: readonly Song[];
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
  readonly source_playlist_id?: number | null;
  readonly cover_image_url?: string | null;
}

export interface DeckPlaylistApiRequest {
  readonly name: string;
  readonly duration_minutes?: number | null;
  readonly genre?: string | readonly string[] | null;
  readonly year?: number | readonly number[] | null;
  readonly artist?: string | readonly string[] | null;
  readonly country?: string | readonly string[] | null;
  readonly description?: string | null;
  readonly reference_playlist_id?: number | null;
  readonly source_playlist_id?: number | null;
  readonly referencePlaylistId?: number | null;
  readonly sourcePlaylistId?: number | null;
  readonly startDate?: string | null;
  readonly endDate?: string | null;
}

export interface PlaylistSwipeAddApiRequest {
  readonly track_id: number;
  readonly action: 'like' | 'dislike';
}
