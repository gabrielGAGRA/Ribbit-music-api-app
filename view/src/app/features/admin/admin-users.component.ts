import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import type { AdminAccount, AdminUserPlanSummary } from '@ribbit/shared-types';
import { safeInject } from '../../core/safe-inject';
import { IconComponent } from '../../shared/icon.component';
import { AdminStateService } from './admin-state.service';

type UsersTab = 'all' | 'admins';

/** User directory and administrator role management screen backing /api/admin/users and /api/admin/administrators. */
@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './admin-users.component.html',
  styleUrl: './admin-users.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminUsersComponent {
  protected readonly adminState = safeInject(AdminStateService, new AdminStateService());

  protected readonly activeTab = signal<UsersTab>('all');
  protected readonly searchQuery = signal<string>('');
  protected readonly selectedPlanFilter = signal<string>('all');
  protected readonly actionError = signal<string>('');

  protected readonly planFilterOptions = computed<readonly string[]>(() =>
    this.adminState.plans().map((plan) => plan.name),
  );

  protected readonly filteredUsers = computed<readonly AdminUserPlanSummary[]>(() => {
    const query = this.searchQuery().trim().toLowerCase();
    const planFilter = this.selectedPlanFilter();

    return this.adminState.usersWithPlans().filter((user) => {
      const matchesPlan = planFilter === 'all' || user.plan_name === planFilter;
      if (!matchesPlan) return false;
      if (!query) return true;
      return (
        user.display_name.toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query) ||
        user.plan_name.toLowerCase().includes(query)
      );
    });
  });

  protected readonly filteredAdministrators = computed<readonly AdminAccount[]>(() => {
    const query = this.searchQuery().trim().toLowerCase();
    const admins = this.adminState.administrators();
    if (!query) return admins;
    return admins.filter(
      (admin) =>
        admin.display_name.toLowerCase().includes(query) ||
        admin.email.toLowerCase().includes(query),
    );
  });

  protected selectTab(tab: UsersTab): void {
    this.actionError.set('');
    this.activeTab.set(tab);
  }

  protected updateSearch(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.searchQuery.set(target.value);
  }

  protected updatePlanFilter(event: Event): void {
    const target = event.target as HTMLSelectElement;
    this.selectedPlanFilter.set(target.value);
  }

  protected promoteUser(userId: number): void {
    this.actionError.set('');
    try {
      this.adminState.promoteUserToAdmin(userId);
    } catch (error: unknown) {
      this.actionError.set(error instanceof Error ? error.message : 'Falha ao promover usuário.');
    }
  }

  protected revokeAdmin(userId: number): void {
    this.actionError.set('');
    try {
      this.adminState.updateAdminRole(userId, false);
    } catch (error: unknown) {
      this.actionError.set(
        error instanceof Error ? error.message : 'Falha ao atualizar permissão.',
      );
    }
  }

  protected isCurrentSessionUser(userId: number): boolean {
    return this.adminState.currentAdmin()?.user_id === userId;
  }
}
