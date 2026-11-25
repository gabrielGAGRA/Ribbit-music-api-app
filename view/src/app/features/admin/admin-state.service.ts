import { HttpClient, HttpParams } from '@angular/common/http';
import type { OnDestroy } from '@angular/core';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { Observable, Subscription } from 'rxjs';
import { forkJoin, throwError } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';
import { AdminDomainError } from './admin-domain-error';
import type {
  ActionSuccessApiDto,
  AdminTrackAccessEntry as AdminTrackAccessEntryApiDto,
  AdminUserPlanSummary as AdminUserPlanSummaryApiDto,
  AudienceReportApiDto,
  AuthApiResponse,
  BlockedGenreEntry,
  CompactCatalogApiResponse,
  ExecutiveDashboardApiDto,
  PlanApiDto,
  PlanBreakdownEntry,
  PlatformCostSettingsApiDto,
  RegisterAdminApiRequest,
  ReviewApiDto,
  SyncCatalogVersionApiResponse,
  TrackBlockApiResponse,
  TrackExplicitApiResponse,
  TrackGenreApiResponse,
  UpdateAdminPlanPayload,
  UpdatePlatformCostsPayload,
  UserApiDto,
} from '@ribbit/shared-types';
import { toApiError } from '../../core/api-error';
import { AuthSessionNotifier } from '../../core/auth-session.notifier';
import {
  clearAdminAuthToken,
  createAdminHttpContext,
  readAdminAuthToken,
  writeAdminAuthToken,
} from '../../core/auth-token.storage';
import type {
  AdminAdministrator,
  AdminModerationReview,
  AdminPlanItem,
  AdminSession,
  AdminTrackAccessEntry,
  AdminTrackApiDto,
  AdminTrackItem,
  AdminUserPlanSummary,
  AudienceReport,
  ExecutiveDashboard,
  GenreAccessCount,
  PlatformCostSettings,
  TrackAccessRank,
} from './admin-mappers';
import {
  DEFAULT_FIRESTORE_QUOTA,
  mapAdminAdministratorDto,
  mapAdminModerationReviewDto,
  mapAdminPlanDto,
  mapAdminTrackAccessEntryDto,
  mapAdminTrackDto,
  mapAdminUserPlanSummaryDto,
  mapAudienceReportDto,
  mapExecutiveDashboardDto,
  mapPlatformCostSettingsDto,
} from './admin-mappers';

export type { AdminTrackItem } from './admin-mappers';

export type AdminTrackSortOption =
  | 'id_asc'
  | 'dislikes_desc'
  | 'likes_desc'
  | 'superlikes_desc'
  | 'recent';

export interface CreateAdminTrackPayload {
  readonly title: string;
  readonly artist: string;
  readonly genre: string;
  readonly duration_seconds: number;
  readonly album?: string;
  readonly country?: string;
  readonly release_year?: number | null;
  readonly cover_url?: string;
  readonly itunes_preview_url?: string;
  readonly spotify_id?: string;
  readonly explicit: boolean;
}

export interface ExternalTrackCandidateApiDto {
  readonly title: string;
  readonly artist: string;
  readonly duration_seconds: number;
  readonly genre: string;
  readonly spotify_id: string | null;
  readonly album: string | null;
  readonly country: string | null;
  readonly release_year: number | null;
  readonly cover_url: string | null;
  readonly itunes_preview_url: string | null;
  readonly explicit: boolean;
  readonly already_in_catalog: boolean;
}

export interface ExternalTrackCandidate {
  readonly title: string;
  readonly artist: string;
  readonly durationSeconds: number;
  readonly genre: string;
  readonly spotifyId: string | null;
  readonly album: string | null;
  readonly country: string | null;
  readonly releaseYear: number | null;
  readonly coverUrl: string | null;
  readonly itunesPreviewUrl: string | null;
  readonly explicit: boolean;
  readonly alreadyInCatalog: boolean;
}

const ADMIN_SESSION_STORAGE_KEY = 'ribbit-admin-session';
const LEGACY_ADMIN_STORAGE_KEYS: readonly string[] = [
  'ribbit-admin-plans',
  'ribbit-admin-users',
  'ribbit-admin-tracks',
  'ribbit-admin-reviews',
];

const EMPTY_DASHBOARD: ExecutiveDashboard = {
  totalUsers: 0,
  estimatedNetRevenue: 0,
  usersByPlan: {},
  revenueByPlan: {},
  profitByPlan: {},
  paidPlansRevenue: 0,
  paidPlansProfit: 0,
  costToRevenuePercent: 0,
  grossRevenue: 0,
  contentCost: 0,
  infrastructureCost: 0,
  totalCosts: 0,
  activeTracksCount: 0,
  contentCostPerTrack: 0.04,
  infrastructureFixedCost: 25,
  infrastructureCostPerUser: 0,
  firestoreUsage: DEFAULT_FIRESTORE_QUOTA,
};

const EMPTY_AUDIENCE: AudienceReport = {
  totalUsers: 0,
  totalTracks: 0,
  activeTracks: 0,
  blockedGenres: {},
  totalAccesses: 0,
  accessesByTrack: [],
  accessesByGenre: [],
};

