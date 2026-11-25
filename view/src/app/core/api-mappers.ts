import type {
  AnnualStatsApiDto,
  ArtistStatApiDto,
  CommunityReview,
  DashboardViewData,
  DecisionKind,
  FamilyMember,
  GenreStatApiDto,
  InteractionSourcePoint,
  JamQueueTrack,
  JamState,
  JamStateApiDto,
  MetricItem,
  MonthlyActivityBar,
  MonthlyInteractionStatApiDto,
  PlanApiDto,
  Playlist,
  PlaylistApiDto,
  RankedArtist,
  RankedGenre,
  ReferenceSource,
  ReleaseEraPoint,
  ReleaseYearStatApiDto,
  ReviewApiDto,
  Song,
  SourceStatApiDto,
  SubscriptionPlan,
  SwipeApiAction,
  TrackApiDto,
  UserApiDto,
} from '@ribbit/shared-types';
import { formatGenreLabel } from './genre-catalog';

const FALLBACK_COVERS: readonly string[] = [
  'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=900&q=85',
  'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=900&q=85',
  'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=900&q=85',
  'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=900&q=85',
  'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=900&q=85',
  'https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?auto=format&fit=crop&w=900&q=85',
];

function isPlaceholderMediaUrl(url: string | null | undefined): boolean {
  if (!url || url.trim().length === 0) return true;
  return url.includes('example.com');
}

/** Formats duration in seconds as m:ss. */
export function formatDurationSeconds(seconds: number): string {
  const safe = Number.isFinite(seconds) && seconds > 0 ? Math.round(seconds) : 0;
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

/** Parses a raw value into a valid ReferenceSource, or null. */
export function toReferenceSource(value: unknown): ReferenceSource | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim().toLowerCase();
  if (
    normalized === 'curtidas' ||
    normalized === 'amadas' ||
    normalized === 'playlists' ||
    normalized === 'livre'
  ) {
    return normalized;
  }
  return null;
}

/** Extracts reference_source from serialized backend deck_filters JSON. */
export function extractReferenceSourceFromFilters(
  deckFilters: string | null | undefined,
): ReferenceSource | null {
  if (!deckFilters) return null;
  try {
    const parsed: unknown = JSON.parse(deckFilters);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return null;
    }
    return 'reference_source' in parsed ? toReferenceSource(parsed.reference_source) : null;
  } catch {
    return null;
  }
}

function parseTimeDurationSeconds(rawTime: string): number {
  const parts = rawTime.split(':').map((part) => Number(part.trim()));
  if (parts.length !== 2) return 0;
  const [mins = Number.NaN, secs = Number.NaN] = parts;
  if (!Number.isFinite(mins) || !Number.isFinite(secs) || mins < 0 || secs < 0) {
    return 0;
  }
  return Math.round(mins * 60 + secs);
}

/** Resolves a Song's duration in seconds from durationSeconds or formatted m:ss time. */
export function resolveSongDurationSeconds(song: Song): number {
  const seconds = song.durationSeconds;
  if (seconds !== undefined && Number.isFinite(seconds) && seconds > 0) {
    return seconds;
  }
  return parseTimeDurationSeconds(song.time);
}

/** Sums the duration in seconds across a list of songs. */
export function computeSongsDurationSeconds(songs: readonly Song[]): number {
  return songs.reduce((acc, song) => acc + resolveSongDurationSeconds(song), 0);
}

/** Computes total playlist duration seconds and returns whether its cap is reached. */
export function isPlaylistDurationLimitReached(playlist: Playlist): boolean {
  const max = playlist.maxDurationSeconds;
  if (max == null || max <= 0) return false;
  const songs = playlist.songs ?? [];
  const totalSeconds =
    songs.length > 0 ? computeSongsDurationSeconds(songs) : (playlist.totalDurationSeconds ?? 0);
  return totalSeconds >= max;
}

