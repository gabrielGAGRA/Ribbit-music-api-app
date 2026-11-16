import { HttpBackend, HttpClient, HttpParams, HttpXhrBackend } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
import type { Observable } from 'rxjs';
import { forkJoin, of, throwError } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';
import type {
  AdminAccount,
  AdminModerationReview,
  AdminSession,
  AdminUserPlanSummary,
  AudienceReportApiDto,
  AuthApiResponse,
  BlockedGenreEntry,
  CompactCatalogApiResponse,
  ExecutiveDashboardApiDto,
  PlanApiDto,
  PlanBreakdownEntry,
  ReviewApiDto,
  SyncCatalogVersionApiResponse,
  TrackApiDto,
  TrackGenreApiResponse,
  UpdateAdminPlanPayload,
  UserApiDto,
} from '@ribbit/shared-types';
import { toApiError } from '../../core/api-error';
import {
  clearAdminAuthToken,
  createAdminHttpContext,
  readAdminAuthToken,
  writeAdminAuthToken,
} from '../../core/auth-token.storage';
import { safeInject } from '../../core/safe-inject';
import {
  DEFAULT_ADMIN_EMAIL,
  DEFAULT_ADMIN_PASSWORD,
  MOCK_ADMIN_PLANS,
  MOCK_ADMIN_REVIEWS,
  MOCK_ADMIN_TRACKS,
  MOCK_ADMIN_USERS,
} from './admin.mock';

const STORAGE_KEYS = {
  session: 'ribbit-admin-session',
  plans: 'ribbit-admin-plans',
  users: 'ribbit-admin-users',
  tracks: 'ribbit-admin-tracks',
  reviews: 'ribbit-admin-reviews',
} as const;

interface TrackBlockApiDto {
  readonly track_id?: number | null;
  readonly blocked: boolean;
}

interface TrackExplicitApiDto {
  readonly track_id: number;
  readonly explicit: boolean;
}

/** Represents a domain or authorization rule violation in the administrative console. */
export class AdminDomainError extends Error {
  readonly code: 'AUTH' | 'FORBIDDEN' | 'NOT_FOUND' | 'RULE' | 'DUPLICATE';

  constructor(
    message: string,
    code: 'AUTH' | 'FORBIDDEN' | 'NOT_FOUND' | 'RULE' | 'DUPLICATE' = 'RULE',
  ) {
    super(message);
    this.name = 'AdminDomainError';
    this.code = code;
  }
}

function readStoredJson<T>(key: string, fallback: T): T {
  try {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed: unknown = JSON.parse(raw);
    return parsed !== null && typeof parsed === 'object' ? (parsed as T) : fallback;
  } catch {
    // Ignore malformed localStorage entries and restore mock fallback
    return fallback;
  }
}

function readStoredArray<T>(key: string, fallback: readonly T[]): readonly T[] {
  try {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as readonly T[]) : fallback;
  } catch {
    // Ignore malformed localStorage arrays and restore mock fallback
    return fallback;
  }
}

function writeStoredJson<T>(key: string, value: T): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // Ignore storage quota errors in browser environments
  }
}

function removeStoredKey(key: string): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(key);
    }
  } catch {
    // Ignore storage access errors
  }
}

