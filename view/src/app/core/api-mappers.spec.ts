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
    });

    expect(playlist.playlistId).toBe(12);
    expect(playlist.count).toBe(1);
    expect(playlist.duration).toBe('3 min');
    expect(playlist.isExported).toBe(true);
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
          deck_source: 'livre',
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

    const dashboard = mapAnnualStatsToDashboard(
      {
        user_id: 9,
        estimated_listening_hours: 12.4,
        total_likes: 48,
        top_genres: ['Rock', 'Pop'],
        top_artists: ['Queen'],
      },
      [fallbackSong],
    );
    expect(dashboard.hoursLabel).toBe('12.4h');
    expect(dashboard.genres.length).toBe(2);
    expect(dashboard.artists[0]?.song.artist).toBe('Queen');
  });
});