/** Formats total seconds into human-readable minutes label. */
export function formatTotalMinutes(totalSeconds: number): string {
  const safe = Number.isFinite(totalSeconds) && totalSeconds > 0 ? totalSeconds : 0;
  if (safe === 0) return '0 min';
  const mins = Math.max(1, Math.round(safe / 60));
  return `${mins} min`;
}

/** Resolves a valid cover image URL, substituting seed placeholders deterministically. */
export function resolveCoverUrl(rawUrl: string | null | undefined, seed: number): string {
  if (!isPlaceholderMediaUrl(rawUrl) && rawUrl) {
    return rawUrl;
  }
  const idx = Math.abs(seed) % FALLBACK_COVERS.length;
  return FALLBACK_COVERS[idx] ?? FALLBACK_COVERS[0] ?? '';
}

/** Resolves an audio preview URL, omitting unplayable seed placeholders. */
export function resolvePreviewUrl(rawUrl: string | null | undefined): string | undefined {
  if (isPlaceholderMediaUrl(rawUrl) || !rawUrl) {
    return undefined;
  }
  return rawUrl;
}

/** Maps a backend TrackApiDto into the UI Song view model. */
export function mapTrackDtoToSong(dto: TrackApiDto): Song {
  const previewUrl = resolvePreviewUrl(dto.itunes_preview_url);
  const matchScore = 88 + (dto.track_id % 11);
  return {
    trackId: dto.track_id,
    title: dto.title,
    artist: dto.artist,
    genre: formatGenreLabel(dto.genre),
    time: formatDurationSeconds(dto.duration_seconds),
    image: resolveCoverUrl(dto.cover_url, dto.track_id),
    album: dto.album ?? 'Single',
    year: dto.release_year ? String(dto.release_year) : '2024',
    match: matchScore,
    ...(previewUrl ? { previewUrl } : {}),
    ...(dto.country ? { country: dto.country } : {}),
    explicit: dto.explicit,
    ...(dto.is_deleted ? { isDeleted: true } : {}),
    durationSeconds: dto.duration_seconds,
    averageRating: dto.average_rating ?? null,
    reviewCount: dto.review_count ?? 0,
  };
}

/** Maps a backend PlaylistApiDto into the UI Playlist view model. */
export function mapPlaylistDtoToPlaylist(dto: PlaylistApiDto): Playlist {
  const songs = dto.tracks.map((track) => mapTrackDtoToSong(track));
  const computedSeconds =
    dto.total_duration_seconds > 0
      ? dto.total_duration_seconds
      : dto.tracks.reduce((acc, item) => acc + item.duration_seconds, 0);
  const durationLabel = computedSeconds > 0 ? formatTotalMinutes(computedSeconds) : '0 min';
  const referenceSource = extractReferenceSourceFromFilters(dto.deck_filters);

  return {
    id: String(dto.playlist_id),
    playlistId: dto.playlist_id,
    name: dto.name,
    count: songs.length,
    duration: durationLabel,
    totalDurationSeconds: computedSeconds,
    ...(dto.description ? { description: dto.description } : {}),
    isExported: dto.is_exported,
    ...(dto.spotify_playlist_id ? { spotifyPlaylistId: dto.spotify_playlist_id } : {}),
    ...(dto.source_playlist_id != null ? { sourcePlaylistId: dto.source_playlist_id } : {}),
    ...(dto.cover_image_url ? { coverImageUrl: dto.cover_image_url } : {}),
    ...(dto.max_duration_seconds != null ? { maxDurationSeconds: dto.max_duration_seconds } : {}),
    ...(dto.deck_filters ? { deckFilters: dto.deck_filters } : {}),
    ...(referenceSource ? { referenceSource } : {}),
    songs,
  };
}

/** Translates a UI DecisionKind into the backend SwipeApiAction. */
export function mapDecisionToApiAction(kind: DecisionKind): SwipeApiAction {
  switch (kind) {
    case 'like':
      return 'like';
    case 'love':
      return 'superlike';
    case 'reject':
      return 'dislike';
    default: {
      const exhaustive: never = kind;
      return exhaustive;
    }
  }
}

