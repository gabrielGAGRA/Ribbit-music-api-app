import { HttpClient, HttpParams } from '@angular/common/http';
import type { OnDestroy } from '@angular/core';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { Observable, Subscription } from 'rxjs';
import { forkJoin, throwError } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';
import type {
  ActionSuccessApiDto,
  AdminModerationReview,
  AdminSession,
  AdminTrackAccessEntry,
  AdminUserPlanSummary,
  AudienceReportApiDto,
  AuthApiResponse,
  BlockedGenreEntry,
  CompactCatalogApiResponse,
  ExecutiveDashboardApiDto,
  GenreAccessCountApiDto,
  PlanApiDto,
  PlanBreakdownEntry,
  PlatformCostSettingsApiDto,
  RegisterAdminApiRequest,
  ReviewApiDto,
  SyncCatalogVersionApiResponse,
  TrackAccessRankApiDto,
  TrackApiDto,
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

export interface AdminTrackItem extends TrackApiDto {
  readonly likes_count: number;
  readonly dislikes_count: number;
  readonly superlikes_count: number;
  readonly average_rating?: number | null;
  readonly review_count?: number;
}

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

function normalizeAdminTrack(track: Partial<AdminTrackItem> & TrackApiDto): AdminTrackItem {
  return {
    ...track,
    likes_count: track.likes_count ?? 0,
    dislikes_count: track.dislikes_count ?? 0,
    superlikes_count: track.superlikes_count ?? 0,
    average_rating: track.average_rating ?? null,
    review_count: track.review_count ?? 0,
  };
}

const ADMIN_SESSION_STORAGE_KEY = 'ribbit-admin-session';
const LEGACY_ADMIN_STORAGE_KEYS: readonly string[] = [
  'ribbit-admin-plans',
  'ribbit-admin-users',
  'ribbit-admin-tracks',
  'ribbit-admin-reviews',
];

const EMPTY_DASHBOARD: ExecutiveDashboardApiDto = {
  total_users: 0,
  estimated_net_revenue: 0,
  users_by_plan: {},
  revenue_by_plan: {},
};

const EMPTY_AUDIENCE: AudienceReportApiDto = {
  total_users: 0,
  total_tracks: 0,
  active_tracks: 0,
  blocked_genres: {},
};

/** Represents a domain, validation, or API error in the administrative console. */
export class AdminDomainError extends Error {
  readonly code: 'AUTH' | 'FORBIDDEN' | 'NOT_FOUND' | 'RULE' | 'DUPLICATE' | 'API';

  constructor(
    message: string,
    code: 'AUTH' | 'FORBIDDEN' | 'NOT_FOUND' | 'RULE' | 'DUPLICATE' | 'API' = 'RULE',
  ) {
    super(message);
    this.name = 'AdminDomainError';
    this.code = code;
  }
}

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

function isValidAdminSession(parsed: unknown): parsed is AdminSession {
  if (typeof parsed !== 'object' || parsed === null) return false;
  if (
    !('user_id' in parsed && 'email' in parsed && 'display_name' in parsed && 'is_admin' in parsed)
  ) {
    return false;
  }
  return Boolean((parsed as AdminSession).is_admin);
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
    return isValidAdminSession(parsed) ? parsed : null;
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
  dashboard: ExecutiveDashboardApiDto,
  plans: readonly PlanApiDto[],
): readonly PlanBreakdownEntry[] {
  const totalUsers = dashboard.total_users;
  const planRevenueSum = Object.values(dashboard.revenue_by_plan).reduce(
    (sum, value) => sum + value,
    0,
  );
  const grossRevenue = dashboard.gross_revenue ?? planRevenueSum;
  return plans.map((plan) => {
    const count = dashboard.users_by_plan[plan.name] ?? 0;
    const rev = Math.round((dashboard.revenue_by_plan[plan.name] ?? 0) * 100) / 100;
    return {
      planName: plan.name,
      userCount: count,
      userPercent: toPercent(count, totalUsers),
      revenue: rev,
      revenuePercent: toPercent(rev, grossRevenue),
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

function resolveReviewTrackMeta(
  dto: ReviewApiDto,
  track: TrackApiDto | undefined,
): { readonly title: string; readonly artist: string } {
  return {
    title: dto.track_title ?? track?.title ?? `Faixa #${dto.track_id}`,
    artist: dto.track_artist ?? track?.artist ?? 'Artista do Catálogo',
  };
}

function mapModerationReview(
  dto: ReviewApiDto,
  index: number,
  userById: ReadonlyMap<number, AdminUserPlanSummary>,
  trackById: ReadonlyMap<number, TrackApiDto>,
): AdminModerationReview {
  const author = userById.get(dto.user_id);
  const trackMeta = resolveReviewTrackMeta(dto, trackById.get(dto.track_id));
  return {
    review_id: dto.review_id ?? index + 1,
    user_id: dto.user_id,
    author_name: dto.author_name ?? author?.display_name ?? `Usuário #${dto.user_id}`,
    track_id: dto.track_id,
    track_title: trackMeta.title,
    track_artist: trackMeta.artist,
    rating: dto.rating,
    text: dto.text ?? '',
    likes_count: dto.likes_count,
    created_at: dto.created_at ?? '',
    is_deleted: dto.is_deleted,
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
  private readonly plansSignal = signal<readonly PlanApiDto[]>([]);
  private readonly usersSignal = signal<readonly AdminUserPlanSummary[]>([]);
  private readonly administratorsSignal = signal<readonly UserApiDto[]>([]);
  private readonly activeTracksSignal = signal<readonly AdminTrackItem[]>([]);
  private readonly blockedTracksSignal = signal<readonly AdminTrackItem[]>([]);
  private readonly reviewsSignal = signal<readonly AdminModerationReview[]>([]);
  private readonly dashboardSignal = signal<ExecutiveDashboardApiDto>(EMPTY_DASHBOARD);
  private readonly audienceSignal = signal<AudienceReportApiDto>(EMPTY_AUDIENCE);
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
  readonly isAuthenticated = computed<boolean>(() => Boolean(this.sessionSignal()?.is_admin));
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
      .filter((review) => !review.is_deleted)
      .sort((left, right) => right.likes_count - left.likes_count)
      .slice(0, 10),
  );

  readonly planBreakdown = computed<readonly PlanBreakdownEntry[]>(() =>
    buildBreakdownFromDashboard(this.dashboardSignal(), this.plansSignal()),
  );

  readonly blockedGenreRanking = computed<readonly BlockedGenreEntry[]>(() =>
    buildBlockedGenreEntries(this.audienceSignal().blocked_genres),
  );

  readonly accessesByGenreRanking = computed<
    readonly (GenreAccessCountApiDto & { readonly percent: number })[]
  >(() => {
    const list = this.audienceSignal().accesses_by_genre ?? [];
    const maxCount = list[0]?.access_count ?? 0;
    return list.map((item) => ({
      ...item,
      percent: maxCount > 0 ? Math.round((item.access_count / maxCount) * 100) : 0,
    }));
  });

  readonly topAccessedTracks = computed<
    readonly (TrackAccessRankApiDto & { readonly percent: number })[]
  >(() => {
    const list = this.audienceSignal().accesses_by_track ?? [];
    const maxCount = list[0]?.access_count ?? 0;
    return list.map((item) => ({
      ...item,
      percent: maxCount > 0 ? Math.round((item.access_count / maxCount) * 100) : 0,
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
            user_id: response.user.user_id,
            email: response.user.email,
            display_name: response.user.display_name,
            is_admin: response.user.is_admin,
          };
          this.sessionSignal.set(session);
          writeStoredSession(session);
          this.hydrateFromBackend();
          this.notify(`Bem-vindo ao Console Admin, ${session.display_name}.`);
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
      plans: this.http.get<readonly PlanApiDto[]>('/api/admin/plans'),
      dashboard: this.http.get<ExecutiveDashboardApiDto>('/api/admin/dashboard'),
      audience: this.http.get<AudienceReportApiDto>('/api/admin/audience'),
      users: this.http.get<readonly AdminUserPlanSummary[]>('/api/admin/users'),
      admins: this.http.get<readonly UserApiDto[]>('/api/admin/administrators'),
      activeTracks: this.http
        .get<readonly AdminTrackItem[]>('/api/admin/tracks', {
          params: new HttpParams().set('limit', '100'),
        })
        .pipe(map((items) => items.map((item) => normalizeAdminTrack(item)))),
      blockedTracks: this.http
        .get<readonly AdminTrackItem[]>('/api/admin/blocked-tracks')
        .pipe(map((items) => items.map((item) => normalizeAdminTrack(item)))),
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
  registerAdministrator(payload: RegisterAdminApiRequest): Observable<UserApiDto> {
    let requestBody: RegisterAdminApiRequest;
    try {
      requestBody = buildRegisterAdminPayload(payload);
    } catch (err: unknown) {
      return throwError(() => mapAdminDomainError(err));
    }

    return this.http.post<UserApiDto>('/api/admin/administrators', requestBody).pipe(
      tap((createdAdmin) => {
        this.administratorsSignal.update((current) => [
          ...current.filter((admin) => admin.user_id !== createdAdmin.user_id),
          createdAdmin,
        ]);
        this.refreshUsersAndMetrics();
        this.notify(`Administrador "${createdAdmin.display_name}" cadastrado com sucesso.`);
      }),
      catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
    );
  }

  /** Promotes an existing user to administrator via PUT /api/admin/administrators/{id}. */
  promoteUserToAdmin(userId: number): Observable<UserApiDto> {
    return this.updateAdminRole(userId, true);
  }

  /** Updates administrator privileges via PUT /api/admin/administrators/{id}. */
  updateAdminRole(targetUserId: number, isAdmin: boolean): Observable<UserApiDto> {
    const activeAdminId = this.sessionSignal()?.user_id;
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
        tap((remoteUser) => {
          this.usersSignal.update((users) =>
            users.map((user) =>
              user.user_id === remoteUser.user_id
                ? { ...user, is_admin: remoteUser.is_admin }
                : user,
            ),
          );
          if (remoteUser.is_admin) {
            this.administratorsSignal.update((admins) => [
              ...admins.filter((admin) => admin.user_id !== remoteUser.user_id),
              remoteUser,
            ]);
          } else {
            this.administratorsSignal.update((admins) =>
              admins.filter((admin) => admin.user_id !== remoteUser.user_id),
            );
          }
          this.notify(
            remoteUser.is_admin
              ? `${remoteUser.display_name} agora possui acesso administrativo.`
              : `Acesso administrativo de ${remoteUser.display_name} revogado.`,
          );
        }),
        catchError((err: unknown) => throwError(() => mapAdminDomainError(err))),
      );
  }

  /** Updates plan pricing, name, or profile limits via PUT /api/admin/plans/{id}. */
  updatePlan(planId: number, payload: UpdateAdminPlanPayload): Observable<PlanApiDto> {
    const existingPlan = this.plansSignal().find((item) => item.plan_id === planId);
    if (!existingPlan) {
      return throwError(() => new AdminDomainError(`Plano ${planId} não encontrado.`, 'NOT_FOUND'));
    }

    let resolvedName = existingPlan.name;
    let resolvedPrice = existingPlan.monthly_price;
    let resolvedMaxProfiles = existingPlan.max_profiles;
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
        tap((remotePlan) => {
          this.plansSignal.update((plans) =>
            plans.map((item) => (item.plan_id === planId ? remotePlan : item)),
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
    return this.http.get<readonly AdminTrackItem[]>('/api/admin/tracks', { params }).pipe(
      map((items) => items.map((item) => normalizeAdminTrack(item))),
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

  /** Creates a new catalog track via POST /api/admin/tracks and refreshes metrics. */
  createTrack(payload: CreateAdminTrackPayload): Observable<AdminTrackItem> {
    return this.http.post<AdminTrackItem>('/api/admin/tracks', payload).pipe(
      map((item) => normalizeAdminTrack(item)),
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
                item.review_id === reviewId ? { ...item, is_deleted: true } : item,
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
    tracks: readonly TrackApiDto[],
  ): AdminModerationReview[] {
    const userById = new Map<number, AdminUserPlanSummary>(
      users.map((user) => [user.user_id, user]),
    );
    const trackById = new Map<number, TrackApiDto>(tracks.map((track) => [track.track_id, track]));

    return reviewDtos.map((dto, index) => mapModerationReview(dto, index, userById, trackById));
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
      this.http.get<readonly AdminTrackAccessEntry[]>('/api/admin/access-history', {
        params,
      }),
      (entries) => {
        this.accessHistorySignal.set(entries);
      },
    );
  }

  updatePlatformCosts(payload: UpdatePlatformCostsPayload): Observable<PlatformCostSettingsApiDto> {
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
      tap(() => {
        this.notify('Custos operacionais atualizados com sucesso.');
        this.runBackgroundRefresh(
          this.http.get<ExecutiveDashboardApiDto>('/api/admin/dashboard'),
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
        users: this.http.get<readonly AdminUserPlanSummary[]>('/api/admin/users'),
        dashboard: this.http.get<ExecutiveDashboardApiDto>('/api/admin/dashboard'),
        audience: this.http.get<AudienceReportApiDto>('/api/admin/audience'),
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
        dashboard: this.http.get<ExecutiveDashboardApiDto>('/api/admin/dashboard'),
        users: this.http.get<readonly AdminUserPlanSummary[]>('/api/admin/users'),
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
        audience: this.http.get<AudienceReportApiDto>('/api/admin/audience'),
        dashboard: this.http.get<ExecutiveDashboardApiDto>('/api/admin/dashboard'),
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
          .get<readonly AdminTrackItem[]>('/api/admin/tracks', {
            params: new HttpParams().set('limit', '100'),
          })
          .pipe(map((items) => items.map((item) => normalizeAdminTrack(item)))),
        blockedTracks: this.http
          .get<readonly AdminTrackItem[]>('/api/admin/blocked-tracks')
          .pipe(map((items) => items.map((item) => normalizeAdminTrack(item)))),
        audience: this.http.get<AudienceReportApiDto>('/api/admin/audience'),
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
      const target = this.activeTracksSignal().find((track) => track.track_id === trackId);
      this.activeTracksSignal.update((tracks) =>
        tracks.filter((track) => track.track_id !== trackId),
      );
      if (target) {
        this.blockedTracksSignal.update((tracks) => [
          ...tracks.filter((track) => track.track_id !== trackId),
          { ...target, is_deleted: true },
        ]);
      }
      return;
    }

    const target = this.blockedTracksSignal().find((track) => track.track_id === trackId);
    this.blockedTracksSignal.update((tracks) =>
      tracks.filter((track) => track.track_id !== trackId),
    );
    if (target) {
      this.activeTracksSignal.update((tracks) => [
        ...tracks.filter((track) => track.track_id !== trackId),
        { ...target, is_deleted: false },
      ]);
    }
  }

  private patchTrackInLists(
    trackId: number,
    updater: (track: AdminTrackItem) => AdminTrackItem,
  ): void {
    this.activeTracksSignal.update((tracks) =>
      tracks.map((track) => (track.track_id === trackId ? updater(track) : track)),
    );
    this.blockedTracksSignal.update((tracks) =>
      tracks.map((track) => (track.track_id === trackId ? updater(track) : track)),
    );
  }

  private findTrackTitle(trackId: number): string {
    const found =
      this.activeTracksSignal().find((track) => track.track_id === trackId) ??
      this.blockedTracksSignal().find((track) => track.track_id === trackId);
    return found?.title ?? `#${trackId}`;
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

  private validateMaxProfiles(maxProfiles: number): number {
    if (!Number.isFinite(maxProfiles) || !Number.isInteger(maxProfiles) || maxProfiles < 1) {
      throw new AdminDomainError('O limite de perfis deve ser de pelo menos 1.', 'RULE');
    }
    return maxProfiles;
  }
}