function clearLegacyAdminMockStorage(): void {
  try {
    if (typeof localStorage === 'undefined') return;
    for (const key of LEGACY_ADMIN_STORAGE_KEYS) {
      localStorage.removeItem(key);
    }
  } catch {
    // Ignore storage cleanup errors in restricted browser contexts
  }
}

function parseCamelSession(parsed: object): AdminSession | null {
  if (
    'userId' in parsed &&
    typeof parsed.userId === 'number' &&
    'email' in parsed &&
    typeof parsed.email === 'string' &&
    'displayName' in parsed &&
    typeof parsed.displayName === 'string' &&
    'isAdmin' in parsed &&
    Boolean(parsed.isAdmin)
  ) {
    return {
      userId: parsed.userId,
      email: parsed.email,
      displayName: parsed.displayName,
      isAdmin: true,
    };
  }
  return null;
}

function parseLegacySession(parsed: object): AdminSession | null {
  if (
    'user_id' in parsed &&
    typeof parsed.user_id === 'number' &&
    'email' in parsed &&
    typeof parsed.email === 'string' &&
    'display_name' in parsed &&
    typeof parsed.display_name === 'string' &&
    'is_admin' in parsed &&
    Boolean(parsed.is_admin)
  ) {
    return {
      userId: parsed.user_id,
      email: parsed.email,
      displayName: parsed.display_name,
      isAdmin: true,
    };
  }
  return null;
}

function parseStoredSession(parsed: unknown): AdminSession | null {
  if (typeof parsed !== 'object' || parsed === null) return null;
  return parseCamelSession(parsed) ?? parseLegacySession(parsed);
}

function readStoredSession(): AdminSession | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    if (!readAdminAuthToken()) {
      localStorage.removeItem(ADMIN_SESSION_STORAGE_KEY);
      return null;
    }
    const raw = localStorage.getItem(ADMIN_SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return parseStoredSession(parsed);
  } catch {
    // Ignore malformed session entries and require fresh authentication
    return null;
  }
}

function writeStoredSession(session: AdminSession): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(ADMIN_SESSION_STORAGE_KEY, JSON.stringify(session));
    }
  } catch {
    // Ignore storage quota errors in browser environments
  }
}

function removeStoredSession(): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(ADMIN_SESSION_STORAGE_KEY);
    }
  } catch {
    // Ignore storage access errors
  }
}