/** Translates a backend interaction action string into a UI DecisionKind. */
export function mapApiActionToDecision(action: string): DecisionKind {
  const normalized = action.trim().toLowerCase();
  if (normalized === 'superlike' || normalized === 'amada') return 'love';
  if (normalized === 'dislike' || normalized === 'deslike' || normalized === 'rejeitada') {
    return 'reject';
  }
  return 'like';
}

function formatPriceBRL(value: number): string {
  if (value <= 0) return 'R$ 0';
  return `R$ ${value.toFixed(2).replace('.', ',')}`;
}

function resolvePlanMetadata(plan: PlanApiDto): {
  readonly displayName: string;
  readonly copy: string;
  readonly features: readonly string[];
  readonly featured: boolean;
} {
  const lower = plan.name.toLowerCase();
  if (lower === 'free') {
    return {
      displayName: 'Ribbit Free',
      copy: 'Para descobrir no seu ritmo.',
      features: ['Swipes ilimitados', 'Playlists manuais', 'Prévia de 30 segundos'],
      featured: false,
    };
  }
  if (lower.includes('fam') || plan.max_profiles > 1) {
    return {
      displayName: 'Ribbit Jam',
      copy: `Até ${plan.max_profiles} perfis, cada um no seu ritmo.`,
      features: [
        `Até ${plan.max_profiles} contas`,
        'Jams privadas ilimitadas',
        'Controle familiar',
        'Recomendações separadas',
      ],
      featured: false,
    };
  }
  return {
    displayName: 'Ribbit Pro',
    copy: 'Sua experiência completa.',
    features: [
      'Tudo do plano Free',
      'Dashboard anual e estatísticas',
      'Bloqueio de gêneros e revisão de swipes',
      'Playlists inteligentes',
    ],
    featured: true,
  };
}

/** Maps a backend PlanApiDto into a UI SubscriptionPlan with monthly/annual pricing. */
export function mapPlanDtoToSubscriptionPlan(dto: PlanApiDto, annual: boolean): SubscriptionPlan {
  const meta = resolvePlanMetadata(dto);
  const effectiveMonthly =
    dto.monthly_price > 0 && annual
      ? Math.round(dto.monthly_price * 0.8 * 100) / 100
      : dto.monthly_price;

  return {
    planId: dto.plan_id,
    name: dto.name,
    displayName: meta.displayName,
    price: formatPriceBRL(effectiveMonthly),
    monthlyPrice: dto.monthly_price,
    maxProfiles: dto.max_profiles,
    copy: meta.copy,
    features: meta.features,
    featured: meta.featured,
  };
}

function formatRelativeAge(isoDate: string | null | undefined): {
  readonly age: string;
  readonly timestamp: number;
} {
  if (!isoDate) {
    return { age: 'agora', timestamp: Date.now() };
  }
  const parsed = Date.parse(isoDate);
  if (!Number.isFinite(parsed)) {
    return { age: 'recente', timestamp: Date.now() };
  }
  const diffMinutes = Math.max(0, Math.floor((Date.now() - parsed) / 60_000));
  if (diffMinutes < 2) return { age: 'agora', timestamp: parsed };
  if (diffMinutes < 60) return { age: `há ${diffMinutes} min`, timestamp: parsed };
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return { age: `há ${diffHours} h`, timestamp: parsed };
  const diffDays = Math.floor(diffHours / 24);
  return { age: `há ${diffDays} d`, timestamp: parsed };
}

/** Maps a backend UserApiDto into a camelCase FamilyMember domain model. */
export function mapFamilyMemberDto(dto: UserApiDto): FamilyMember {
  return {
    userId: dto.user_id,
    email: dto.email,
    displayName: dto.display_name,
    age: dto.age ?? null,
    planId: dto.plan_id,
    birthDate: dto.birth_date ?? null,
    primaryAccountId: dto.primary_account_id ?? null,
    blockedGenres: dto.blocked_genres ?? [],
    blockedArtists: dto.blocked_artists ?? [],
    isAdmin: dto.is_admin,
  };
}

