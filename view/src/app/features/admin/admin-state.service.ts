import { Injectable, computed, signal } from '@angular/core';
import type {
  AdminAccount,
  AdminModerationReview,
  AdminSession,
  AdminUserPlanSummary,
  AudienceReportApiDto,
  BlockedGenreEntry,
  ExecutiveDashboardApiDto,
  PlanApiDto,
  PlanBreakdownEntry,
  TrackApiDto,
  UpdateAdminPlanPayload,
} from '@ribbit/shared-types';
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
  const breakdown: PlanBreakdownEntry[] = [];

  for (const plan of plans) {
    const count = userCounts.get(plan.name) ?? 0;
    const rev = Math.round((planRevenues.get(plan.name) ?? 0) * 100) / 100;
    usersByPlanObj[plan.name] = count;
    revenueByPlanObj[plan.name] = rev;
    breakdown.push({
      planName: plan.name,
      userCount: count,
      userPercent: toPercent(count, totalUsers),
      revenue: rev,
      revenuePercent: toPercent(rev, roundedTotalRevenue),
    });
  }

  return {
    dashboard: {
      total_users: totalUsers,
      estimated_net_revenue: roundedTotalRevenue,
      users_by_plan: usersByPlanObj,
      revenue_by_plan: revenueByPlanObj,
    },
    breakdown,
  };
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

  const sorted = [...counts.entries()].sort((left, right) => right[1] - left[1]);
  const maxCount = sorted[0]?.[1] ?? 0;
  const record: Record<string, number> = {};
  const entries: BlockedGenreEntry[] = sorted.map(([genre, count]) => {
    record[genre] = count;
    return {
      genre,
      count,
      percent: maxCount > 0 ? Math.round((count / maxCount) * 100) : 0,
    };
  });

  return { record, entries };
}

/** Isolated reactive state store backing all /api/admin/* screens via localStorage mocks. */
@Injectable({ providedIn: 'root' })
export class AdminStateService {
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
  private readonly toastSignal = signal<string>('');

  readonly defaultAdminEmail = DEFAULT_ADMIN_EMAIL;
  readonly defaultAdminPassword = DEFAULT_ADMIN_PASSWORD;

  readonly currentAdmin = this.sessionSignal.asReadonly();
  readonly isAuthenticated = computed<boolean>(() => Boolean(this.sessionSignal()?.is_admin));
  readonly plans = this.plansSignal.asReadonly();
  readonly tracks = this.tracksSignal.asReadonly();
  readonly toastMessage = this.toastSignal.asReadonly();

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
    () => this.planMetrics().dashboard,
  );

  readonly planBreakdown = computed<readonly PlanBreakdownEntry[]>(
    () => this.planMetrics().breakdown,
  );

  private readonly genreAggregation = computed(() => computeBlockedGenres(this.usersSignal()));

  readonly blockedGenreRanking = computed<readonly BlockedGenreEntry[]>(
    () => this.genreAggregation().entries,
  );

  readonly audienceReport = computed<AudienceReportApiDto>(() => ({
    total_users: this.usersSignal().length,
    total_tracks: this.tracksSignal().length,
    active_tracks: this.activeTracks().length,
    blocked_genres: this.genreAggregation().record,
  }));

  /** Authenticates an administrator matching POST /api/admin/login semantics. */
  loginAdmin(email: string, password: string): AdminSession {
    const normalizedEmail = email.trim().toLowerCase();
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

  /** Clears the active administrative session. */
  logoutAdmin(): void {
    this.sessionSignal.set(null);
    removeStoredKey(STORAGE_KEYS.session);
    this.notify('Sessão administrativa encerrada.');
  }

  /** Promotes a user to administrator in the local mock data. */
  promoteUserToAdmin(userId: number): AdminAccount {
    return this.setUserAdminFlag(userId, true);
  }

  /** Updates administrator privileges matching PUT /api/admin/administrators/{id}. */
  updateAdminRole(targetUserId: number, isAdmin: boolean): AdminAccount {
    const activeAdminId = this.sessionSignal()?.user_id;
    if (activeAdminId === targetUserId && !isAdmin) {
      throw new AdminDomainError('Administrador não pode revogar o próprio acesso.', 'RULE');
    }
    return this.setUserAdminFlag(targetUserId, isAdmin);
  }

  /** Updates plan pricing, name, or profile limits matching PUT /api/admin/plans/{id}. */
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
    writeStoredJson(STORAGE_KEYS.plans, nextPlans);
    this.notify(`Plano "${updatedPlan.name}" atualizado com sucesso.`);
    return updatedPlan;
  }

  /** Searches active catalog tracks matching GET /api/tracks/search. */
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

  /** Blocks or restores a catalog track matching PUT /api/admin/tracks/{id}/block. */
  setTrackBlocked(trackId: number, blocked: boolean): TrackApiDto {
    const updated = this.mutateTrack(trackId, (track) => ({ ...track, is_deleted: blocked }));
    this.notify(
      blocked
        ? `Faixa "${updated.title}" bloqueada no catálogo.`
        : `Faixa "${updated.title}" restaurada ao catálogo ativo.`,
    );
    return updated;
  }

  /** Updates explicit advisory flag matching PUT /api/admin/tracks/{id}/explicit. */
  setTrackExplicit(trackId: number, explicit: boolean): TrackApiDto {
    const updated = this.mutateTrack(trackId, (track) => ({ ...track, explicit }));
    this.notify(
      explicit
        ? `Selo +18 ativado em "${updated.title}".`
        : `Selo +18 removido de "${updated.title}".`,
    );
    return updated;
  }

  /** Soft-deletes an abusive review matching DELETE /api/reviews/{id}. */
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
  }

  /** Restores all administrative mock datasets to their factory seed state. */
  resetDemoData(): void {
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

  private setUserAdminFlag(userId: number, isAdmin: boolean): AdminAccount {
    const currentUsers = this.usersSignal();
    const found = currentUsers.find((user) => user.user_id === userId);
    if (!found) {
      throw new AdminDomainError(`Usuário com ID ${userId} não encontrado.`, 'NOT_FOUND');
    }

    const updatedUser: AdminAccount = { ...found, is_admin: isAdmin };
    const nextUsers = currentUsers.map((user) => (user.user_id === userId ? updatedUser : user));
    this.usersSignal.set(nextUsers);
    writeStoredJson(STORAGE_KEYS.users, nextUsers);
    this.notify(
      isAdmin
        ? `${updatedUser.display_name} agora possui acesso administrativo.`
        : `Acesso administrativo de ${updatedUser.display_name} revogado.`,
    );
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
