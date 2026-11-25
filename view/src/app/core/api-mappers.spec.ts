import { describe, expect, it } from 'vitest';
import {
  formatDurationSeconds,
  formatTotalMinutes,
  mapAnnualStatsToDashboard,
  mapApiActionToDecision,
  mapDecisionToApiAction,
  mapJamStateDto,
  mapPlanDtoToSubscriptionPlan,
  mapPlaylistDtoToPlaylist,
  mapReviewDtoToCommunityReview,
  mapTrackDtoToSong,
  resolveCoverUrl,
  resolvePreviewUrl,
} from './api-mappers';

describe('api-mappers', () => {
  it('formats track seconds and playlist minutes cleanly', () => {
    expect(formatDurationSeconds(233)).toBe('3:53');
    expect(formatDurationSeconds(0)).toBe('0:00');
    expect(formatTotalMinutes(1080)).toBe('18 min');
    expect(formatTotalMinutes(0)).toBe('0 min');
  });

  it('replaces example.com placeholder cover and preview URLs safely', () => {
    const cover = resolveCoverUrl('https://example.com/bohemian.jpg', 1);
    expect(cover).toContain('unsplash.com');
    expect(resolveCoverUrl('https://cdn.ribbit.app/cover.jpg', 1)).toBe(
      'https://cdn.ribbit.app/cover.jpg',
    );

    expect(resolvePreviewUrl('https://example.com/preview.mp3')).toBeUndefined();
    expect(resolvePreviewUrl('https://audio.itunes.apple.com/preview.m4a')).toBe(
      'https://audio.itunes.apple.com/preview.m4a',
    );
  });

  it('maps TrackApiDto and PlaylistApiDto into Song and Playlist view models', () => {
    const song = mapTrackDtoToSong({
      track_id: 7,
      title: 'Blinding Lights',
      artist: 'The Weeknd',
      duration_seconds: 200,
      genre: 'Pop',
      album: 'After Hours',
      release_year: 2020,
      cover_url: 'https://example.com/blinding.jpg',
      itunes_preview_url: 'https://audio.itunes.apple.com/blinding.m4a',
      explicit: false,
      is_deleted: false,
    });

    expect(song.trackId).toBe(7);
    expect(song.time).toBe('3:20');
    expect(song.year).toBe('2020');
    expect(song.previewUrl).toBe('https://audio.itunes.apple.com/blinding.m4a');

    const playlist = mapPlaylistDtoToPlaylist({
      playlist_id: 12,
      user_id: 1,
      name: 'Noite Neon',
      is_exported: true,
      tracks: [
        {
          track_id: 7,
          title: 'Blinding Lights',
          artist: 'The Weeknd',
          duration_seconds: 200,
          genre: 'Pop',
          explicit: false,
          is_deleted: false,
        },
      ],
      total_duration_seconds: 200,
      cover_image_url: 'https://example.com/cover.png',
      max_duration_seconds: 3600,
      deck_filters: '{"genre":"Pop"}',
      source_playlist_id: 3,
    });

    expect(playlist.playlistId).toBe(12);
    expect(playlist.count).toBe(1);
    expect(playlist.duration).toBe('3 min');
    expect(playlist.totalDurationSeconds).toBe(200);
    expect(playlist.isExported).toBe(true);
    expect(playlist.coverImageUrl).toBe('https://example.com/cover.png');
    expect(playlist.maxDurationSeconds).toBe(3600);
    expect(playlist.deckFilters).toBe('{"genre":"Pop"}');
    expect(playlist.sourcePlaylistId).toBe(3);

    const emptyDurationPlaylist = mapPlaylistDtoToPlaylist({
      playlist_id: 13,
      user_id: 1,
      name: 'Nova com Limite',
      is_exported: false,
      tracks: [],
      total_duration_seconds: 0,
      max_duration_seconds: 2700,
      deck_filters: '{"genre":[],"reference_source":"curtidas"}',
    });
    expect(emptyDurationPlaylist.duration).toBe('0 min');
    expect(emptyDurationPlaylist.totalDurationSeconds).toBe(0);
    expect(emptyDurationPlaylist.maxDurationSeconds).toBe(2700);
    expect(emptyDurationPlaylist.referenceSource).toBe('curtidas');
  });

  it('translates swipe actions between UI and backend contracts', () => {
    expect(mapDecisionToApiAction('like')).toBe('like');
    expect(mapDecisionToApiAction('love')).toBe('superlike');
    expect(mapDecisionToApiAction('reject')).toBe('dislike');

    expect(mapApiActionToDecision('superlike')).toBe('love');
    expect(mapApiActionToDecision('dislike')).toBe('reject');
    expect(mapApiActionToDecision('like')).toBe('like');
  });

  it('maps subscription plans, reviews, jam state, and annual stats', () => {
    const annualPlan = mapPlanDtoToSubscriptionPlan(
      { plan_id: 2, name: 'Individual', monthly_price: 14.9, max_profiles: 1 },
      true,
    );
    expect(annualPlan.planId).toBe(2);
    expect(annualPlan.featured).toBe(true);
    expect(annualPlan.price).toBe('R$ 11,92');

    const review = mapReviewDtoToCommunityReview({
      dto: {
        review_id: 4,
        user_id: 9,
        track_id: 7,
        rating: 5,
        text: 'Sintetizador incrível!',
        likes_count: 3,
        is_deleted: false,
      },
      currentUserId: 9,
      currentUserName: 'Carolina Britto',
    });
    expect(review.author).toBe('Carolina Britto');
    expect(review.initials).toBe('CB');

    const otherUserReview = mapReviewDtoToCommunityReview({
      dto: {
        review_id: 10,
        user_id: 42,
        track_id: 100,
        rating: 4,
        text: 'Produção fantástica!',
        likes_count: 7,
        is_deleted: false,
        author_name: 'Marcos Silva',
        track_title: 'Música Boa',
        track_artist: 'Cantor Famoso',
        track_image: 'https://i.scdn.co/image/cover123.jpg',
      },
      currentUserId: 9,
      currentUserName: 'Carolina Britto',
    });
    expect(otherUserReview.author).toBe('Marcos Silva');
    expect(otherUserReview.initials).toBe('MS');
    expect(otherUserReview.songTitle).toBe('Música Boa');
    expect(otherUserReview.songArtist).toBe('Cantor Famoso');
    expect(otherUserReview.songImage).toBe('https://i.scdn.co/image/cover123.jpg');

    const fallbackSong = mapTrackDtoToSong({
      track_id: 1,
      title: 'Bohemian Rhapsody',
      artist: 'Queen',
      duration_seconds: 354,
      genre: 'Rock',
      explicit: false,
      is_deleted: false,
    });

    const jamState = mapJamStateDto({
      dto: {
        jam: {
          jam_id: 5,
          host_user_id: 9,
          room_name: 'Sala Indie',
          room_code: '123456',
          is_active: true,
          duration_minutes: 95,
          max_superlikes: 5,
          superlikes_used: 2,
          skip_votes_threshold: 3,
          accumulated_duration_seconds: 600,
          deck_source: 'playlist',
          source_playlist_id: 12,
        },
        current_track: null,
        queue: [{ jam_id: 5, track_id: 1, vote_points: 4 }],
        skip_votes: 1,
      },
      trackLookup: new Map([[1, fallbackSong]]),
      fallbackSong,
    });
    expect(jamState.jamId).toBe(5);
    expect(jamState.durationHours).toBe(1);
    expect(jamState.durationMinutes).toBe(35);
    expect(jamState.queueItems?.[0]?.votePoints).toBe(4);
    expect(jamState.deckSource).toBe('playlist');
    expect(jamState.sourcePlaylistId).toBe(12);

    const dashboard = mapAnnualStatsToDashboard(
      {
        user_id: 9,
        year: null,
        available_years: [2026],
        total_interactions: 10,
        total_likes: 5,
        total_superlikes: 2,
        total_dislikes: 3,
        positive_rate: 0.7,
        top_genres: [
          { genre: 'hip-hop', likes: 3, superlikes: 1, dislikes: 0, total_positive: 4 },
          { genre: 'rock', likes: 1, superlikes: 0, dislikes: 1, total_positive: 1 },
        ],
        top_artists: [
          {
            artist: 'Queen',
            likes: 3,
            superlikes: 1,
            dislikes: 0,
            total_positive: 4,
            cover_url: 'https://is1-ssl.mzstatic.com/first-liked-cover.jpg',
          },
          {
            artist: 'Zero Likes Band',
            likes: 0,
            superlikes: 0,
            dislikes: 3,
            total_positive: 0,
            cover_url: null,
          },
        ],
        by_month: [{ month: 11, likes: 5, superlikes: 2, dislikes: 3, total: 10 }],
        by_release_year: [
          { release_year: 2018, likes: 3, superlikes: 0, total_positive: 3 },
          { release_year: 2021, likes: 1, superlikes: 1, total_positive: 2 },
        ],
        by_source: [
          { source: 'discovery', likes: 4, superlikes: 1, dislikes: 3, total: 8 },
          { source: 'playlist', likes: 1, superlikes: 1, dislikes: 0, total: 2 },
        ],
        total_reviews: 2,
        average_rating: 4.5,
        total_playlists: 3,
        total_jams_participated: 1,
      },
      [fallbackSong],
    );
    expect(dashboard.totalInteractions).toBe(10);
    expect(dashboard.positiveRatePercent).toBe(70);
    expect(dashboard.availableYears).toEqual([2026]);
    expect(dashboard.genres).toEqual([
      {
        genre: 'Hip Hop',
        likes: 3,
        superlikes: 1,
        dislikes: 0,
        totalPositive: 4,
        percentage: 80,
        rank: '01',
      },
      {
        genre: 'Rock',
        likes: 1,
        superlikes: 0,
        dislikes: 1,
        totalPositive: 1,
        percentage: 20,
        rank: '02',
      },
    ]);
    expect(dashboard.artists).toHaveLength(1);
    expect(dashboard.artists[0]?.song.artist).toBe('Queen');
    expect(dashboard.artists[0]?.song.image).toBe(
      'https://is1-ssl.mzstatic.com/first-liked-cover.jpg',
    );
    expect(dashboard.artists[0]?.summary).toBe('3 curtidas · 1 amada');
    expect(dashboard.monthlyBars).toHaveLength(12);
    expect(dashboard.maxMonthlyTotal).toBe(10);
    expect(dashboard.monthlyBars[10]?.total).toBe(10);
    expect(dashboard.monthlyBars[10]?.likesHeight).toBeGreaterThan(0);
    expect(dashboard.releaseEras.map((era) => ({ label: era.label, pct: era.percentage }))).toEqual(
      [
        { label: '2010s', pct: 60 },
        { label: '2020s', pct: 40 },
      ],
    );
    expect(dashboard.sources.map((src) => ({ label: src.label, pct: src.percentage }))).toEqual([
      { label: 'Descoberta', pct: 80 },
      { label: 'Playlists', pct: 20 },
    ]);
  });

  it('marks isDeleted only when TrackApiDto.is_deleted is true', () => {
    const active = mapTrackDtoToSong({
      track_id: 1,
      title: 'Active',
      artist: 'Artist',
      duration_seconds: 180,
      genre: 'Pop',
      explicit: false,
      is_deleted: false,
    });
    const removed = mapTrackDtoToSong({
      track_id: 2,
      title: 'Removed',
      artist: 'Artist',
      duration_seconds: 180,
      genre: 'Pop',
      explicit: false,
      is_deleted: true,
    });

    expect(active.isDeleted).toBeUndefined();
    expect(removed.isDeleted).toBe(true);
  });
});