function toPercent(part: number, total: number): number {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

function accumulatePlanTotals(
  users: readonly AdminAccount[],
  plans: readonly PlanApiDto[],
): {
  readonly userCounts: ReadonlyMap<string, number>;
  readonly planRevenues: ReadonlyMap<string, number>;
  readonly totalRevenue: number;
} {
  const planMap = new Map<number, PlanApiDto>(plans.map((plan) => [plan.plan_id, plan]));
  const userCounts = new Map<string, number>();
  const planRevenues = new Map<string, number>();
  let totalRevenue = 0;

  for (const user of users) {
    const plan = planMap.get(user.plan_id);
    if (!plan) continue;
    userCounts.set(plan.name, (userCounts.get(plan.name) ?? 0) + 1);
    if (user.primary_account_id === undefined) {
      totalRevenue += plan.monthly_price;
      planRevenues.set(plan.name, (planRevenues.get(plan.name) ?? 0) + plan.monthly_price);
    }
  }

  return { userCounts, planRevenues, totalRevenue };
}

function buildBreakdownFromDashboard(
  dashboard: ExecutiveDashboardApiDto,
  plans: readonly PlanApiDto[],
): readonly PlanBreakdownEntry[] {
  const totalUsers = dashboard.total_users;
  const totalRevenue = dashboard.estimated_net_revenue;
  return plans.map((plan) => {
    const count = dashboard.users_by_plan[plan.name] ?? 0;
    const rev = Math.round((dashboard.revenue_by_plan[plan.name] ?? 0) * 100) / 100;
    return {
      planName: plan.name,
      userCount: count,
      userPercent: toPercent(count, totalUsers),
      revenue: rev,
      revenuePercent: toPercent(rev, totalRevenue),
    };
  });
}

function computePlanMetrics(
  users: readonly AdminAccount[],
  plans: readonly PlanApiDto[],
): {
  readonly dashboard: ExecutiveDashboardApiDto;
  readonly breakdown: readonly PlanBreakdownEntry[];
} {
  const { userCounts, planRevenues, totalRevenue } = accumulatePlanTotals(users, plans);
  const roundedTotalRevenue = Math.round(totalRevenue * 100) / 100;
  const totalUsers = users.length;
  const usersByPlanObj: Record<string, number> = {};
  const revenueByPlanObj: Record<string, number> = {};

  for (const plan of plans) {
    const count = userCounts.get(plan.name) ?? 0;
    const rev = Math.round((planRevenues.get(plan.name) ?? 0) * 100) / 100;
    usersByPlanObj[plan.name] = count;
    revenueByPlanObj[plan.name] = rev;
  }

  const dashboard: ExecutiveDashboardApiDto = {
    total_users: totalUsers,
    estimated_net_revenue: roundedTotalRevenue,
    users_by_plan: usersByPlanObj,
    revenue_by_plan: revenueByPlanObj,
  };

  return {
    dashboard,
    breakdown: buildBreakdownFromDashboard(dashboard, plans),
  };
}

function buildBlockedGenreEntriesFromRecord(
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

function computeBlockedGenres(users: readonly AdminAccount[]): {
  readonly record: Readonly<Record<string, number>>;
  readonly entries: readonly BlockedGenreEntry[];
} {
  const counts = new Map<string, number>();
  for (const user of users) {
    for (const genre of user.blocked_genres) {
      counts.set(genre, (counts.get(genre) ?? 0) + 1);
    }
  }

  const record: Record<string, number> = {};
  for (const [genre, count] of counts.entries()) {
    record[genre] = count;
  }

  return {
    record,
    entries: buildBlockedGenreEntriesFromRecord(record),
  };
}

function resolveActiveHttpClient(): HttpClient | null {
  const client = safeInject(HttpClient, null);
  if (!client) return null;
  const backend = safeInject(HttpBackend, null);
  const isUnmockedJsdom =
    typeof navigator !== 'undefined' &&
    navigator.userAgent.includes('jsdom') &&
    backend instanceof HttpXhrBackend;
  return isUnmockedJsdom ? null : client;
}

function resolveMergedPlanId(
  planName: string,
  planIdByName: ReadonlyMap<string, number>,
  adminDto: UserApiDto | undefined,
  existing: AdminAccount | undefined,
): number {
  const byName = planIdByName.get(planName.toLowerCase());
  if (byName !== undefined) return byName;
  if (adminDto !== undefined) return adminDto.plan_id;
  return existing ? existing.plan_id : 1;
}

function resolveMergedBlockedGenres(
  adminDto: UserApiDto | undefined,
  existing: AdminAccount | undefined,
): readonly string[] {
  if (adminDto?.blocked_genres) return [...adminDto.blocked_genres];
  return existing ? existing.blocked_genres : [];
}

function resolveMergedCreatedAt(
  adminDto: UserApiDto | undefined,
  existing: AdminAccount | undefined,
): string {
  if (adminDto?.created_at) return adminDto.created_at;
  return existing ? existing.created_at : new Date().toISOString();
}

function mergeAdminAccountFromSummary(
  summary: AdminUserPlanSummary,
  planIdByName: ReadonlyMap<string, number>,
  adminById: ReadonlyMap<number, UserApiDto>,
  existingById: ReadonlyMap<number, AdminAccount>,
): AdminAccount {
  const existing = existingById.get(summary.user_id);
  const adminDto = adminById.get(summary.user_id);
  const primaryAccountId = adminDto?.primary_account_id ?? existing?.primary_account_id;
  return {
    user_id: summary.user_id,
    email: summary.email,
    password: existing ? existing.password : '',
    display_name: summary.display_name,
    age: summary.age,
    plan_id: resolveMergedPlanId(summary.plan_name, planIdByName, adminDto, existing),
    is_admin: summary.is_admin || adminById.has(summary.user_id),
    ...(primaryAccountId != null ? { primary_account_id: primaryAccountId } : {}),
    blocked_genres: resolveMergedBlockedGenres(adminDto, existing),
    created_at: resolveMergedCreatedAt(adminDto, existing),
  };
}

/** Coordinates /api/admin/* HTTP integration with explicit local fallback state when offline or isolated. */
@Injectable({ providedIn: 'root' })
export class AdminStateService {
  private readonly http = resolveActiveHttpClient();
  private readonly sessionSignal = signal<AdminSession | null>(
    readStoredJson<AdminSession | null>(STORAGE_KEYS.session, null),
  );
  private readonly plansSignal = signal<readonly PlanApiDto[]>(
    readStoredArray<PlanApiDto>(STORAGE_KEYS.plans, MOCK_ADMIN_PLANS),
  );
  private readonly usersSignal = signal<readonly AdminAccount[]>(
    readStoredArray<AdminAccount>(STORAGE_KEYS.users, MOCK_ADMIN_USERS),
  );
  private readonly tracksSignal = signal<readonly TrackApiDto[]>(
    readStoredArray<TrackApiDto>(STORAGE_KEYS.tracks, MOCK_ADMIN_TRACKS),
  );
  private readonly reviewsSignal = signal<readonly AdminModerationReview[]>(
    readStoredArray<AdminModerationReview>(STORAGE_KEYS.reviews, MOCK_ADMIN_REVIEWS),
  );
  private readonly remoteDashboardSignal = signal<ExecutiveDashboardApiDto | null>(null);
  private readonly remoteAudienceSignal = signal<AudienceReportApiDto | null>(null);
  private readonly toastSignal = signal<string>('');
  private readonly usingLocalFallbackSignal = signal<boolean>(this.http === null);
  private readonly fallbackReasonSignal = signal<string>(
    this.http === null
      ? 'HttpClient não injetado — operando sobre dados locais de fallback (localStorage).'
      : '',
  );

  readonly defaultAdminEmail = DEFAULT_ADMIN_EMAIL;
  readonly defaultAdminPassword = DEFAULT_ADMIN_PASSWORD;

  readonly currentAdmin = this.sessionSignal.asReadonly();
  readonly isAuthenticated = computed<boolean>(() => Boolean(this.sessionSignal()?.is_admin));
  readonly plans = this.plansSignal.asReadonly();
  readonly tracks = this.tracksSignal.asReadonly();
  readonly toastMessage = this.toastSignal.asReadonly();
  readonly isUsingLocalFallback = this.usingLocalFallbackSignal.asReadonly();
  readonly fallbackReason = this.fallbackReasonSignal.asReadonly();
  readonly dataSourceMode = computed<'api' | 'local-fallback'>(() =>
    this.usingLocalFallbackSignal() ? 'local-fallback' : 'api',
  );
  readonly dataSourceBanner = computed<string>(() =>
    this.usingLocalFallbackSignal()
      ? `MODO FALLBACK LOCAL ATIVO — ${this.fallbackReasonSignal() || 'Dados simulados em localStorage'}`
      : 'CONECTADO AO BACKEND REAL (/api/admin)',
  );

  readonly activeTracks = computed<readonly TrackApiDto[]>(() =>
    this.tracksSignal().filter((track) => !track.is_deleted),
  );

  readonly blockedTracks = computed<readonly TrackApiDto[]>(() =>
    this.tracksSignal().filter((track) => track.is_deleted),
  );

  readonly topModerationReviews = computed<readonly AdminModerationReview[]>(() =>
    [...this.reviewsSignal()]
      .filter((review) => !review.is_deleted)
      .sort((left, right) => right.likes_count - left.likes_count)
      .slice(0, 10),
  );

  readonly administrators = computed<readonly AdminAccount[]>(() =>
    this.usersSignal().filter((user) => user.is_admin),
  );

  readonly usersWithPlans = computed<readonly AdminUserPlanSummary[]>(() => {
    const planNames = new Map<number, string>(
      this.plansSignal().map((plan) => [plan.plan_id, plan.name]),
    );
    return this.usersSignal().map((user) => ({
      user_id: user.user_id,
      email: user.email,
      display_name: user.display_name,
      age: user.age,
      plan_name: planNames.get(user.plan_id) ?? 'Free',
      is_admin: user.is_admin,
    }));
  });

  private readonly planMetrics = computed(() =>
    computePlanMetrics(this.usersSignal(), this.plansSignal()),
  );

  readonly executiveDashboard = computed<ExecutiveDashboardApiDto>(
    () => this.remoteDashboardSignal() ?? this.planMetrics().dashboard,
  );

  readonly planBreakdown = computed<readonly PlanBreakdownEntry[]>(() => {
    const remote = this.remoteDashboardSignal();
    if (remote) {
      return buildBreakdownFromDashboard(remote, this.plansSignal());
    }
    return this.planMetrics().breakdown;
  });

  private readonly genreAggregation = computed(() => computeBlockedGenres(this.usersSignal()));

  readonly blockedGenreRanking = computed<readonly BlockedGenreEntry[]>(() => {
    const remote = this.remoteAudienceSignal();
    if (remote) {
      return buildBlockedGenreEntriesFromRecord(remote.blocked_genres);
    }
    return this.genreAggregation().entries;
  });

  readonly audienceReport = computed<AudienceReportApiDto>(() => {
    const remote = this.remoteAudienceSignal();
    if (remote) {
      return remote;
    }
    return {
      total_users: this.usersSignal().length,
      total_tracks: this.tracksSignal().length,
      active_tracks: this.activeTracks().length,
      blocked_genres: this.genreAggregation().record,
    };
  });

  constructor() {
    if (this.http && this.isAuthenticated()) {
      if (readAdminAuthToken()) {
        this.hydrateFromBackend();
      } else {
        this.activateLocalFallback(
          'Sessão administrativa local restaurada sem token JWT — operando em modo fallback local.',
        );
      }
    }
  }

  /** Returns true when Angular HttpClient is available for real backend calls. */
  hasHttpClient(): boolean {
    return this.http !== null;
  }

  /** Marks the store as actively using local fallback data instead of the HTTP backend. */
  private activateLocalFallback(reason: string): void {
    this.usingLocalFallbackSignal.set(true);
    this.fallbackReasonSignal.set(reason);
  }

  /** Marks the store as synchronized with the real /api/admin HTTP backend. */
  private markApiConnected(): void {
    this.usingLocalFallbackSignal.set(false);
    this.fallbackReasonSignal.set('');
  }

  /** Authenticates an administrator against POST /api/admin/login with explicit fallback when offline. */
  loginAdminWithApi(email: string, password: string): Observable<AdminSession> {
    const normalizedEmail = email.trim().toLowerCase();
    if (!this.http) {
      this.activateLocalFallback(
        'HttpClient ausente — login realizado no fallback local (localStorage).',
      );
      try {
        return of(this.loginAdminFallback(normalizedEmail, password));
      } catch (err: unknown) {
        return throwError(() => err);
      }
    }

    return this.http
      .post<AuthApiResponse>('/api/admin/login', {
        email: normalizedEmail,
        password,
      })
      .pipe(
        map((response) => {
          writeAdminAuthToken(response.access_token);
          const session: AdminSession = {
            user_id: response.user.user_id,
            email: response.user.email,
            display_name: response.user.display_name,
            is_admin: response.user.is_admin,
          };
          this.sessionSignal.set(session);
          writeStoredJson(STORAGE_KEYS.session, session);
          this.markApiConnected();
          this.hydrateFromBackend();
          this.notify(`Bem-vindo ao Console Admin, ${session.display_name}.`);
          return session;
        }),
        catchError((err: unknown) => {
          const status = (err as { status?: number })?.status;
          if (status === 401 || status === 403 || status === 400 || status === 422) {
            const apiErr = toApiError(err);
            return throwError(
              () =>
                new AdminDomainError(
                  apiErr.message || 'Credenciais inválidas.',
                  status === 403 ? 'FORBIDDEN' : 'AUTH',
                ),
            );
          }
          this.activateLocalFallback(
            'Backend /api/admin/login inacessível — usando fallback local (localStorage).',
          );
          try {
            return of(this.loginAdminFallback(normalizedEmail, password));
          } catch (fallbackErr: unknown) {
            return throwError(() => fallbackErr);
          }
        }),
      );
  }

  /** Authenticates an administrator synchronously (and syncs with POST /api/admin/login if HttpClient is present). */
  loginAdmin(email: string, password: string): AdminSession {
    const normalizedEmail = email.trim().toLowerCase();
    if (!this.http) {
      this.activateLocalFallback(
        'HttpClient não injetado — autenticação realizada via fallback local.',
      );
      return this.loginAdminFallback(normalizedEmail, password);
    }

    const session = this.loginAdminFallback(normalizedEmail, password);
    this.http
      .post<AuthApiResponse>('/api/admin/login', {
        email: normalizedEmail,
        password,
      })
      .pipe(
        tap((response) => {
          writeAdminAuthToken(response.access_token);
          const remoteSession: AdminSession = {
            user_id: response.user.user_id,
            email: response.user.email,
            display_name: response.user.display_name,
            is_admin: response.user.is_admin,
          };
          this.sessionSignal.set(remoteSession);
          writeStoredJson(STORAGE_KEYS.session, remoteSession);
          this.markApiConnected();
          this.hydrateFromBackend();
        }),
        catchError(() => {
          this.activateLocalFallback(
            'POST /api/admin/login indisponível — sessão mantida em fallback local.',
          );
          return of(null);
        }),
      )
      .subscribe();

    return session;
  }

  private loginAdminFallback(normalizedEmail: string, password: string): AdminSession {
    const account = this.usersSignal().find(
      (candidate) => candidate.email.toLowerCase() === normalizedEmail,
    );

    if (!account || account.password !== password) {
      throw new AdminDomainError('Credenciais inválidas.', 'AUTH');
    }
    if (!account.is_admin) {
      throw new AdminDomainError('Acesso restrito a administradores.', 'FORBIDDEN');
    }

    const session: AdminSession = {
      user_id: account.user_id,
      email: account.email,
      display_name: account.display_name,
      is_admin: true,
    };
    this.sessionSignal.set(session);
    writeStoredJson(STORAGE_KEYS.session, session);
    this.notify(`Bem-vindo ao Console Admin, ${account.display_name}.`);
    return session;
  }

  /** Loads all administrative projections from /api/admin/* endpoints into reactive signals. */
  hydrateFromBackend(): void {
    if (!this.http) {
      this.activateLocalFallback('HttpClient não injetado — impossível hidratar de /api/admin.');
      return;
    }

    forkJoin({
      plans: this.http.get<readonly PlanApiDto[]>('/api/admin/plans'),
      dashboard: this.http.get<ExecutiveDashboardApiDto>('/api/admin/dashboard'),
      audience: this.http.get<AudienceReportApiDto>('/api/admin/audience'),
      users: this.http.get<readonly AdminUserPlanSummary[]>('/api/admin/users'),
      admins: this.http.get<readonly UserApiDto[]>('/api/admin/administrators'),
      activeTracks: this.http
        .get<readonly TrackApiDto[]>('/api/tracks/search', {
          params: new HttpParams().set('limit', '100'),
          context: createAdminHttpContext(),
        })
        .pipe(catchError(() => of(this.activeTracks()))),
      blockedTracks: this.http.get<readonly TrackApiDto[]>('/api/admin/blocked-tracks'),
      reviews: this.http.get<readonly ReviewApiDto[]>('/api/admin/reviews'),
    }).subscribe({
      next: (payload) => {
        this.markApiConnected();
        if (payload.plans.length > 0) {
          this.plansSignal.set(payload.plans);
          writeStoredJson(STORAGE_KEYS.plans, payload.plans);
        }
        this.remoteDashboardSignal.set(payload.dashboard);
        this.remoteAudienceSignal.set(payload.audience);
        this.applyBackendUsersAndAdmins(payload.users, payload.admins, payload.plans);
        this.applyBackendTracks(payload.activeTracks, payload.blockedTracks);
        this.applyBackendReviews(payload.reviews);
      },
      error: () => {
        this.activateLocalFallback(
          'Falha ao sincronizar com /api/admin/* — exibindo dados de fallback local.',
        );
      },
    });
  }

  private applyBackendUsersAndAdmins(
    userSummaries: readonly AdminUserPlanSummary[],
    adminDtos: readonly UserApiDto[],
    plans: readonly PlanApiDto[],
  ): void {
    const planIdByName = new Map<string, number>(
      plans.map((plan) => [plan.name.toLowerCase(), plan.plan_id]),
    );
    const adminById = new Map<number, UserApiDto>(adminDtos.map((admin) => [admin.user_id, admin]));
    const existingById = new Map<number, AdminAccount>(
      this.usersSignal().map((user) => [user.user_id, user]),
    );

    const merged: AdminAccount[] = userSummaries.map((summary) =>
      mergeAdminAccountFromSummary(summary, planIdByName, adminById, existingById),
    );

    if (merged.length > 0) {
      this.usersSignal.set(merged);
      writeStoredJson(STORAGE_KEYS.users, merged);
    }
  }

  private applyBackendTracks(
    activeTracks: readonly TrackApiDto[],
    blockedTracks: readonly TrackApiDto[],
  ): void {
    const byId = new Map<number, TrackApiDto>();
    for (const track of activeTracks) {
      byId.set(track.track_id, { ...track, is_deleted: false });
    }
    for (const track of blockedTracks) {
      byId.set(track.track_id, { ...track, is_deleted: true });
    }
    const combined = [...byId.values()];
    if (combined.length > 0) {
      this.tracksSignal.set(combined);
      writeStoredJson(STORAGE_KEYS.tracks, combined);
    }
  }

  private applyBackendReviews(reviewDtos: readonly ReviewApiDto[]): void {
    const userById = new Map<number, AdminAccount>(
      this.usersSignal().map((user) => [user.user_id, user]),
    );
    const trackById = new Map<number, TrackApiDto>(
      this.tracksSignal().map((track) => [track.track_id, track]),
    );

    const mapped: AdminModerationReview[] = reviewDtos.map((dto, index) => {
      const author = userById.get(dto.user_id);
      const track = trackById.get(dto.track_id);
      return {
        review_id: dto.review_id ?? index + 1,
        user_id: dto.user_id,
        author_name: author?.display_name ?? `Usuário #${dto.user_id}`,
        track_id: dto.track_id,
        track_title: track?.title ?? `Faixa #${dto.track_id}`,
        track_artist: track?.artist ?? 'Artista do Catálogo',
        rating: dto.rating,
        text: dto.text ?? '',
        likes_count: dto.likes_count,
        created_at: dto.created_at ?? new Date().toISOString(),
        is_deleted: dto.is_deleted,
      };
    });

    this.reviewsSignal.set(mapped);
    writeStoredJson(STORAGE_KEYS.reviews, mapped);
  }

  /** Clears the active administrative session and token. */
  logoutAdmin(): void {
    this.sessionSignal.set(null);
    this.remoteDashboardSignal.set(null);
    this.remoteAudienceSignal.set(null);
    removeStoredKey(STORAGE_KEYS.session);
    clearAdminAuthToken();
    this.notify('Sessão administrativa encerrada.');
  }

  /** Promotes a user to administrator via PUT /api/admin/administrators/{id} with fallback. */
  promoteUserToAdmin(userId: number): AdminAccount {
    return this.updateAdminRole(userId, true);
  }

  /** Updates administrator privileges via PUT /api/admin/administrators/{id} with explicit fallback. */
  updateAdminRole(targetUserId: number, isAdmin: boolean): AdminAccount {
    const activeAdminId = this.sessionSignal()?.user_id;
    if (activeAdminId === targetUserId && !isAdmin) {
      throw new AdminDomainError('Administrador não pode revogar o próprio acesso.', 'RULE');
    }

    const updated = this.setUserAdminFlag(targetUserId, isAdmin);
    if (!this.http) {
      this.activateLocalFallback(
        'HttpClient não injetado — permissão de admin alterada apenas no fallback local.',
      );
      return updated;
    }

    this.http
      .put<UserApiDto>(`/api/admin/administrators/${targetUserId}`, {
        is_admin: isAdmin,
      })
      .subscribe({
        next: (remoteUser) => {
          this.markApiConnected();
          this.setUserAdminFlag(remoteUser.user_id, remoteUser.is_admin, false);
        },
        error: () => {
          this.activateLocalFallback(
            `Falha em PUT /api/admin/administrators/${targetUserId} — mantido no fallback local.`,
          );
        },
      });

    return updated;
  }

  /** Updates plan pricing, name, or profile limits via PUT /api/admin/plans/{id} with explicit fallback. */
  updatePlan(planId: number, payload: UpdateAdminPlanPayload): PlanApiDto {
    const currentPlans = this.plansSignal();
    const existingPlan = currentPlans.find((item) => item.plan_id === planId);
    if (!existingPlan) {
      throw new AdminDomainError(`Plano ${planId} não encontrado.`, 'NOT_FOUND');
    }

    const resolvedName =
      payload.new_name !== undefined
        ? this.validatePlanName(planId, payload.new_name)
        : existingPlan.name;
    const resolvedPrice =
      payload.new_price !== undefined
        ? this.validatePlanPrice(payload.new_price)
        : existingPlan.monthly_price;
    const resolvedMaxProfiles =
      payload.max_profiles !== undefined
        ? this.validateMaxProfiles(planId, payload.max_profiles)
        : existingPlan.max_profiles;

    const updatedPlan: PlanApiDto = {
      plan_id: planId,
      name: resolvedName,
      monthly_price: resolvedPrice,
      max_profiles: resolvedMaxProfiles,
    };

    const nextPlans = currentPlans.map((item) => (item.plan_id === planId ? updatedPlan : item));
    this.plansSignal.set(nextPlans);
    this.remoteDashboardSignal.set(null);
    writeStoredJson(STORAGE_KEYS.plans, nextPlans);
    this.notify(`Plano "${updatedPlan.name}" atualizado com sucesso.`);

    if (!this.http) {
      this.activateLocalFallback(
        'HttpClient não injetado — plano atualizado apenas no fallback local.',
      );
      return updatedPlan;
    }

    this.http
      .put<PlanApiDto>(`/api/admin/plans/${planId}`, {
        new_name: resolvedName,
        new_price: resolvedPrice,
        max_profiles: resolvedMaxProfiles,
      })
      .subscribe({
        next: (remotePlan) => {
          this.markApiConnected();
          const syncedPlans = this.plansSignal().map((item) =>
            item.plan_id === planId ? remotePlan : item,
          );
          this.plansSignal.set(syncedPlans);
          writeStoredJson(STORAGE_KEYS.plans, syncedPlans);
        },
        error: () => {
          this.activateLocalFallback(
            `Falha em PUT /api/admin/plans/${planId} — alteração mantida no fallback local.`,
          );
        },
      });

    return updatedPlan;
  }

  /** Filters active catalog tracks locally and optionally queries GET /api/tracks/search. */
  searchCatalogTracks(query: string): readonly TrackApiDto[] {
    const term = query.trim().toLowerCase();
    const active = this.activeTracks();
    if (!term) return active;
    return active.filter(
      (track) =>
        track.title.toLowerCase().includes(term) ||
        track.artist.toLowerCase().includes(term) ||
        track.genre.toLowerCase().includes(term) ||
        (track.album?.toLowerCase().includes(term) ?? false),
    );
  }

  /** Queries GET /api/tracks/search on the backend and merges results into the admin track store. */
  fetchCatalogTracksFromBackend(query: string): Observable<readonly TrackApiDto[]> {
    if (!this.http) {
      this.activateLocalFallback(
        'HttpClient não injetado — busca de catálogo executada no fallback local.',
      );
      return of(this.searchCatalogTracks(query));
    }

    let params = new HttpParams().set('limit', '50');
    const trimmed = query.trim();
    if (trimmed) {
      params = params.set('query', trimmed);
    }

    return this.http
      .get<readonly TrackApiDto[]>('/api/tracks/search', {
        params,
        context: createAdminHttpContext(),
      })
      .pipe(
        tap((remoteTracks) => {
          this.markApiConnected();
          if (trimmed.length > 0) {
            const mergedActive = new Map<number, TrackApiDto>(
              this.activeTracks().map((track) => [track.track_id, track]),
            );
            for (const track of remoteTracks) {
              mergedActive.set(track.track_id, { ...track, is_deleted: false });
            }
            this.applyBackendTracks([...mergedActive.values()], this.blockedTracks());
          } else {
            this.applyBackendTracks(remoteTracks, this.blockedTracks());
          }
        }),
        catchError(() => {
          this.activateLocalFallback(
            'Falha em GET /api/tracks/search — usando busca no fallback local.',
          );
          return of(this.searchCatalogTracks(query));
        }),
      );
  }

  /** Blocks or restores a catalog track via PUT /api/admin/tracks/{id}/block with explicit fallback. */
  setTrackBlocked(trackId: number, blocked: boolean): TrackApiDto {
    const updated = this.mutateTrack(trackId, (track) => ({ ...track, is_deleted: blocked }));
    this.remoteAudienceSignal.set(null);
    this.notify(
      blocked
        ? `Faixa "${updated.title}" bloqueada no catálogo.`
        : `Faixa "${updated.title}" restaurada ao catálogo ativo.`,
    );

    if (!this.http) {
      this.activateLocalFallback(
        'HttpClient não injetado — bloqueio de faixa aplicado no fallback local.',
      );
      return updated;
    }

    this.http
      .put<TrackBlockApiDto>(`/api/admin/tracks/${trackId}/block`, {
        blocked,
      })
      .subscribe({
        next: (response) => {
          this.markApiConnected();
          this.mutateTrack(trackId, (track) => ({ ...track, is_deleted: response.blocked }));
        },
        error: () => {
          this.activateLocalFallback(
            `Falha em PUT /api/admin/tracks/${trackId}/block — mantido no fallback local.`,
          );
        },
      });

    return updated;
  }

  /** Updates explicit advisory flag via PUT /api/admin/tracks/{id}/explicit with explicit fallback. */
  setTrackExplicit(trackId: number, explicit: boolean): TrackApiDto {
    const updated = this.mutateTrack(trackId, (track) => ({ ...track, explicit }));
    this.notify(
      explicit
        ? `Selo +18 ativado em "${updated.title}".`
        : `Selo +18 removido de "${updated.title}".`,
    );

    if (!this.http) {
      this.activateLocalFallback(
        'HttpClient não injetado — selo +18 atualizado no fallback local.',
      );
      return updated;
    }

    this.http
      .put<TrackExplicitApiDto>(`/api/admin/tracks/${trackId}/explicit`, {
        explicit,
      })
      .subscribe({
        next: (response) => {
          this.markApiConnected();
          this.mutateTrack(trackId, (track) => ({ ...track, explicit: response.explicit }));
        },
        error: () => {
          this.activateLocalFallback(
            `Falha em PUT /api/admin/tracks/${trackId}/explicit — mantido no fallback local.`,
          );
        },
      });

    return updated;
  }

  /** Updates track genre via PUT /api/admin/tracks/{id}/genre with explicit fallback to local mock. */
  updateTrackGenre(trackId: number, genre: string): Observable<TrackGenreApiResponse> {
    const trimmedGenre = genre.trim();
    if (!trimmedGenre) {
      throw new AdminDomainError('O gênero da faixa é obrigatório.', 'RULE');
    }

    const fallbackAction = (reason: string): TrackGenreApiResponse => {
      this.activateLocalFallback(reason);
      this.mutateTrack(trackId, (track) => ({ ...track, genre: trimmedGenre }));
      this.notify(`Gênero da faixa #${trackId} atualizado para "${trimmedGenre}".`);
      return { track_id: trackId, genre: trimmedGenre };
    };

    if (!this.http) {
      return of(fallbackAction('HttpClient não injetado — gênero atualizado no fallback local.'));
    }

    return this.http
      .put<TrackGenreApiResponse>(`/api/admin/tracks/${trackId}/genre`, {
        genre: trimmedGenre,
      })
      .pipe(
        tap((response) => {
          this.markApiConnected();
          this.mutateTrack(trackId, (track) => ({ ...track, genre: response.genre }));
          this.notify(`Gênero da faixa #${trackId} atualizado para "${response.genre}".`);
        }),
        catchError(() => {
          return of(
            fallbackAction(
              `Falha em PUT /api/admin/tracks/${trackId}/genre — atualizado no fallback local.`,
            ),
          );
        }),
      );
  }

  /** Triggers catalog delta-table compaction via POST /api/admin/catalog/compact with explicit fallback. */
  compactCatalog(): Observable<CompactCatalogApiResponse> {
    const fallbackAction = (reason: string): CompactCatalogApiResponse => {
      this.activateLocalFallback(reason);
      const fallbackRes: CompactCatalogApiResponse = {
        new_version: Date.now(),
        message: 'Catálogo compactado com sucesso (Delta Tables — Fallback Local).',
      };
      this.notify(fallbackRes.message);
      return fallbackRes;
    };

    if (!this.http) {
      return of(
        fallbackAction('HttpClient não injetado — compactação simulada no fallback local.'),
      );
    }

    return this.http.post<CompactCatalogApiResponse>('/api/admin/catalog/compact', {}).pipe(
      tap((response) => {
        this.markApiConnected();
        this.notify(response.message || 'Catálogo compactado com sucesso.');
      }),
      catchError(() => {
        return of(
          fallbackAction(
            'Falha em POST /api/admin/catalog/compact — compactação simulada no fallback local.',
          ),
        );
      }),
    );
  }

  /** Synchronizes catalog delta tables via POST /api/admin/catalog/sync with explicit fallback. */
  syncCatalog(force = false): Observable<SyncCatalogVersionApiResponse> {
    const fallbackAction = (reason: string): SyncCatalogVersionApiResponse => {
      this.activateLocalFallback(reason);
      const fallbackRes: SyncCatalogVersionApiResponse = {
        synced: true,
        version: Date.now(),
        message: 'Catálogo sincronizado com sucesso (Fallback Local).',
      };
      this.notify(fallbackRes.message);
      return fallbackRes;
    };

    if (!this.http) {
      return of(
        fallbackAction('HttpClient não injetado — sincronização simulada no fallback local.'),
      );
    }

    return this.http
      .post<SyncCatalogVersionApiResponse>(`/api/admin/catalog/sync?force=${force}`, {})
      .pipe(
        tap((response) => {
          this.markApiConnected();
          this.notify(response.message || 'Catálogo sincronizado com sucesso.');
        }),
        catchError(() => {
          return of(
            fallbackAction(
              'Falha em POST /api/admin/catalog/sync — sincronização simulada no fallback local.',
            ),
          );
        }),
      );
  }

  /** Soft-deletes an abusive review via DELETE /api/reviews/{id} with explicit fallback. */
  deleteReview(reviewId: number): void {
    const current = this.reviewsSignal();
    const target = current.find((item) => item.review_id === reviewId && !item.is_deleted);
    if (!target) {
      throw new AdminDomainError(`Avaliação ${reviewId} não encontrada.`, 'NOT_FOUND');
    }

    const next = current.map((item) =>
      item.review_id === reviewId ? { ...item, is_deleted: true } : item,
    );
    this.reviewsSignal.set(next);
    writeStoredJson(STORAGE_KEYS.reviews, next);
    this.notify(`Avaliação #${reviewId} removida pela moderação.`);

    if (!this.http) {
      this.activateLocalFallback(
        'HttpClient não injetado — avaliação removida apenas no fallback local.',
      );
      return;
    }

    this.http
      .delete<{ readonly success: boolean }>(`/api/reviews/${reviewId}`, {
        context: createAdminHttpContext(),
      })
      .subscribe({
        next: () => {
          this.markApiConnected();
        },
        error: () => {
          this.activateLocalFallback(
            `Falha em DELETE /api/reviews/${reviewId} — remoção mantida no fallback local.`,
          );
        },
      });
  }

  /** Restores all administrative mock datasets to their factory seed state and activates local fallback mode. */
  resetDemoData(): void {
    this.activateLocalFallback('Dados de demonstração restaurados manualmente pelo administrador.');
    this.remoteDashboardSignal.set(null);
    this.remoteAudienceSignal.set(null);
    this.plansSignal.set(MOCK_ADMIN_PLANS);
    this.usersSignal.set(MOCK_ADMIN_USERS);
    this.tracksSignal.set(MOCK_ADMIN_TRACKS);
    this.reviewsSignal.set(MOCK_ADMIN_REVIEWS);
    writeStoredJson(STORAGE_KEYS.plans, MOCK_ADMIN_PLANS);
    writeStoredJson(STORAGE_KEYS.users, MOCK_ADMIN_USERS);
    writeStoredJson(STORAGE_KEYS.tracks, MOCK_ADMIN_TRACKS);
    writeStoredJson(STORAGE_KEYS.reviews, MOCK_ADMIN_REVIEWS);
    this.notify('Dados de demonstração do painel restaurados.');
  }

  /** Displays a transient feedback toast inside the admin console. */
  notify(message: string): void {
    this.toastSignal.set(message);
    setTimeout(() => {
      if (this.toastSignal() === message) {
        this.toastSignal.set('');
      }
    }, 3400);
  }

  /** Dismisses the active admin toast banner immediately. */
  clearToast(): void {
    this.toastSignal.set('');
  }

  /** Returns the maximum occupied profiles among titular subscribers of a plan. */
  getOccupiedProfilesForPlan(planId: number): number {
    const allUsers = this.usersSignal();
    let maxOccupied = 1;
    for (const holder of allUsers) {
      if (holder.plan_id !== planId || holder.primary_account_id !== undefined) continue;
      const dependents = allUsers.filter((dep) => dep.primary_account_id === holder.user_id).length;
      if (dependents + 1 > maxOccupied) {
        maxOccupied = dependents + 1;
      }
    }
    return maxOccupied;
  }

  private setUserAdminFlag(userId: number, isAdmin: boolean, shouldNotify = true): AdminAccount {
    const currentUsers = this.usersSignal();
    const found = currentUsers.find((user) => user.user_id === userId);
    if (!found) {
      throw new AdminDomainError(`Usuário com ID ${userId} não encontrado.`, 'NOT_FOUND');
    }

    const updatedUser: AdminAccount = { ...found, is_admin: isAdmin };
    const nextUsers = currentUsers.map((user) => (user.user_id === userId ? updatedUser : user));
    this.usersSignal.set(nextUsers);
    writeStoredJson(STORAGE_KEYS.users, nextUsers);
    if (shouldNotify) {
      this.notify(
        isAdmin
          ? `${updatedUser.display_name} agora possui acesso administrativo.`
          : `Acesso administrativo de ${updatedUser.display_name} revogado.`,
      );
    }
    return updatedUser;
  }

  private validatePlanName(planId: number, rawName: string): string {
    const cleaned = rawName.trim();
    if (!cleaned) {
      throw new AdminDomainError('O nome do plano é obrigatório.', 'RULE');
    }
    const duplicate = this.plansSignal().some(
      (plan) => plan.plan_id !== planId && plan.name.toLowerCase() === cleaned.toLowerCase(),
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

  private validateMaxProfiles(planId: number, maxProfiles: number): number {
    if (!Number.isFinite(maxProfiles) || !Number.isInteger(maxProfiles) || maxProfiles < 1) {
      throw new AdminDomainError('O limite de perfis deve ser de pelo menos 1.', 'RULE');
    }
    const occupied = this.getOccupiedProfilesForPlan(planId);
    if (maxProfiles < occupied) {
      throw new AdminDomainError(
        'O limite não pode ser menor que os perfis já vinculados.',
        'RULE',
      );
    }
    return maxProfiles;
  }

  private mutateTrack(trackId: number, updater: (track: TrackApiDto) => TrackApiDto): TrackApiDto {
    const current = this.tracksSignal();
    const target = current.find((item) => item.track_id === trackId);
    if (!target) {
      throw new AdminDomainError(`Faixa ${trackId} não encontrada.`, 'NOT_FOUND');
    }
    const updated = updater(target);
    const next = current.map((item) => (item.track_id === trackId ? updated : item));
    this.tracksSignal.set(next);
    writeStoredJson(STORAGE_KEYS.tracks, next);
    return updated;
  }
}
