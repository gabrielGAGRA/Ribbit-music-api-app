import type { Song, TrackApiDto } from './track.model';

export interface JamQueueTrack {
  readonly song: Song;
  readonly votePoints: number;
}

export interface JamState {
  readonly jamId?: number;
  readonly roomId?: number;
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
  readonly deckSource?: 'livre' | 'curtidas' | 'playlist';
  readonly sourcePlaylistId?: number | null;
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
