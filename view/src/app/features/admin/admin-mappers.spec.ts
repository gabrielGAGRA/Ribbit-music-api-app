import type {
  AdminTrackAccessEntry as AdminTrackAccessEntryApiDto,
  AdminUserPlanSummary as AdminUserPlanSummaryApiDto,
  AudienceReportApiDto,
  ExecutiveDashboardApiDto,
  PlanApiDto,
  PlatformCostSettingsApiDto,
  ReviewApiDto,
  UserApiDto,
} from '@ribbit/shared-types';
import { describe, expect, it } from 'vitest';
import {
  mapAdminAdministratorDto,
  mapAdminModerationReviewDto,
  mapAdminPlanDto,
  mapAdminTrackAccessEntryDto,
  mapAdminTrackDto,
  mapAdminUserPlanSummaryDto,
  mapAudienceReportDto,
  mapExecutiveDashboardDto,
  mapPlatformCostSettingsDto,
  type AdminTrackApiDto,
  type AdminTrackItem,
  type AdminUserPlanSummary,
} from './admin-mappers';

describe('admin-mappers', () => {
  it('maps plan DTO into AdminPlanItem', () => {
    const dto: PlanApiDto = {
      plan_id: 3,
      name: 'Família',
      monthly_price: 27.9,
      max_profiles: 4,
    };

    expect(mapAdminPlanDto(dto)).toEqual({
      planId: 3,
      name: 'Família',
      monthlyPrice: 27.9,
      maxProfiles: 4,
    });
  });

  it('maps user plan summary and administrator DTOs', () => {
    const summaryDto: AdminUserPlanSummaryApiDto = {
      user_id: 10,
      email: 'alice@ribbit.app',
      display_name: 'Alice',
      age: 28,
      plan_name: 'Individual',
      is_admin: false,
    };
    const adminDto: UserApiDto = {
      user_id: 1,
      email: 'admin@ribbit.app',
      display_name: 'Admin',
      plan_id: 3,
      is_admin: true,
    };

    expect(mapAdminUserPlanSummaryDto(summaryDto)).toEqual({
      userId: 10,
      email: 'alice@ribbit.app',
      displayName: 'Alice',
      age: 28,
      planName: 'Individual',
      isAdmin: false,
    });

    expect(mapAdminAdministratorDto(adminDto)).toEqual({
      userId: 1,
      email: 'admin@ribbit.app',
      displayName: 'Admin',
      age: null,
      isAdmin: true,
    });
  });

  it('maps admin track DTO with optional metrics and defaults', () => {
    const dto: AdminTrackApiDto = {
      track_id: 42,
      title: 'Midnight',
      artist: 'Luna',
      genre: 'Indie',
      duration_seconds: 215,
      explicit: true,
      is_deleted: false,
      likes_count: 12,
      dislikes_count: 2,
      superlikes_count: 4,
      average_rating: 4.5,
      review_count: 8,
    };

    expect(mapAdminTrackDto(dto)).toEqual({
      trackId: 42,
      title: 'Midnight',
      artist: 'Luna',
      album: null,
      genre: 'Indie',
      durationSeconds: 215,
      releaseYear: null,
      explicit: true,
      isDeleted: false,
      likesCount: 12,
      dislikesCount: 2,
      superlikesCount: 4,
      averageRating: 4.5,
      reviewCount: 8,
    });
  });

  it('maps executive dashboard DTO with grossRevenue fallback from revenue_by_plan', () => {
    const dto: ExecutiveDashboardApiDto = {
      total_users: 100,
      estimated_net_revenue: 850.5,
      users_by_plan: { Free: 60, Individual: 40 },
      revenue_by_plan: { Free: 0, Individual: 596 },
    };

    const mapped = mapExecutiveDashboardDto(dto);
    expect(mapped.grossRevenue).toBe(596);
    expect(mapped.contentCostPerTrack).toBe(0.04);
    expect(mapped.infrastructureFixedCost).toBe(10);
    expect(mapped.infrastructureCostPerUser).toBe(0.5);
    expect(mapped.totalCosts).toBe(0);
  });

  it('maps audience report, platform cost settings, and track access entry DTOs', () => {
    const audienceDto: AudienceReportApiDto = {
      total_users: 50,
      total_tracks: 120,
      active_tracks: 115,
      blocked_genres: { Rock: 5 },
      total_accesses: 300,
      accesses_by_track: [
        {
          track_id: 7,
          title: 'Pulse',
          artist: 'Nova',
          is_deleted: false,
          access_count: 45,
        },
      ],
      accesses_by_genre: [{ genre: 'Pop', access_count: 120 }],
    };

    expect(mapAudienceReportDto(audienceDto)).toEqual({
      totalUsers: 50,
      totalTracks: 120,
      activeTracks: 115,
      blockedGenres: { Rock: 5 },
      totalAccesses: 300,
      accessesByTrack: [
        {
          trackId: 7,
          title: 'Pulse',
          artist: 'Nova',
          isDeleted: false,
          accessCount: 45,
        },
      ],
      accessesByGenre: [{ genre: 'Pop', accessCount: 120 }],
    });

    const costDto: PlatformCostSettingsApiDto = {
      content_cost_per_track: 0.08,
      infrastructure_fixed_cost: 25,
      infrastructure_cost_per_user: 0.75,
      updated_at: '2026-01-01T00:00:00Z',
    };
    expect(mapPlatformCostSettingsDto(costDto)).toEqual({
      contentCostPerTrack: 0.08,
      infrastructureFixedCost: 25,
      infrastructureCostPerUser: 0.75,
      updatedAt: '2026-01-01T00:00:00Z',
    });

    const accessDto: AdminTrackAccessEntryApiDto = {
      access_id: 99,
      user_id: 3,
      user_display_name: 'Bob',
      user_email: 'bob@ribbit.app',
      track_id: 7,
      track_title: 'Pulse',
      track_artist: 'Nova',
      track_genre: 'Pop',
      track_is_deleted: false,
      source: 'play',
      accessed_at: '2026-01-02T12:00:00Z',
    };
    expect(mapAdminTrackAccessEntryDto(accessDto)).toEqual({
      accessId: 99,
      userId: 3,
      userDisplayName: 'Bob',
      userEmail: 'bob@ribbit.app',
      trackId: 7,
      trackTitle: 'Pulse',
      trackArtist: 'Nova',
      trackGenre: 'Pop',
      trackIsDeleted: false,
      source: 'play',
      accessedAt: '2026-01-02T12:00:00Z',
    });
  });

  it('maps moderation review DTO with fallbacks from userById and trackById maps', () => {
    const userMap = new Map<number, AdminUserPlanSummary>([
      [
        5,
        {
          userId: 5,
          email: 'carol@ribbit.app',
          displayName: 'Carol',
          age: 22,
          planName: 'Free',
          isAdmin: false,
        },
      ],
    ]);
    const trackMap = new Map<number, AdminTrackItem>([
      [
        11,
        {
          trackId: 11,
          title: 'Echoes',
          artist: 'Waves',
          album: null,
          genre: 'Ambient',
          durationSeconds: 180,
          releaseYear: 2023,
          explicit: false,
          isDeleted: false,
          likesCount: 0,
          dislikesCount: 0,
          superlikesCount: 0,
          averageRating: null,
          reviewCount: 0,
        },
      ],
    ]);

    const reviewFromMaps: ReviewApiDto = {
      user_id: 5,
      track_id: 11,
      rating: 5,
      text: 'Great track',
      likes_count: 3,
      is_deleted: false,
    };
    expect(mapAdminModerationReviewDto(reviewFromMaps, 0, userMap, trackMap)).toEqual({
      reviewId: 1,
      userId: 5,
      authorName: 'Carol',
      trackId: 11,
      trackTitle: 'Echoes',
      trackArtist: 'Waves',
      rating: 5,
      text: 'Great track',
      likesCount: 3,
      createdAt: '',
      isDeleted: false,
    });

    const reviewFallback: ReviewApiDto = {
      review_id: 77,
      user_id: 999,
      track_id: 888,
      rating: 2,
      likes_count: 0,
      is_deleted: true,
    };
    expect(mapAdminModerationReviewDto(reviewFallback, 4, userMap, trackMap)).toEqual({
      reviewId: 77,
      userId: 999,
      authorName: 'Usuário #999',
      trackId: 888,
      trackTitle: 'Faixa #888',
      trackArtist: 'Artista do Catálogo',
      rating: 2,
      text: '',
      likesCount: 0,
      createdAt: '',
      isDeleted: true,
    });
  });
});
