import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { readInputChecked, readInputValue, readSelectValue } from '@shared/dom-event-values';
import { IconComponent } from '@shared/icon.component';
import type {
  AdminAdministrator,
  AdminTrackAccessEntry,
  AdminUserPlanSummary,
} from '../admin-mappers';
import { AdminStateService } from '../admin-state.service';

type UsersTab = 'all' | 'admins' | 'access-history';

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
  protected readonly adminState = inject(AdminStateService);

  protected readonly activeTab = signal<UsersTab>('all');
  protected readonly searchQuery = signal<string>('');
  protected readonly selectedPlanFilter = signal<string>('all');
  protected readonly accessUserFilter = signal<number | null>(null);
  protected readonly accessOnlyDeleted = signal<boolean>(false);
  protected readonly actionError = signal<string>('');
  protected readonly updatingUserId = signal<number | null>(null);

  protected readonly showRegisterForm = signal<boolean>(false);
  protected readonly newAdminName = signal<string>('');
  protected readonly newAdminEmail = signal<string>('');
  protected readonly newAdminPassword = signal<string>('');
  protected readonly newAdminAge = signal<string>('30');
  protected readonly newAdminBirthDate = signal<string>('');
  protected readonly registerError = signal<string>('');
  protected readonly isRegistering = signal<boolean>(false);

  protected readonly planFilterOptions = computed<readonly string[]>(() =>
    this.adminState.plans().map((plan) => plan.name),
  );

  protected readonly filteredUsers = computed<readonly AdminUserPlanSummary[]>(() => {
    const query = this.searchQuery().trim().toLowerCase();
    const planFilter = this.selectedPlanFilter();

    return this.adminState.usersWithPlans().filter((user) => {
      const matchesPlan = planFilter === 'all' || user.planName === planFilter;
      if (!matchesPlan) return false;
      if (!query) return true;
      return (
        user.displayName.toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query) ||
        user.planName.toLowerCase().includes(query)
      );
    });
  });

  protected readonly filteredAdministrators = computed<readonly AdminAdministrator[]>(() => {
    const query = this.searchQuery().trim().toLowerCase();
    const admins = this.adminState.administrators();
    if (!query) return admins;
    return admins.filter(
      (admin) =>
        admin.displayName.toLowerCase().includes(query) ||
        admin.email.toLowerCase().includes(query),
    );
  });

  protected readonly filteredAccessHistory = computed<readonly AdminTrackAccessEntry[]>(() => {
    const query = this.searchQuery().trim().toLowerCase();
    const entries = this.adminState.accessHistory();
    if (!query) return entries;
    return entries.filter(
      (entry) =>
        entry.userDisplayName.toLowerCase().includes(query) ||
        entry.userEmail.toLowerCase().includes(query) ||
        entry.trackTitle.toLowerCase().includes(query) ||
        entry.trackArtist.toLowerCase().includes(query) ||
        entry.trackGenre.toLowerCase().includes(query) ||
        entry.source.toLowerCase().includes(query),
    );
  });

  protected selectTab(tab: UsersTab): void {
    this.actionError.set('');
    this.registerError.set('');
    this.activeTab.set(tab);
    if (tab === 'access-history') {
      this.reloadAccessHistory();
    }
  }

  protected updateAccessUserFilter(event: Event): void {
    const raw = readSelectValue(event);
    if (!raw || raw === 'all') {
      this.accessUserFilter.set(null);
    } else {
      const parsed = Number(raw);
      this.accessUserFilter.set(Number.isFinite(parsed) ? parsed : null);
    }
    this.reloadAccessHistory();
  }

  protected toggleAccessOnlyDeleted(event: Event): void {
    this.accessOnlyDeleted.set(readInputChecked(event));
    this.reloadAccessHistory();
  }

  protected formatAccessTimestamp(iso: string): string {
    const parsed = new Date(iso);
    if (Number.isNaN(parsed.getTime())) return iso;
    return parsed.toLocaleString('pt-BR');
  }

  private reloadAccessHistory(): void {
    this.adminState.loadAccessHistory({
      userId: this.accessUserFilter(),
      onlyDeleted: this.accessOnlyDeleted(),
      limit: 100,
    });
  }

  protected updateSearch(event: Event): void {
    this.searchQuery.set(readInputValue(event));
  }

  protected updatePlanFilter(event: Event): void {
    this.selectedPlanFilter.set(readSelectValue(event));
  }

  protected toggleRegisterForm(): void {
    const nextState = !this.showRegisterForm();
    this.showRegisterForm.set(nextState);
    this.registerError.set('');
    if (!nextState) {
      this.resetRegisterDrafts();
    }
  }

  protected updateNewAdminName(event: Event): void {
    this.newAdminName.set(readInputValue(event));
  }

  protected updateNewAdminEmail(event: Event): void {
    this.newAdminEmail.set(readInputValue(event));
  }

  protected updateNewAdminPassword(event: Event): void {
    this.newAdminPassword.set(readInputValue(event));
  }

  protected updateNewAdminAge(event: Event): void {
    this.newAdminAge.set(readInputValue(event));
  }

  protected updateNewAdminBirthDate(event: Event): void {
    this.newAdminBirthDate.set(readInputValue(event));
  }

  protected submitRegisterAdmin(event: Event): void {
    event.preventDefault();
    if (this.isRegistering()) return;

    this.registerError.set('');
    const parsedAge = Number(this.newAdminAge());
    this.isRegistering.set(true);

    this.adminState
      .registerAdministrator({
        display_name: this.newAdminName(),
        email: this.newAdminEmail(),
        password: this.newAdminPassword(),
        age: Number.isFinite(parsedAge) ? parsedAge : Number.NaN,
        birth_date: this.newAdminBirthDate().trim() || null,
      })
      .subscribe({
        next: () => {
          this.isRegistering.set(false);
          this.showRegisterForm.set(false);
          this.resetRegisterDrafts();
        },
        error: (error: Error) => {
          this.isRegistering.set(false);
          this.registerError.set(error.message);
        },
      });
  }

  protected promoteUser(userId: number): void {
    if (this.updatingUserId() !== null) return;
    this.actionError.set('');
    this.updatingUserId.set(userId);
    this.adminState.promoteUserToAdmin(userId).subscribe({
      next: () => {
        this.updatingUserId.set(null);
      },
      error: (error: Error) => {
        this.updatingUserId.set(null);
        this.actionError.set(error.message);
      },
    });
  }

  protected revokeAdmin(userId: number): void {
    if (this.updatingUserId() !== null) return;
    this.actionError.set('');
    this.updatingUserId.set(userId);
    this.adminState.updateAdminRole(userId, false).subscribe({
      next: () => {
        this.updatingUserId.set(null);
      },
      error: (error: Error) => {
        this.updatingUserId.set(null);
        this.actionError.set(error.message);
      },
    });
  }

  protected isCurrentSessionUser(userId: number): boolean {
    return this.adminState.currentAdmin()?.userId === userId;
  }

  private resetRegisterDrafts(): void {
    this.newAdminName.set('');
    this.newAdminEmail.set('');
    this.newAdminPassword.set('');
    this.newAdminAge.set('30');
    this.newAdminBirthDate.set('');
  }
}
