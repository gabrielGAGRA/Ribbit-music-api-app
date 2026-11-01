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
  | 'repeat';

export type DecisionKind = 'like' | 'love' | 'reject';

export interface Decision {
  readonly index: number;
  readonly kind: DecisionKind;
}

export interface Song {
  readonly title: string;
  readonly artist: string;
  readonly genre: string;
  readonly time: string;
  readonly image: string;
  readonly album: string;
  readonly year: string;
  readonly match: number;
}

export interface CommunityReview {
  readonly id: number;
  readonly author: string;
  readonly initials: string;
  readonly text: string;
  readonly likes: number;
  readonly age: string;
  readonly date: number;
}

export type ReferenceSource = 'curtidas' | 'amadas' | 'playlists' | 'livre';

export interface Playlist {
  readonly id?: string;
  readonly name: string;
  readonly count: number;
  readonly duration: string;
  readonly songs?: readonly Song[];
}

export interface NavigationItem {
  readonly id: string;
  readonly label: string;
  readonly sub: string;
  readonly icon: IconName;
}

export interface SubscriptionPlan {
  readonly name: string;
  readonly displayName: string;
  readonly price: string;
  readonly copy: string;
  readonly features: readonly string[];
  readonly featured?: boolean;
}

export interface JamState {
  readonly active: boolean;
  readonly code: string;
  readonly roomName: string;
  readonly votes: number;
  readonly voteThreshold: number;
  readonly durationHours: number;
  readonly durationMinutes: number;
  readonly superlikesCount?: number;
  readonly superlikesLimit?: number;
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

export interface CadastroUsuarioRequest {
  readonly nome_exibicao: string;
  readonly email: string;
  readonly senha: string;
  readonly data_nascimento: string;
  readonly plano_id?: number | null;
}

export interface LoginRequest {
  readonly email: string;
  readonly senha: string;
}

export interface UsuarioResponse {
  readonly usuario_id: number;
  readonly email: string;
  readonly nome_exibicao: string;
  readonly idade: number;
  readonly data_nascimento?: string | null;
  readonly plano_id: number;
  readonly spotify_id?: string | null;
  readonly titular_id?: number | null;
  readonly generos_bloqueados?: string | null;
  readonly is_admin: boolean;
  readonly criado_em?: string | null;
}


