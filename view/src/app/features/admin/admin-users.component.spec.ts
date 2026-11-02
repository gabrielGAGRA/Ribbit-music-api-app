import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';
import { AdminStateService } from './admin-state.service';
import { AdminUsersComponent } from './admin-users.component';

describe('AdminUsersComponent', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
  });

  it('filters users by search and plan, promotes listeners, and surfaces self-demotion error', () => {
    const state = TestBed.inject(AdminStateService);
    state.loginAdmin(state.defaultAdminEmail, state.defaultAdminPassword);

    const component = TestBed.runInInjectionContext(() => new AdminUsersComponent());

    expect(component['filteredUsers']().length).toBe(8);

    component['selectedPlanFilter'].set('Família');
    expect(component['filteredUsers']().length).toBe(3);

    component['selectedPlanFilter'].set('all');
    component['searchQuery'].set('joão');
    expect(component['filteredUsers']().length).toBe(1);

    component['promoteUser'](3);
    expect(state.administrators().some((admin) => admin.user_id === 3)).toBe(true);

    component['selectTab']('admins');
    component['searchQuery'].set('');
    expect(component['filteredAdministrators']().length).toBe(3);

    component['revokeAdmin'](1);
    expect(component['actionError']()).toContain('revogar o próprio acesso');

    component['revokeAdmin'](3);
    expect(component['actionError']()).toBe('');
    expect(state.administrators().some((admin) => admin.user_id === 3)).toBe(false);
  });
});