function toPercent(part: number, total: number): number {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

function buildBreakdownFromDashboard(
  dashboard: ExecutiveDashboard,
  plans: readonly AdminPlanItem[],
): readonly PlanBreakdownEntry[] {
  const totalUsers = dashboard.totalUsers;
  const grossRevenue = dashboard.grossRevenue;
  return plans.map((plan) => {
    const count = dashboard.usersByPlan[plan.name] ?? 0;
    const rev = Math.round((dashboard.revenueByPlan[plan.name] ?? 0) * 100) / 100;
    const isPaid = plan.monthlyPrice > 0;
    const allocatedFallback =
      isPaid && totalUsers > 0 ? dashboard.totalCosts * (count / totalUsers) : 0;
    const rawProfit =
      dashboard.profitByPlan[plan.name] ?? (isPaid ? rev - allocatedFallback : 0);
    const profit = isPaid ? Math.round(rawProfit * 100) / 100 : 0;
    const marginPercent = isPaid && rev > 0 ? Math.round((profit / rev) * 100) : 0;
    return {
      planName: plan.name,
      userCount: count,
      userPercent: toPercent(count, totalUsers),
      revenue: rev,
      revenuePercent: toPercent(rev, grossRevenue),
      isPaid,
      profit,
      marginPercent,
    };
  });
}

function buildBlockedGenreEntries(
  record: Readonly<Record<string, number>>,
): readonly BlockedGenreEntry[] {
  const sorted = Object.entries(record).sort((left, right) => right[1] - left[1]);
  const maxCount = sorted[0]?.[1] ?? 0;
  return sorted.map(([genre, count]) => ({
    genre,
    count,
    percent: maxCount > 0 ? Math.round((count / maxCount) * 100) : 0,
  }));
}

function validateAdminAge(rawAge: number | undefined): number {
  const age = rawAge ?? 30;
  if (!Number.isFinite(age) || !Number.isInteger(age) || age < 18) {
    throw new AdminDomainError('A idade mínima do administrador é 18 anos.', 'RULE');
  }
  return age;
}

function buildRegisterAdminPayload(payload: RegisterAdminApiRequest): RegisterAdminApiRequest {
  const email = payload.email.trim().toLowerCase();
  const displayName = payload.display_name.trim();
  if (!email.includes('@')) {
    throw new AdminDomainError('Informe um e-mail válido para o administrador.', 'RULE');
  }
  if (displayName.length < 2 || displayName.length > 50) {
    throw new AdminDomainError('O nome deve ter entre 2 e 50 caracteres.', 'RULE');
  }
  if (payload.password.length < 6) {
    throw new AdminDomainError('A senha deve possuir ao menos 6 caracteres.', 'RULE');
  }
  const age = validateAdminAge(payload.age);
  return {
    email,
    password: payload.password,
    display_name: displayName,
    age,
    ...(payload.birth_date ? { birth_date: payload.birth_date } : {}),
  };
}

function mapAdminDomainError(err: unknown): AdminDomainError {
  if (err instanceof AdminDomainError) {
    return err;
  }
  const apiErr = toApiError(err);
  if (apiErr.status === 401) {
    return new AdminDomainError(apiErr.message || 'Credenciais inválidas.', 'AUTH');
  }
  if (apiErr.status === 403) {
    return new AdminDomainError(
      apiErr.message || 'Acesso restrito a administradores.',
      'FORBIDDEN',
    );
  }
  if (apiErr.status === 404) {
    return new AdminDomainError(apiErr.message || 'Registro não encontrado.', 'NOT_FOUND');
  }
  if (apiErr.status === 409) {
    return new AdminDomainError(apiErr.message || 'Conflito de dados.', 'DUPLICATE');
  }
  return new AdminDomainError(apiErr.message, 'API');
}

/** Coordinates /api/admin/* HTTP integration with reactive Angular signals. */
@Injectable({ providedIn: 'root' })
export class AdminStateService implements OnDestroy {
  private readonly http = inject(HttpClient);
  private readonly sessionNotifier = inject(AuthSessionNotifier);
  private readonly router = inject(Router, { optional: true });

  private readonly sessionSignal = signal<AdminSession | null>(readStoredSession());
  private readonly plansSignal = signal<readonly AdminPlanItem[]>([]);
  private readonly usersSignal = signal<readonly AdminUserPlanSummary[]>([]);
  private readonly administratorsSignal = signal<readonly AdminAdministrator[]>([]);
  private readonly activeTracksSignal = signal<readonly AdminTrackItem[]>([]);
  private readonly blockedTracksSignal = signal<readonly AdminTrackItem[]>([]);
  private readonly reviewsSignal = signal<readonly AdminModerationReview[]>([]);
  private readonly dashboardSignal = signal<ExecutiveDashboard>(EMPTY_DASHBOARD);
  private readonly audienceSignal = signal<AudienceReport>(EMPTY_AUDIENCE);
  private readonly isLoadingSignal = signal<boolean>(false);
  private readonly syncErrorSignal = signal<string>('');
  private readonly toastSignal = signal<string>('');
  private readonly hasHydratedSignal = signal<boolean>(false);
  private readonly lastCatalogQuerySignal = signal<string>('');
  private readonly accessHistorySignal = signal<readonly AdminTrackAccessEntry[]>([]);

  private readonly unsubscribeAdminUnauthorized: () => void;
  private hydrationSub: Subscription | null = null;
  private refreshSub: Subscription | null = null;
  private sessionEpoch = 0;
  private toastTimer: ReturnType<typeof setTimeout> | null = null;

  readonly currentAdmin = this.sessionSignal.asReadonly();
  readonly isAuthenticated = computed<boolean>(() => Boolean(this.sessionSignal()?.isAdmin));
  readonly plans = this.plansSignal.asReadonly();
  readonly usersWithPlans = this.usersSignal.asReadonly();
  readonly administrators = this.administratorsSignal.asReadonly();
  readonly activeTracks = this.activeTracksSignal.asReadonly();
  readonly blockedTracks = this.blockedTracksSignal.asReadonly();
  readonly executiveDashboard = this.dashboardSignal.asReadonly();
  readonly audienceReport = this.audienceSignal.asReadonly();
  readonly isLoading = this.isLoadingSignal.asReadonly();
  readonly syncError = this.syncErrorSignal.asReadonly();
  readonly toastMessage = this.toastSignal.asReadonly();
  readonly hasHydrated = this.hasHydratedSignal.asReadonly();
  readonly lastCatalogQuery = this.lastCatalogQuerySignal.asReadonly();
  readonly accessHistory = this.accessHistorySignal.asReadonly();

  readonly topModerationReviews = computed<readonly AdminModerationReview[]>(() =>
    [...this.reviewsSignal()]
      .filter((review) => !review.isDeleted)
      .sort((left, right) => right.likesCount - left.likesCount)
      .slice(0, 10),
  );

  readonly planBreakdown = computed<readonly PlanBreakdownEntry[]>(() =>
    buildBreakdownFromDashboard(this.dashboardSignal(), this.plansSignal()),
  );

  readonly blockedGenreRanking = computed<readonly BlockedGenreEntry[]>(() =>
    buildBlockedGenreEntries(this.audienceSignal().blockedGenres),
  );

  readonly accessesByGenreRanking = computed<
    readonly (GenreAccessCount & { readonly percent: number })[]
  >(() => {
    const list = this.audienceSignal().accessesByGenre;
    const maxCount = list[0]?.accessCount ?? 0;
    return list.map((item) => ({
      ...item,
      percent: maxCount > 0 ? Math.round((item.accessCount / maxCount) * 100) : 0,
    }));
  });

  readonly topAccessedTracks = computed<
    readonly (TrackAccessRank & { readonly percent: number })[]
  >(() => {
    const list = this.audienceSignal().accessesByTrack;
    const maxCount = list[0]?.accessCount ?? 0;
    return list.map((item) => ({
      ...item,
      percent: maxCount > 0 ? Math.round((item.accessCount / maxCount) * 100) : 0,
    }));
  });

  constructor() {
    clearLegacyAdminMockStorage();
    this.unsubscribeAdminUnauthorized = this.sessionNotifier.onAdminUnauthorized(() => {
      this.clearSessionState();
      if (this.router) {
        this.router.navigate(['/admin/login']).catch(() => {});
      }
    });
  }

  ngOnDestroy(): void {
    this.unsubscribeAdminUnauthorized();
    this.hydrationSub?.unsubscribe();
    this.hydrationSub = null;
    this.refreshSub?.unsubscribe();
    this.refreshSub = null;
    if (this.toastTimer !== null) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
  }

  /** Authenticates an administrator against POST /api/admin/login and hydrates dashboard state. */
  loginAdmin(email: string, password: string): Observable<AdminSession> {
    const normalizedEmail = email.trim().toLowerCase();
    return this.http
      .post<AuthApiResponse>('/api/admin/login', {
        email: normalizedEmail,
        password,
      })
      .pipe(
        map((response) => {
          if (!response.user.is_admin) {
            throw new AdminDomainError('Acesso restrito a administradores.', 'FORBIDDEN');
          }
          writeAdminAuthToken(response.access_token);
          const session: AdminSession = {
            userId: response.user.user_id,
            email: response.user.email,
            displayName: response.user.display_name,
            isAdmin: response.user.is_admin,
          };
          this.sessionSignal.set(session);
          writeStoredSession(session);
          this.hydrateFromBackend();
          this.notify(`Bem-vindo ao Console Admin, ${session.displayName}.`);
          return session;
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Loads all administrative projections from /api/admin/* endpoints into reactive signals. */
  hydrateFromBackend(): void {
    this.hydrationSub?.unsubscribe();
    const expectedEpoch = this.sessionEpoch;
    this.isLoadingSignal.set(true);
    this.syncErrorSignal.set('');

    this.hydrationSub = forkJoin({
      plans: this.http
        .get<readonly PlanApiDto[]>('/api/admin/plans')
        .pipe(map((items) => items.map((item) => mapAdminPlanDto(item)))),
      dashboard: this.http
        .get<ExecutiveDashboardApiDto>('/api/admin/dashboard')
        .pipe(map((dto) => mapExecutiveDashboardDto(dto))),
      audience: this.http
        .get<AudienceReportApiDto>('/api/admin/audience')
        .pipe(map((dto) => mapAudienceReportDto(dto))),
      users: this.http
        .get<readonly AdminUserPlanSummaryApiDto[]>('/api/admin/users')
        .pipe(map((items) => items.map((item) => mapAdminUserPlanSummaryDto(item)))),
      admins: this.http
        .get<readonly UserApiDto[]>('/api/admin/administrators')
        .pipe(map((items) => items.map((item) => mapAdminAdministratorDto(item)))),
      activeTracks: this.http
        .get<readonly AdminTrackApiDto[]>('/api/admin/tracks', {
          params: new HttpParams().set('limit', '100'),
        })
        .pipe(map((items) => items.map((item) => mapAdminTrackDto(item)))),
      blockedTracks: this.http
        .get<readonly AdminTrackApiDto[]>('/api/admin/blocked-tracks')
        .pipe(map((items) => items.map((item) => mapAdminTrackDto(item)))),
      reviews: this.http.get<readonly ReviewApiDto[]>('/api/admin/reviews'),
    }).subscribe({
      next: (payload) => {
        if (this.sessionEpoch !== expectedEpoch) return;
        this.plansSignal.set(payload.plans);
        this.dashboardSignal.set(payload.dashboard);
        this.audienceSignal.set(payload.audience);
        this.usersSignal.set(payload.users);
        this.administratorsSignal.set(payload.admins);
        this.activeTracksSignal.set(payload.activeTracks);
        this.lastCatalogQuerySignal.set('');
        this.blockedTracksSignal.set(payload.blockedTracks);
        this.reviewsSignal.set(
          this.mapReviews(payload.reviews, payload.users, [
            ...payload.activeTracks,
            ...payload.blockedTracks,
          ]),
        );
        this.hasHydratedSignal.set(true);
        this.isLoadingSignal.set(false);
        this.syncErrorSignal.set('');
      },
      error: (err: unknown) => {
        if (this.sessionEpoch !== expectedEpoch) return;
        this.isLoadingSignal.set(false);
        this.syncErrorSignal.set(mapAdminDomainError(err).message);
      },
    });
  }

  /** Clears the active administrative session and resets cached backend signals. */
  logoutAdmin(): void {
    this.clearSessionState();
    this.notify('Sessão administrativa encerrada.');
  }

  /** Registers a new eligible administrator via POST /api/admin/administrators. */
  registerAdministrator(payload: RegisterAdminApiRequest): Observable<AdminAdministrator> {
    let requestBody: RegisterAdminApiRequest;
    try {
      requestBody = buildRegisterAdminPayload(payload);
    } catch (err: unknown) {
      return throwError(() => mapAdminDomainError(err));
    }

    return this.http.post<UserApiDto>('/api/admin/administrators', requestBody).pipe(
      map((dto) => mapAdminAdministratorDto(dto)),
      tap((createdAdmin) => {
        this.administratorsSignal.update((current) => [
          ...current.filter((admin) => admin.userId !== createdAdmin.userId),
          createdAdmin,
        ]);
        this.refreshUsersAndMetrics();
        this.notify(`Administrador "${createdAdmin.displayName}" cadastrado com sucesso.`);
      }),
      catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
    );
  }

  /** Promotes an existing user to administrator via PUT /api/admin/administrators/{id}. */
  promoteUserToAdmin(userId: number): Observable<AdminAdministrator> {
    return this.updateAdminRole(userId, true);
  }

  /** Updates administrator privileges via PUT /api/admin/administrators/{id}. */
  updateAdminRole(targetUserId: number, isAdmin: boolean): Observable<AdminAdministrator> {
    const activeAdminId = this.sessionSignal()?.userId;
    if (activeAdminId === targetUserId && !isAdmin) {
      return throwError(
        () => new AdminDomainError('Administrador não pode revogar o próprio acesso.', 'RULE'),
      );
    }

    return this.http
      .put<UserApiDto>(`/api/admin/administrators/${targetUserId}`, {
        is_admin: isAdmin,
      })
      .pipe(
        map((dto) => mapAdminAdministratorDto(dto)),
        tap((remoteUser) => {
          this.usersSignal.update((users) =>
            users.map((user) =>
              user.userId === remoteUser.userId ? { ...user, isAdmin: remoteUser.isAdmin } : user,
            ),
          );
          if (remoteUser.isAdmin) {
            this.administratorsSignal.update((admins) => [
              ...admins.filter((admin) => admin.userId !== remoteUser.userId),
              remoteUser,
            ]);
          } else {
            this.administratorsSignal.update((admins) =>
              admins.filter((admin) => admin.userId !== remoteUser.userId),
            );
          }
          this.notify(
            remoteUser.isAdmin
              ? `${remoteUser.displayName} agora possui acesso administrativo.`
              : `Acesso administrativo de ${remoteUser.displayName} revogado.`,
          );
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Updates plan pricing, name, or profile limits via PUT /api/admin/plans/{id}. */
  updatePlan(planId: number, payload: UpdateAdminPlanPayload): Observable<AdminPlanItem> {
    const existingPlan = this.plansSignal().find((item) => item.planId === planId);
    if (!existingPlan) {
      return throwError(() => new AdminDomainError(`Plano ${planId} não encontrado.`, 'NOT_FOUND'));
    }

    let resolvedName = existingPlan.name;
    let resolvedPrice = existingPlan.monthlyPrice;
    let resolvedMaxProfiles = existingPlan.maxProfiles;
    try {
      if (payload.new_name !== undefined) {
        resolvedName = this.validatePlanName(planId, payload.new_name);
      }
      if (payload.new_price !== undefined) {
        resolvedPrice = this.validatePlanPrice(payload.new_price);
      }
      if (payload.max_profiles !== undefined) {
        resolvedMaxProfiles = this.validateMaxProfiles(payload.max_profiles);
      }
    } catch (err: unknown) {
      return throwError(() => mapAdminDomainError(err));
    }

    return this.http
      .put<PlanApiDto>(`/api/admin/plans/${planId}`, {
        new_name: resolvedName,
        new_price: resolvedPrice,
        max_profiles: resolvedMaxProfiles,
      })
      .pipe(
        map((dto) => mapAdminPlanDto(dto)),
        tap((remotePlan) => {
          this.plansSignal.update((plans) =>
            plans.map((item) => (item.planId === planId ? remotePlan : item)),
          );
          this.refreshDashboardAndUsers();
          this.notify(`Plano "${remotePlan.name}" atualizado com sucesso.`);
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Queries GET /api/admin/tracks with optional search, sort, and dislike filter. */
  loadAdminCatalog(
    options: {
      readonly query?: string;
      readonly sortBy?: AdminTrackSortOption;
      readonly minDislikes?: number | null;
      readonly limit?: number;
    } = {},
  ): Observable<readonly AdminTrackItem[]> {
    let params = new HttpParams().set('limit', String(options.limit ?? 100));
    const trimmed = options.query?.trim() ?? '';
    if (trimmed) {
      params = params.set('query', trimmed);
    }
    if (options.sortBy && options.sortBy !== 'id_asc') {
      params = params.set('sort_by', options.sortBy);
    }
    if (options.minDislikes !== null && options.minDislikes !== undefined) {
      params = params.set('min_dislikes', String(options.minDislikes));
    }

    const expectedEpoch = this.sessionEpoch;
    return this.http.get<readonly AdminTrackApiDto[]>('/api/admin/tracks', { params }).pipe(
      map((items) => items.map((item) => mapAdminTrackDto(item))),
      tap((remoteTracks) => {
        if (this.sessionEpoch !== expectedEpoch) return;
        this.activeTracksSignal.set(remoteTracks);
        this.lastCatalogQuerySignal.set(trimmed);
      }),
      catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
    );
  }

  /** Queries GET /api/admin/tracks on the backend and updates active catalog tracks. */
  fetchCatalogTracksFromBackend(query: string): Observable<readonly AdminTrackItem[]> {
    return this.loadAdminCatalog({ query });
  }

  /** Queries GET /api/admin/tracks/external-search by title and artist. */
  searchExternalTracks(
    title: string,
    artist: string,
  ): Observable<readonly ExternalTrackCandidate[]> {
    let params = new HttpParams().set('limit', '10');
    if (title.trim()) params = params.set('title', title.trim());
    if (artist.trim()) params = params.set('artist', artist.trim());
    return this.http
      .get<readonly ExternalTrackCandidateApiDto[]>('/api/admin/tracks/external-search', { params })
      .pipe(
        map((items) =>
          items.map((item) => ({
            title: item.title,
            artist: item.artist,
            durationSeconds: item.duration_seconds,
            genre: item.genre,
            spotifyId: item.spotify_id,
            album: item.album,
            country: item.country,
            releaseYear: item.release_year,
            coverUrl: item.cover_url,
            itunesPreviewUrl: item.itunes_preview_url,
            explicit: item.explicit,
            alreadyInCatalog: item.already_in_catalog,
          })),
        ),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Creates a new catalog track via POST /api/admin/tracks and refreshes metrics. */
  createTrack(payload: CreateAdminTrackPayload): Observable<AdminTrackItem> {
    return this.http.post<AdminTrackApiDto>('/api/admin/tracks', payload).pipe(
      map((item) => mapAdminTrackDto(item)),
      tap((created) => {
        this.activeTracksSignal.update((tracks) => [created, ...tracks]);
        this.refreshAudienceAndDashboard();
        this.notify(`Faixa "${created.title}" cadastrada no catálogo.`);
      }),
      catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
    );
  }

  /** Blocks or restores a catalog track via PUT /api/admin/tracks/{id}/block. */
  setTrackBlocked(trackId: number, blocked: boolean): Observable<TrackBlockApiResponse> {
    return this.http
      .put<TrackBlockApiResponse>(`/api/admin/tracks/${trackId}/block`, {
        blocked,
      })
      .pipe(
        tap((response) => {
          this.applyTrackBlockUpdate(trackId, response.blocked);
          this.refreshAudienceAndDashboard();
          const title = this.findTrackTitle(trackId);
          this.notify(
            response.blocked
              ? `Faixa "${title}" bloqueada no catálogo.`
              : `Faixa "${title}" restaurada ao catálogo ativo.`,
          );
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Updates explicit advisory flag via PUT /api/admin/tracks/{id}/explicit. */
  setTrackExplicit(trackId: number, explicit: boolean): Observable<TrackExplicitApiResponse> {
    return this.http
      .put<TrackExplicitApiResponse>(`/api/admin/tracks/${trackId}/explicit`, {
        explicit,
      })
      .pipe(
        tap((response) => {
          this.patchTrackInLists(trackId, (track) => ({
            ...track,
            explicit: response.explicit,
          }));
          const title = this.findTrackTitle(trackId);
          this.notify(
            response.explicit
              ? `Selo +18 ativado em "${title}".`
              : `Selo +18 removido de "${title}".`,
          );
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Updates track genre via PUT /api/admin/tracks/{id}/genre. */
  updateTrackGenre(trackId: number, genre: string): Observable<TrackGenreApiResponse> {
    const trimmedGenre = genre.trim();
    if (!trimmedGenre) {
      return throwError(() => new AdminDomainError('O gênero da faixa é obrigatório.', 'RULE'));
    }

    return this.http
      .put<TrackGenreApiResponse>(`/api/admin/tracks/${trackId}/genre`, {
        genre: trimmedGenre,
      })
      .pipe(
        tap((response) => {
          this.patchTrackInLists(trackId, (track) => ({
            ...track,
            genre: response.genre,
          }));
          this.notify(`Gênero da faixa #${trackId} atualizado para "${response.genre}".`);
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Triggers catalog delta-table compaction via POST /api/admin/catalog/compact. */
  compactCatalog(): Observable<CompactCatalogApiResponse> {
    return this.http.post<CompactCatalogApiResponse>('/api/admin/catalog/compact', {}).pipe(
      tap((response) => {
        this.notify(response.message || 'Catálogo compactado com sucesso.');
      }),
      catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
    );
  }

  /** Synchronizes catalog delta tables via POST /api/admin/catalog/sync. */
  syncCatalog(force = false): Observable<SyncCatalogVersionApiResponse> {
    const params = new HttpParams().set('force', String(force));
    return this.http
      .post<SyncCatalogVersionApiResponse>('/api/admin/catalog/sync', {}, { params })
      .pipe(
        tap((response) => {
          this.notify(response.message || 'Catálogo sincronizado com sucesso.');
          if (response.synced) {
            this.refreshTracksAndAudience();
          }
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Requests review deletion via DELETE /api/admin/reviews/{id}. */
  deleteReview(reviewId: number): Observable<ActionSuccessApiDto> {
    return this.http
      .delete<ActionSuccessApiDto>(`/api/admin/reviews/${reviewId}`, {
        context: createAdminHttpContext(),
      })
      .pipe(
        tap((response) => {
          if (response.success) {
            this.reviewsSignal.update((reviews) =>
              reviews.map((item) =>
                item.reviewId === reviewId ? { ...item, isDeleted: true } : item,
              ),
            );
            this.notify(`Avaliação #${reviewId} removida pela moderação.`);
          }
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Displays a transient feedback toast inside the admin console. */
  notify(message: string): void {
    this.toastSignal.set(message);
    if (this.toastTimer !== null) {
      clearTimeout(this.toastTimer);
    }
    this.toastTimer = setTimeout(() => {
      if (this.toastSignal() === message) {
        this.toastSignal.set('');
      }
      this.toastTimer = null;
    }, 3400);
  }

  /** Dismisses the active admin toast banner immediately. */
  clearToast(): void {
    this.toastSignal.set('');
    if (this.toastTimer !== null) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
  }

  private clearSessionState(): void {
    this.sessionEpoch += 1;
    this.hydrationSub?.unsubscribe();
    this.hydrationSub = null;
    this.refreshSub?.unsubscribe();
    this.refreshSub = null;
    this.isLoadingSignal.set(false);
    this.sessionSignal.set(null);
    this.plansSignal.set([]);
    this.usersSignal.set([]);
    this.accessHistorySignal.set([]);
    this.administratorsSignal.set([]);
    this.activeTracksSignal.set([]);
    this.blockedTracksSignal.set([]);
    this.reviewsSignal.set([]);
    this.dashboardSignal.set(EMPTY_DASHBOARD);
    this.audienceSignal.set(EMPTY_AUDIENCE);
    this.hasHydratedSignal.set(false);
    this.lastCatalogQuerySignal.set('');
    this.syncErrorSignal.set('');
    removeStoredSession();
    clearAdminAuthToken();
  }

  private mapReviews(
    reviewDtos: readonly ReviewApiDto[],
    users: readonly AdminUserPlanSummary[],
    tracks: readonly AdminTrackItem[],
  ): AdminModerationReview[] {
    const userById = new Map<number, AdminUserPlanSummary>(
      users.map((user) => [user.userId, user]),
    );
    const trackById = new Map<number, AdminTrackItem>(
      tracks.map((track) => [track.trackId, track]),
    );

    return reviewDtos.map((dto, index) =>
      mapAdminModerationReviewDto(dto, index, userById, trackById),
    );
  }

  private runBackgroundRefresh<T>(source$: Observable<T>, apply: (payload: T) => void): void {
    this.refreshSub?.unsubscribe();
    const expectedEpoch = this.sessionEpoch;
    this.refreshSub = source$.subscribe({
      next: (payload) => {
        if (this.sessionEpoch !== expectedEpoch) return;
        apply(payload);
      },
      error: (err: unknown) => {
        if (this.sessionEpoch !== expectedEpoch) return;
        this.syncErrorSignal.set(mapAdminDomainError(err).message);
      },
    });
  }

  loadAccessHistory(filters?: {
    readonly userId?: number | null;
    readonly onlyDeleted?: boolean;
    readonly limit?: number;
  }): void {
    let params = new HttpParams().set('limit', String(filters?.limit ?? 100));
    if (filters?.userId !== undefined && filters.userId !== null) {
      params = params.set('user_id', String(filters.userId));
    }
    if (filters?.onlyDeleted) {
      params = params.set('only_deleted', 'true');
    }
    this.runBackgroundRefresh(
      this.http
        .get<readonly AdminTrackAccessEntryApiDto[]>('/api/admin/access-history', { params })
        .pipe(map((entries) => entries.map((entry) => mapAdminTrackAccessEntryDto(entry)))),
      (entries) => {
        this.accessHistorySignal.set(entries);
      },
    );
  }

  updatePlatformCosts(payload: UpdatePlatformCostsPayload): Observable<PlatformCostSettings> {
    if (
      !Number.isFinite(payload.content_cost_per_track) ||
      payload.content_cost_per_track < 0 ||
      !Number.isFinite(payload.infrastructure_fixed_cost) ||
      payload.infrastructure_fixed_cost < 0 ||
      !Number.isFinite(payload.infrastructure_cost_per_user) ||
      payload.infrastructure_cost_per_user < 0
    ) {
      return throwError(
        () => new AdminDomainError('Os custos operacionais não podem ser negativos.', 'RULE'),
      );
    }
    return this.http.put<PlatformCostSettingsApiDto>('/api/admin/costs', payload).pipe(
      map((dto) => mapPlatformCostSettingsDto(dto)),
      tap(() => {
        this.notify('Custos operacionais atualizados com sucesso.');
        this.runBackgroundRefresh(
          this.http
            .get<ExecutiveDashboardApiDto>('/api/admin/dashboard')
            .pipe(map((dto) => mapExecutiveDashboardDto(dto))),
          (dashboard) => {
            this.dashboardSignal.set(dashboard);
          },
        );
      }),
      catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
    );
  }

  private refreshUsersAndMetrics(): void {
    this.runBackgroundRefresh(
      forkJoin({
        users: this.http
          .get<readonly AdminUserPlanSummaryApiDto[]>('/api/admin/users')
          .pipe(map((items) => items.map((item) => mapAdminUserPlanSummaryDto(item)))),
        dashboard: this.http
          .get<ExecutiveDashboardApiDto>('/api/admin/dashboard')
          .pipe(map((dto) => mapExecutiveDashboardDto(dto))),
        audience: this.http
          .get<AudienceReportApiDto>('/api/admin/audience')
          .pipe(map((dto) => mapAudienceReportDto(dto))),
      }),
      (payload) => {
        this.usersSignal.set(payload.users);
        this.dashboardSignal.set(payload.dashboard);
        this.audienceSignal.set(payload.audience);
      },
    );
  }

  private refreshDashboardAndUsers(): void {
    this.runBackgroundRefresh(
      forkJoin({
        dashboard: this.http
          .get<ExecutiveDashboardApiDto>('/api/admin/dashboard')
          .pipe(map((dto) => mapExecutiveDashboardDto(dto))),
        users: this.http
          .get<readonly AdminUserPlanSummaryApiDto[]>('/api/admin/users')
          .pipe(map((items) => items.map((item) => mapAdminUserPlanSummaryDto(item)))),
      }),
      (payload) => {
        this.dashboardSignal.set(payload.dashboard);
        this.usersSignal.set(payload.users);
      },
    );
  }

  private refreshAudienceAndDashboard(): void {
    this.runBackgroundRefresh(
      forkJoin({
        audience: this.http
          .get<AudienceReportApiDto>('/api/admin/audience')
          .pipe(map((dto) => mapAudienceReportDto(dto))),
        dashboard: this.http
          .get<ExecutiveDashboardApiDto>('/api/admin/dashboard')
          .pipe(map((dto) => mapExecutiveDashboardDto(dto))),
      }),
      (payload) => {
        this.audienceSignal.set(payload.audience);
        this.dashboardSignal.set(payload.dashboard);
      },
    );
  }

  private refreshTracksAndAudience(): void {
    this.runBackgroundRefresh(
      forkJoin({
        activeTracks: this.http
          .get<readonly AdminTrackApiDto[]>('/api/admin/tracks', {
            params: new HttpParams().set('limit', '100'),
          })
          .pipe(map((items) => items.map((item) => mapAdminTrackDto(item)))),
        blockedTracks: this.http
          .get<readonly AdminTrackApiDto[]>('/api/admin/blocked-tracks')
          .pipe(map((items) => items.map((item) => mapAdminTrackDto(item)))),
        audience: this.http
          .get<AudienceReportApiDto>('/api/admin/audience')
          .pipe(map((dto) => mapAudienceReportDto(dto))),
      }),
      (payload) => {
        this.activeTracksSignal.set(payload.activeTracks);
        this.lastCatalogQuerySignal.set('');
        this.blockedTracksSignal.set(payload.blockedTracks);
        this.audienceSignal.set(payload.audience);
      },
    );
  }

  private applyTrackBlockUpdate(trackId: number, blocked: boolean): void {
    if (blocked) {
      const target = this.activeTracksSignal().find((track) => track.trackId === trackId);
      this.activeTracksSignal.update((tracks) =>
        tracks.filter((track) => track.trackId !== trackId),
      );
      if (target) {
        this.blockedTracksSignal.update((tracks) => [
          ...tracks.filter((track) => track.trackId !== trackId),
          { ...target, isDeleted: true },
        ]);
      }
      return;
    }

    const target = this.blockedTracksSignal().find((track) => track.trackId === trackId);
    this.blockedTracksSignal.update((tracks) =>
      tracks.filter((track) => track.trackId !== trackId),
    );
    if (target) {
      this.activeTracksSignal.update((tracks) => [
        ...tracks.filter((track) => track.trackId !== trackId),
        { ...target, isDeleted: false },
      ]);
    }
  }

  private patchTrackInLists(
    trackId: number,
    updater: (track: AdminTrackItem) => AdminTrackItem,
  ): void {
    this.activeTracksSignal.update((tracks) =>
      tracks.map((track) => (track.trackId === trackId ? updater(track) : track)),
    );
    this.blockedTracksSignal.update((tracks) =>
      tracks.map((track) => (track.trackId === trackId ? updater(track) : track)),
    );
  }

  private findTrackTitle(trackId: number): string {
    const found =
      this.activeTracksSignal().find((track) => track.trackId === trackId) ??
      this.blockedTracksSignal().find((track) => track.trackId === trackId);
    return found?.title ?? `#${trackId}`;
  }

  private validatePlanName(planId: number, rawName: string): string {
    const cleaned = rawName.trim();
    if (!cleaned) {
      throw new AdminDomainError('O nome do plano é obrigatório.', 'RULE');
    }
    const duplicate = this.plansSignal().some(
      (plan) => plan.planId !== planId && plan.name.toLowerCase() === cleaned.toLowerCase(),
    );
    if (duplicate) {
      throw new AdminDomainError('Já existe um plano com esse nome.', 'DUPLICATE');
    }
    return cleaned;
  }

  private validatePlanPrice(price: number): number {
    if (!Number.isFinite(price) || price < 0) {
      throw new AdminDomainError('O preço mensal não pode ser negativo.', 'RULE');
    }
    return Math.round(price * 100) / 100;
  }

  private validateMaxProfiles(maxProfiles: number): number {
    if (!Number.isFinite(maxProfiles) || !Number.isInteger(maxProfiles) || maxProfiles < 1) {
      throw new AdminDomainError('O limite de perfis deve ser de pelo menos 1.', 'RULE');
    }
    return maxProfiles;
  }
}