/** Derives uppercase 2-character initials from a display name. */
export function computeInitials(name: string, fallback = 'RB'): string {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter((part) => part.length > 0);
  if (parts.length >= 2) {
    return `${parts[0]?.[0] ?? ''}${parts[1]?.[0] ?? ''}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase() || fallback;
}

function resolveReviewAuthor(dto: ReviewApiDto, isOwn: boolean, currentUserName?: string): string {
  if (isOwn) {
    return currentUserName || 'Você';
  }
  return dto.author_name?.trim() || `Ouvinte #${dto.user_id}`;
}

function resolveReviewCover(dto: ReviewApiDto, trackImage?: string): string | undefined {
  if (trackImage) {
    return trackImage;
  }
  if (dto.track_image || dto.track_title) {
    return resolveCoverUrl(dto.track_image, dto.track_id);
  }
  return undefined;
}

function resolveReviewTrackMetadata(dto: ReviewApiDto, track?: Song) {
  const songTitle = track ? track.title : (dto.track_title ?? undefined);
  const songArtist = track ? track.artist : (dto.track_artist ?? undefined);
  const songImage = resolveReviewCover(dto, track?.image);
  return { songTitle, songArtist, songImage };
}

function resolveReviewText(dto: ReviewApiDto): string {
  return dto.text && dto.text.trim().length > 0
    ? dto.text
    : `Avaliou com ${dto.rating}/5 estrelas.`;
}

/** Maps a ReviewApiDto into a UI CommunityReview card item. */
export function mapReviewDtoToCommunityReview(options: {
  readonly dto: ReviewApiDto;
  readonly track?: Song;
  readonly currentUserId?: number;
  readonly currentUserName?: string;
}): CommunityReview {
  const { dto, track, currentUserId, currentUserName } = options;
  const isOwn = currentUserId !== undefined && dto.user_id === currentUserId;
  const author = resolveReviewAuthor(dto, isOwn, currentUserName);
  const relative = formatRelativeAge(dto.created_at);
  const { songTitle, songArtist, songImage } = resolveReviewTrackMetadata(dto, track);

  return {
    id: dto.review_id ?? dto.track_id * 1000 + dto.user_id,
    author,
    initials: computeInitials(author),
    text: resolveReviewText(dto),
    likes: dto.likes_count,
    age: relative.age,
    date: relative.timestamp,
    userId: dto.user_id,
    trackId: dto.track_id,
    rating: dto.rating,
    ...(songTitle ? { songTitle } : {}),
    ...(songArtist ? { songArtist } : {}),
    ...(songImage ? { songImage } : {}),
  };
}

/** Maps a JamStateApiDto into the UI JamState signal model. */
export function mapJamStateDto(options: {
  readonly dto: JamStateApiDto;
  readonly trackLookup: ReadonlyMap<number, Song>;
  readonly fallbackSong: Song;
}): JamState {
  const { dto, trackLookup, fallbackSong } = options;
  const jam = dto.jam;
  const hours = Math.floor(jam.duration_minutes / 60);
  const mins = jam.duration_minutes % 60;
  const currentTrack = dto.current_track
    ? mapTrackDtoToSong(dto.current_track)
    : jam.current_track_id
      ? trackLookup.get(jam.current_track_id)
      : undefined;

  const queueItems: JamQueueTrack[] = dto.queue.map((qItem) => {
    const song = trackLookup.get(qItem.track_id) ?? {
      ...fallbackSong,
      trackId: qItem.track_id,
      title: `Faixa #${qItem.track_id}`,
    };
    return { song, votePoints: qItem.vote_points };
  });

  return {
    ...(jam.jam_id != null ? { jamId: jam.jam_id, roomId: jam.jam_id } : {}),
    hostUserId: jam.host_user_id,
    active: jam.is_active,
    code: jam.room_code,
    roomName: jam.room_name,
    votes: dto.skip_votes,
    voteThreshold: jam.skip_votes_threshold,
    durationHours: hours,
    durationMinutes: mins,
    accumulatedMinutes: Math.round(jam.accumulated_duration_seconds / 60),
    superlikesCount: jam.superlikes_used,
    superlikesLimit: jam.max_superlikes,
    deckSource:
      jam.deck_source === 'curtidas' || jam.deck_source === 'playlist' ? jam.deck_source : 'livre',
    ...(jam.source_playlist_id != null ? { sourcePlaylistId: jam.source_playlist_id } : {}),
    ...(currentTrack ? { currentTrack } : {}),
    queueItems,
  };
}

const MONTH_LABELS: readonly string[] = [
  'Jan',
  'Fev',
  'Mar',
  'Abr',
  'Mai',
  'Jun',
  'Jul',
  'Ago',
  'Set',
  'Out',
  'Nov',
  'Dez',
];

const SOURCE_LABELS: Record<string, string> = {
  discovery: 'Descoberta',
  playlist: 'Playlists',
  search: 'Busca',
  profile: 'Perfil',
  jam: 'Jams',
  unknown: 'Outros',
};

function formatArtistInteractionSummary(likes: number, superlikes: number): string {
  const parts: string[] = [];
  if (likes > 0) parts.push(likes === 1 ? '1 curtida' : `${likes} curtidas`);
  if (superlikes > 0) parts.push(superlikes === 1 ? '1 amada' : `${superlikes} amadas`);
  return parts.length > 0 ? parts.join(' · ') : '0 curtidas';
}

function mapTopGenres(rawGenres: readonly GenreStatApiDto[]): readonly RankedGenre[] {
  const totalPositiveSum = rawGenres.reduce(
    (sum, item) => sum + Math.max(0, item.total_positive),
    0,
  );
  return rawGenres.map((item, idx) => ({
    genre: formatGenreLabel(item.genre),
    likes: item.likes,
    superlikes: item.superlikes,
    dislikes: item.dislikes,
    totalPositive: item.total_positive,
    percentage:
      totalPositiveSum > 0
        ? Math.round((Math.max(0, item.total_positive) / totalPositiveSum) * 100)
        : 0,
    rank: String(idx + 1).padStart(2, '0'),
  }));
}

function mapTopArtists(
  rawArtists: readonly ArtistStatApiDto[],
  knownSongs: readonly Song[],
): readonly RankedArtist[] {
  return rawArtists
    .filter((item) => item.total_positive > 0)
    .map((item, idx) => {
      const artistLower = item.artist.trim().toLowerCase();
      const matchedSong = knownSongs.find(
        (candidate) => candidate.artist.trim().toLowerCase() === artistLower,
      );
      const artistImage =
        item.cover_url && !isPlaceholderMediaUrl(item.cover_url)
          ? item.cover_url
          : (matchedSong?.image ?? resolveCoverUrl(null, idx + 1));
      const song: Song = matchedSong
        ? { ...matchedSong, image: artistImage }
        : {
            title: item.artist,
            artist: item.artist,
            genre: '',
            time: '',
            image: artistImage,
            album: '',
            year: '',
            match: 0,
          };
      return {
        song,
        rank: String(idx + 1),
        likes: item.likes,
        superlikes: item.superlikes,
        totalPositive: item.total_positive,
        summary: formatArtistInteractionSummary(item.likes, item.superlikes),
      };
    });
}

function scaleBarSegment(count: number, maxTotal: number, plotHeight: number): number {
  if (count <= 0 || maxTotal <= 0) return 0;
  return Math.min(plotHeight, Math.max(2, Math.round((count / maxTotal) * plotHeight)));
}

function mapMonthlyActivityBars(rawMonths: readonly MonthlyInteractionStatApiDto[]): {
  readonly bars: readonly MonthlyActivityBar[];
  readonly maxTotal: number;
} {
  const plotHeight = 128;
  const baselineY = 150;
  const byMonth = new Map<number, MonthlyInteractionStatApiDto>();
  for (const item of rawMonths) {
    byMonth.set(item.month, item);
  }
  const totals = MONTH_LABELS.map((_, idx) => byMonth.get(idx + 1)?.total ?? 0);
  const maxTotal = Math.max(0, ...totals);

  const bars: readonly MonthlyActivityBar[] = MONTH_LABELS.map((label, idx) => {
    const month = idx + 1;
    const stats = byMonth.get(month);
    const likes = stats?.likes ?? 0;
    const superlikes = stats?.superlikes ?? 0;
    const dislikes = stats?.dislikes ?? 0;
    const total = stats?.total ?? 0;
    const x = 18 + idx * 48;
    const dislikesHeight = scaleBarSegment(dislikes, maxTotal, plotHeight);
    const likesHeight = scaleBarSegment(likes, maxTotal, plotHeight);
    const superlikesHeight = scaleBarSegment(superlikes, maxTotal, plotHeight);
    const dislikesY = baselineY - dislikesHeight;
    const likesY = dislikesY - likesHeight;
    const superlikesY = likesY - superlikesHeight;
    return {
      month,
      label,
      likes,
      superlikes,
      dislikes,
      total,
      x,
      dislikesY,
      dislikesHeight,
      likesY,
      likesHeight,
      superlikesY,
      superlikesHeight,
      totalLabelY: Math.max(14, superlikesY - 6),
      tooltip: `${label}: ${total} interações (${likes} curtidas, ${superlikes} amadas, ${dislikes} rejeitadas)`,
    };
  });

  return { bars, maxTotal };
}

function mapReleaseEras(rawYears: readonly ReleaseYearStatApiDto[]): readonly ReleaseEraPoint[] {
  const decadeMap = new Map<number, { likes: number; superlikes: number; totalPositive: number }>();
  for (const item of rawYears) {
    const decade = Math.floor(item.release_year / 10) * 10;
    const existing = decadeMap.get(decade) ?? { likes: 0, superlikes: 0, totalPositive: 0 };
    decadeMap.set(decade, {
      likes: existing.likes + item.likes,
      superlikes: existing.superlikes + item.superlikes,
      totalPositive: existing.totalPositive + item.total_positive,
    });
  }
  const sorted = [...decadeMap.entries()].sort((a, b) => a[0] - b[0]);
  const totalPositiveSum = sorted.reduce(
    (sum, [, bucket]) => sum + Math.max(0, bucket.totalPositive),
    0,
  );
  return sorted.map(([decade, bucket]) => ({
    decade,
    label: `${decade}s`,
    totalPositive: bucket.totalPositive,
    likes: bucket.likes,
    superlikes: bucket.superlikes,
    percentage:
      totalPositiveSum > 0
        ? Math.round((Math.max(0, bucket.totalPositive) / totalPositiveSum) * 100)
        : 0,
  }));
}

function mapInteractionSources(
  rawSources: readonly SourceStatApiDto[],
): readonly InteractionSourcePoint[] {
  const totalSum = rawSources.reduce((sum, item) => sum + Math.max(0, item.total), 0);
  return rawSources.map((item) => ({
    source: item.source,
    label: SOURCE_LABELS[item.source.toLowerCase()] ?? item.source,
    total: item.total,
    likes: item.likes,
    superlikes: item.superlikes,
    dislikes: item.dislikes,
    percentage: totalSum > 0 ? Math.round((Math.max(0, item.total) / totalSum) * 100) : 0,
  }));
}

function resolvePositiveRatePercent(
  dto: AnnualStatsApiDto,
  totalPositive: number,
  totalInteractions: number,
): number {
  if (dto.positive_rate !== undefined) {
    return Math.round(Math.max(0, Math.min(1, dto.positive_rate)) * 100);
  }
  if (totalInteractions > 0) {
    return Math.round((totalPositive / totalInteractions) * 100);
  }
  return 0;
}

interface NormalizedDashboardTotals {
  readonly totalLikes: number;
  readonly totalSuperlikes: number;
  readonly totalDislikes: number;
  readonly totalInteractions: number;
  readonly positiveRatePercent: number;
  readonly totalReviews: number;
  readonly averageRating: number;
  readonly totalPlaylists: number;
  readonly totalJamsParticipated: number;
}

function normalizeDashboardTotals(dto: AnnualStatsApiDto): NormalizedDashboardTotals {
  const totalLikes = dto.total_likes;
  const totalSuperlikes = dto.total_superlikes ?? 0;
  const totalDislikes = dto.total_dislikes ?? 0;
  const totalInteractions = dto.total_interactions ?? totalLikes + totalSuperlikes + totalDislikes;
  const positiveRatePercent = resolvePositiveRatePercent(
    dto,
    totalLikes + totalSuperlikes,
    totalInteractions,
  );
  return {
    totalLikes,
    totalSuperlikes,
    totalDislikes,
    totalInteractions,
    positiveRatePercent,
    totalReviews: dto.total_reviews ?? 0,
    averageRating: dto.average_rating ?? 0,
    totalPlaylists: dto.total_playlists ?? 0,
    totalJamsParticipated: dto.total_jams_participated ?? 0,
  };
}

function buildDashboardMetrics(totals: NormalizedDashboardTotals): readonly MetricItem[] {
  const jamWord = totals.totalJamsParticipated === 1 ? 'jam participada' : 'jams participadas';
  const reviewDetail =
    totals.totalReviews > 0
      ? `Média ${totals.averageRating.toFixed(1)} de 5`
      : 'Nenhuma avaliação ainda';

  return [
    {
      value: String(totals.totalInteractions),
      label: 'Interações totais',
      detail: `${totals.totalLikes} curtidas · ${totals.totalSuperlikes} amadas`,
      icon: 'heart',
    },
    {
      value: `${totals.positiveRatePercent}%`,
      label: 'Taxa de aprovação',
      detail: `${totals.totalDislikes} rejeitadas no período`,
      icon: 'sparkles',
    },
    {
      value: String(totals.totalPlaylists),
      label: 'Playlists criadas',
      detail: `${totals.totalJamsParticipated} ${jamWord}`,
      icon: 'music',
    },
    {
      value: String(totals.totalReviews),
      label: 'Avaliações',
      detail: reviewDetail,
      icon: 'star',
    },
  ];
}

/** Maps AnnualStatsApiDto into Dashboard metrics, ranked genres, artists, and chart series. */
export function mapAnnualStatsToDashboard(
  dto: AnnualStatsApiDto,
  knownSongs: readonly Song[],
): DashboardViewData {
  const totals = normalizeDashboardTotals(dto);
  const monthly = mapMonthlyActivityBars(dto.by_month ?? []);

  return {
    selectedYear: dto.year ?? null,
    availableYears: dto.available_years ?? [],
    totalInteractions: totals.totalInteractions,
    positiveRatePercent: totals.positiveRatePercent,
    totalLikes: totals.totalLikes,
    totalSuperlikes: totals.totalSuperlikes,
    totalDislikes: totals.totalDislikes,
    metrics: buildDashboardMetrics(totals),
    genres: mapTopGenres(dto.top_genres),
    artists: mapTopArtists(dto.top_artists, knownSongs),
    monthlyBars: monthly.bars,
    maxMonthlyTotal: monthly.maxTotal,
    releaseEras: mapReleaseEras(dto.by_release_year ?? []),
    sources: mapInteractionSources(dto.by_source ?? []),
    totalReviews: totals.totalReviews,
    averageRating: totals.averageRating,
    totalPlaylists: totals.totalPlaylists,
    totalJamsParticipated: totals.totalJamsParticipated,
  };
}
