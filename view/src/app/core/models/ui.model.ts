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
  readonly time: string;
}

export interface RankedGenre {
  readonly genre: string;
  readonly percentage: number;
  readonly rank: string;
}

export interface AnnualStatsApiDto {
  readonly user_id: number;
  readonly estimated_listening_hours: number;
  readonly total_likes: number;
  readonly top_genres: readonly string[];
  readonly top_artists: readonly string[];
}

export interface ActionSuccessApiDto {
  readonly success: boolean;
}
