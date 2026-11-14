import type {
  AnnualStatsApiDto,
  CommunityReview,
  DecisionKind,
  JamQueueTrack,
  JamState,
  JamStateApiDto,
  MetricItem,
  PlanApiDto,
  Playlist,
  PlaylistApiDto,
  RankedArtist,
  RankedGenre,
  ReviewApiDto,
  Song,
  SubscriptionPlan,
  SwipeApiAction,
  TrackApiDto,
} from '@ribbit/shared-types';

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

/** Formats total seconds into human-readable minutes label. */
export function formatTotalMinutes(totalSeconds: number): string {
  const safe = Number.isFinite(totalSeconds) && totalSeconds > 0 ? totalSeconds : 0;
  const mins = Math.max(1, Math.round(safe / 60));
  return `${mins} min`;
}

/** Resolves a valid cover image URL, substituting seed placeholders deterministically. */
export function resolveCoverUrl(rawUrl: string | null | undefined, seed: number): string {
  if (!isPlaceholderMediaUrl(rawUrl) && rawUrl) {
    return rawUrl;
  }
  const idx = Math.abs(seed) % FALLBACK_COVERS.length;
  return FALLBACK_COVERS[idx] ?? FALLBACK_COVERS[0]!;
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
    genre: dto.genre || 'Indie',
    time: formatDurationSeconds(dto.duration_seconds),
    image: resolveCoverUrl(dto.cover_url, dto.track_id),
    album: dto.album ?? 'Single',
    year: dto.release_year ? String(dto.release_year) : '2024',
    match: matchScore,
    ...(previewUrl ? { previewUrl } : {}),
    ...(dto.country ? { country: dto.country } : {}),
    explicit: dto.explicit,
    durationSeconds: dto.duration_seconds,
  };
}

/** Maps a backend PlaylistApiDto into the UI Playlist view model. */
export function mapPlaylistDtoToPlaylist(dto: PlaylistApiDto): Playlist {
  const songs = dto.tracks.map((track) => mapTrackDtoToSong(track));
  const computedSeconds =
    dto.total_duration_seconds > 0
      ? dto.total_duration_seconds
      : dto.tracks.reduce((acc, item) => acc + item.duration_seconds, 0);
  const durationLabel =
    computedSeconds > 0
      ? formatTotalMinutes(computedSeconds)
      : dto.max_duration_seconds
        ? formatTotalMinutes(dto.max_duration_seconds)
        : '0 min';

  return {
    id: String(dto.playlist_id),
    playlistId: dto.playlist_id,
    name: dto.name,
    count: songs.length,
    duration: durationLabel,
    ...(dto.description ? { description: dto.description } : {}),
    isExported: dto.is_exported,
    ...(dto.spotify_playlist_id ? { spotifyPlaylistId: dto.spotify_playlist_id } : {}),
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

function computeInitials(name: string): string {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter((part) => part.length > 0);
  if (parts.length >= 2) {
    return `${parts[0]![0] ?? ''}${parts[1]![0] ?? ''}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase() || 'RB';
}

function resolveReviewAuthor(
  dto: ReviewApiDto,
  isOwn: boolean,
  currentUserName?: string,
): string {
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
    ...(jam.jam_id != null ? { jamId: jam.jam_id } : {}),
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
    ...(currentTrack ? { currentTrack } : {}),
    queueItems,
  };
}

/** Maps AnnualStatsApiDto into Dashboard metrics, ranked genres, and ranked artists. */
export function mapAnnualStatsToDashboard(
  dto: AnnualStatsApiDto,
  knownSongs: readonly Song[],
): {
  readonly hoursLabel: string;
  readonly metrics: readonly MetricItem[];
  readonly genres: readonly RankedGenre[];
  readonly artists: readonly RankedArtist[];
} {
  const hoursRounded = Math.max(0, Math.round(dto.estimated_listening_hours * 10) / 10);
  const hoursLabel = `${hoursRounded}h`;
  const metrics: readonly MetricItem[] = [
    {
      value: String(dto.total_likes),
      label: 'Músicas curtidas',
      detail: 'Interações positivas no seu histórico',
      icon: 'heart',
    },
    {
      value: `${hoursRounded}h`,
      label: 'Tempo estimado',
      detail: 'Calculado sobre suas descobertas',
      icon: 'headphones',
    },
    {
      value: String(dto.top_genres.length),
      label: 'Gêneros em alta',
      detail: dto.top_genres[0] ? `Liderado por ${dto.top_genres[0]}` : 'Continue deslizando',
      icon: 'sparkles',
    },
    {
      value: String(dto.top_artists.length),
      label: 'Artistas favoritos',
      detail: dto.top_artists[0] ? `Destaque: ${dto.top_artists[0]}` : 'Explore novos sons',
      icon: 'music',
    },
  ];

  const weights: readonly number[] = [52, 31, 17];
  const genres: readonly RankedGenre[] = dto.top_genres.map((genre, idx) => ({
    genre,
    percentage: weights[idx] ?? 15,
    rank: `0${idx + 1}`,
  }));

  const artists: readonly RankedArtist[] = dto.top_artists.map((artistName, idx) => {
    const matchedSong = knownSongs.find(
      (item) => item.artist.toLowerCase() === artistName.toLowerCase(),
    );
    const song: Song = matchedSong ?? {
      title: artistName,
      artist: artistName,
      genre: dto.top_genres[idx] ?? 'Descoberta',
      time: '3:30',
      image: resolveCoverUrl(null, idx + 1),
      album: 'Ribbit Radar',
      year: '2026',
      match: 95 - idx * 3,
    };
    const estMinutes = Math.max(15, Math.round((dto.total_likes * 3.5) / (idx + 1.5)));
    return {
      song,
      rank: String(idx + 1),
      time: `${estMinutes} min`,
    };
  });

  return { hoursLabel, metrics, genres, artists };
}
