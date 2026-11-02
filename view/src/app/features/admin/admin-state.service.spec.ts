import { beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD } from './admin.mock';
import { AdminDomainError, AdminStateService } from './admin-state.service';

describe('AdminStateService', () => {
  let service: AdminStateService;

  beforeEach(() => {
    localStorage.clear();
    service = new AdminStateService();
  });

  it('authenticates valid admin credentials and persists isolated session', () => {
    expect(service.isAuthenticated()).toBe(false);

    const session = service.loginAdmin(DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD);

    expect(session.is_admin).toBe(true);
    expect(service.isAuthenticated()).toBe(true);
    expect(localStorage.getItem('ribbit-admin-session')).toContain(DEFAULT_ADMIN_EMAIL);

    const reloaded = new AdminStateService();
    expect(reloaded.currentAdmin()?.email).toBe(DEFAULT_ADMIN_EMAIL);

    reloaded.logoutAdmin();
    expect(reloaded.isAuthenticated()).toBe(false);
  });

  it('rejects wrong password and non-admin accounts on login', () => {
    expect(() => service.loginAdmin(DEFAULT_ADMIN_EMAIL, 'wrong-pass')).toThrowError(
      AdminDomainError,
    );
    expect(() => service.loginAdmin('joao.lucas@ribbit.app', 'RibbitUser123!')).toThrow(
      'Acesso restrito a administradores.',
    );
  });

  it('computes executive dashboard and audience metrics excluding family dependents from net revenue', () => {
    const dashboard = service.executiveDashboard();
    // 8 users total; titulars on paid plans: 3 Individual (3 * 14.9 = 44.7) + 1 Família (27.9) = 72.6
    expect(dashboard.total_users).toBe(8);
    expect(dashboard.estimated_net_revenue).toBe(72.6);
    expect(dashboard.users_by_plan['Família']).toBe(3);
    expect(dashboard.revenue_by_plan['Família']).toBe(27.9);

    const audience = service.audienceReport();
    expect(audience.total_tracks).toBe(7);
    expect(audience.active_tracks).toBe(5);
    expect(audience.blocked_genres['Sertanejo']).toBe(4);
  });

  it('promotes users to admin and prevents administrator self-demotion', () => {
    service.loginAdmin(DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD);

    const promoted = service.promoteUserToAdmin(3);
    expect(promoted.is_admin).toBe(true);
    expect(service.administrators().some((admin) => admin.user_id === 3)).toBe(true);

    expect(() => service.updateAdminRole(1, false)).toThrow(
      'Administrador não pode revogar o próprio acesso.',
    );

    const demoted = service.updateAdminRole(2, false);
    expect(demoted.is_admin).toBe(false);
  });

  it('updates plans and enforces unique name, non-negative price, and dependent capacity', () => {
    const updated = service.updatePlan(2, {
      new_name: 'Ribbit Individual Plus',
      new_price: 16.9,
      max_profiles: 2,
    });
    expect(updated.name).toBe('Ribbit Individual Plus');
    expect(updated.monthly_price).toBe(16.9);
    expect(service.executiveDashboard().estimated_net_revenue).toBe(78.6);

    expect(() => service.updatePlan(2, { new_name: '   ' })).toThrow(
      'O nome do plano é obrigatório.',
    );
    expect(() => service.updatePlan(2, { new_name: 'Free' })).toThrow(
      'Já existe um plano com esse nome.',
    );
    expect(() => service.updatePlan(2, { new_price: -5 })).toThrow(
      'O preço mensal não pode ser negativo.',
    );
    // Plan 3 (Família) has Carolina + 2 dependents = 3 occupied profiles
    expect(() => service.updatePlan(3, { max_profiles: 2 })).toThrow(
      'O limite não pode ser menor que os perfis já vinculados.',
    );
  });

  it('searches active tracks, toggles block/explicit flags, deletes reviews, and resets demo state', () => {
    expect(service.searchCatalogTracks('Liniker').length).toBe(1);

    service.setTrackBlocked(103, true);
    expect(service.blockedTracks().some((track) => track.track_id === 103)).toBe(true);
    expect(service.searchCatalogTracks('Liniker').length).toBe(0);

    service.setTrackExplicit(101, true);
    expect(service.activeTracks().find((track) => track.track_id === 101)?.explicit).toBe(true);

    const initialReviews = service.topModerationReviews().length;
    service.deleteReview(503);
    expect(service.topModerationReviews().length).toBe(initialReviews - 1);

    service.resetDemoData();
    expect(service.topModerationReviews().length).toBe(initialReviews);
    expect(service.activeTracks().length).toBe(5);
  });
});
