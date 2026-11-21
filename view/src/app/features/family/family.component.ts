import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';
import type {
  AddFamilyMemberApiRequest,
  UpdateMemberParentalControlsApiRequest,
  UserApiDto,
} from '@ribbit/shared-types';
import { toApiError } from '../../core/api-error';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlanService } from '../../core/services/plan.service';
import { WidthPercentDirective } from '../../shared/dynamic-style.directive';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';
import { BACKEND_GENRES } from '../../shared/modals.component';
import { ProfileApiService } from '../profile/profile-api.service';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function containsCaseInsensitive(list: readonly string[], candidate: string): boolean {
  const target = candidate.trim().toLowerCase();
  return list.some((item) => item.trim().toLowerCase() === target);
}

function removeCaseInsensitive(list: readonly string[], targetValue: string): readonly string[] {
  const target = targetValue.trim().toLowerCase();
  return list.filter((item) => item.trim().toLowerCase() !== target);
}

function calculateAgeFromBirthDate(raw: string): number | null {
  const trimmed = raw.trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  let birthYear: number;
  let birthMonth: number;
  let birthDay: number;

  if (match) {
    birthYear = Number(match[1]);
    birthMonth = Number(match[2]);
    birthDay = Number(match[3]);
  } else {
    const parsed = new Date(trimmed);
    if (Number.isNaN(parsed.getTime())) return null;
    birthYear = parsed.getUTCFullYear();
    birthMonth = parsed.getUTCMonth() + 1;
    birthDay = parsed.getUTCDate();
  }

  const today = new Date();
  let age = today.getFullYear() - birthYear;
  const monthDiff = today.getMonth() + 1 - birthMonth;
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDay)) {
    age--;
  }
  return age >= 0 ? age : null;
}

/** Dedicated parental control and Family plan screen for parent ('pai') and dependent ('filhas') accounts. */
@Component({
  selector: 'app-family',
  standalone: true,
  imports: [IconComponent, FrogComponent, WidthPercentDirective],
  templateUrl: './family.component.html',
  styleUrl: './family.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FamilyComponent {
  protected readonly state = inject(RibbitStateService);
  private readonly profileApi = inject(ProfileApiService, { optional: true });
  private readonly planService = inject(PlanService, { optional: true });
  private readonly router = inject(Router, { optional: true });

  protected readonly availableGenres: readonly string[] = BACKEND_GENRES;

  readonly familyMembers = signal<readonly UserApiDto[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly errorMessage = signal<string>('');
  readonly successMessage = signal<string>('');

  readonly isFormOpen = signal<boolean>(false);
  readonly addMode = signal<'create' | 'link'>('create');
  readonly isSubmitting = signal<boolean>(false);
  readonly removingMemberId = signal<number | null>(null);

  // Create new child account fields
  readonly childDisplayName = signal<string>('');
  readonly childEmail = signal<string>('');
  readonly childPassword = signal<string>('');
  readonly childBirthDate = signal<string>('');

  // Link existing child account field (email or numeric ID) and credentials
  readonly existingChildIdentifier = signal<string>('');
  readonly existingChildPassword = signal<string>('');

  // Parental controls editor state (banned genres & artists per child)
  readonly editingControlsMemberId = signal<number | null>(null);
  readonly draftBlockedGenres = signal<readonly string[]>([]);
  readonly draftBlockedArtists = signal<readonly string[]>([]);
  readonly customGenreInput = signal<string>('');
  readonly artistBanInput = signal<string>('');
  readonly isSavingControls = signal<boolean>(false);
  readonly controlsError = signal<string>('');

  readonly isChildAccount = computed<boolean>(() => this.state.primaryAccountId() !== null);

  readonly isFamilyPlan = computed<boolean>(() => {
    const planName = this.state.currentPlan().toLowerCase();
    if (planName.includes('famíl') || planName.includes('famil')) {
      return true;
    }
    const currentPlanId = this.state.currentPlanId();
    const plans = this.planService?.rawPlans() ?? [];
    const matched = plans.find((p) => p.plan_id === currentPlanId);
    return (matched?.max_profiles ?? 1) > 1;
  });

  readonly maxProfiles = computed<number>(() => {
    const currentPlanId = this.state.currentPlanId();
    const plans = this.planService?.rawPlans() ?? [];
    const matched = plans.find((p) => p.plan_id === currentPlanId);
    if (matched && matched.max_profiles > 1) {
      return matched.max_profiles;
    }
    const familyPlan = plans.find(
      (p) =>
        p.max_profiles > 1 ||
        p.name.toLowerCase().includes('famíl') ||
        p.name.toLowerCase().includes('famil'),
    );
    return familyPlan?.max_profiles ?? 4;
  });

  readonly maxChildAccounts = computed<number>(() => Math.max(1, this.maxProfiles() - 1));

  readonly usedProfilesCount = computed<number>(() => 1 + this.familyMembers().length);

  readonly occupancyPercent = computed<number>(() =>
    Math.min(100, Math.round((this.usedProfilesCount() / this.maxProfiles()) * 100)),
  );

  readonly availableSlots = computed<readonly number[]>(() => {
    const remaining = Math.max(0, this.maxChildAccounts() - this.familyMembers().length);
    return Array.from({ length: remaining }, (_, idx) => idx + 1);
  });

  readonly parentInitials = computed<string>(() => this.computeInitials(this.state.userName()));

  readonly calculatedChildAge = computed<number | null>(() => {
    const raw = this.childBirthDate().trim();
    return raw ? calculateAgeFromBirthDate(raw) : null;
  });

  readonly isNewChildMinor = computed<boolean>(() => {
    const age = this.calculatedChildAge();
    return age !== null && age < 18;
  });

  constructor() {
    effect(() => {
      if (this.isFamilyPlan() && !this.isChildAccount()) {
        this.loadFamilyMembers();
      }
    });
  }

  computeInitials(name: string): string {
    const parts = name
      .trim()
      .split(/\s+/)
      .filter((p) => p.length > 0);
    if (parts.length >= 2) {
      return `${parts[0]![0] ?? ''}${parts[1]![0] ?? ''}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase() || 'CF';
  }

  isMemberMinor(member: UserApiDto): boolean {
    if (member.age != null && member.age > 0 && member.age < 18) {
      return true;
    }
    if (member.birth_date) {
      const age = calculateAgeFromBirthDate(member.birth_date);
      return age !== null && age < 18;
    }
    return false;
  }

  getMemberAgeLabel(member: UserApiDto): string {
    if (member.age != null && member.age > 0) {
      return `${member.age} anos`;
    }
    if (member.birth_date) {
      const age = calculateAgeFromBirthDate(member.birth_date);
      if (age !== null) return `${age} anos`;
    }
    return 'Idade não informada';
  }

  loadFamilyMembers(): void {
    if (!this.profileApi || !readAuthToken()) return;
    this.isLoading.set(true);
    this.errorMessage.set('');
    this.profileApi.listFamilyMembers().subscribe({
      next: (members) => {
        this.familyMembers.set(members);
        this.isLoading.set(false);
      },
      error: (err: unknown) => {
        this.isLoading.set(false);
        this.errorMessage.set(toApiError(err).message);
      },
    });
  }

  openAddChildForm(mode: 'create' | 'link' = 'create'): void {
    this.addMode.set(mode);
    this.isFormOpen.set(true);
    this.errorMessage.set('');
    this.successMessage.set('');
  }

  closeAddChildForm(): void {
    this.isFormOpen.set(false);
    this.errorMessage.set('');
    this.resetFormFields();
  }

  switchAddMode(mode: 'create' | 'link'): void {
    this.addMode.set(mode);
    this.errorMessage.set('');
  }

  onDisplayNameInput(event: Event): void {
    this.childDisplayName.set((event.target as HTMLInputElement).value);
  }

  onEmailInput(event: Event): void {
    this.childEmail.set((event.target as HTMLInputElement).value);
  }

  onPasswordInput(event: Event): void {
    this.childPassword.set((event.target as HTMLInputElement).value);
  }

  onBirthDateInput(event: Event): void {
    this.childBirthDate.set((event.target as HTMLInputElement).value);
  }

  onExistingIdentifierInput(event: Event): void {
    this.existingChildIdentifier.set((event.target as HTMLInputElement).value);
  }

  onExistingPasswordInput(event: Event): void {
    this.existingChildPassword.set((event.target as HTMLInputElement).value);
  }

  submitAddChild(event?: Event): void {
    event?.preventDefault();
    if (this.isSubmitting()) return;
    this.errorMessage.set('');
    this.successMessage.set('');

    if (this.addMode() === 'link') {
      this.submitLinkExistingChild();
      return;
    }
    this.submitCreateNewChild();
  }

  private submitLinkExistingChild(): void {
    const raw = this.existingChildIdentifier().trim();
    if (raw.includes('@')) {
      const normalizedEmail = raw.toLowerCase();
      if (!EMAIL_PATTERN.test(normalizedEmail)) {
        this.errorMessage.set('Informe um e-mail válido para vincular a conta filha.');
        return;
      }
      const password = this.existingChildPassword().trim();
      if (!password) {
        this.errorMessage.set(
          'Informe a senha da conta para autenticar e vincular como conta filha.',
        );
        return;
      }
      this.executeAddRequest(
        { email: normalizedEmail, password },
        `Conta ${normalizedEmail} vinculada como conta filha!`,
      );
      return;
    }

    const parsedId = Number(raw);
    if (!raw || !Number.isInteger(parsedId) || parsedId <= 0) {
      this.errorMessage.set('Informe o e-mail ou ID numérico válido da conta filha.');
      return;
    }
    this.executeAddRequest(
      { dependent_user_id: parsedId },
      `Conta #${parsedId} vinculada como conta filha!`,
    );
  }

  private submitCreateNewChild(): void {
    const displayName = this.childDisplayName().trim();
    const email = this.childEmail().trim();
    const password = this.childPassword().trim();
    const birthDate = this.childBirthDate().trim();

    if (displayName.length < 2) {
      this.errorMessage.set('Informe o nome da conta filha (mínimo 2 caracteres).');
      return;
    }
    if (!EMAIL_PATTERN.test(email)) {
      this.errorMessage.set('Informe um e-mail válido para a conta filha.');
      return;
    }
    if (password.length < 6) {
      this.errorMessage.set('A senha da conta filha deve ter pelo menos 6 caracteres.');
      return;
    }

    this.executeAddRequest(
      {
        display_name: displayName,
        email: email.toLowerCase(),
        password,
        birth_date: birthDate || undefined,
      },
      `Conta filha de ${displayName} criada e vinculada ao seu Plano Família!`,
    );
  }

  private executeAddRequest(payload: AddFamilyMemberApiRequest, toastMsg: string): void {
    if (!this.profileApi || !readAuthToken()) {
      const mockChild: UserApiDto = {
        user_id: Math.floor(Math.random() * 900) + 100,
        email: payload.email ?? `dependente_${payload.dependent_user_id ?? 1}@ribbit.app`,
        display_name: payload.display_name ?? `Conta Filha #${payload.dependent_user_id ?? 1}`,
        age: this.calculatedChildAge() ?? 16,
        plan_id: this.state.currentPlanId(),
        birth_date: payload.birth_date ?? null,
        primary_account_id: this.state.userId() ?? 1,
        blocked_genres: [],
        blocked_artists: [],
        is_admin: false,
      };
      this.familyMembers.update((list) => [...list, mockChild]);
      this.state.notify(toastMsg);
      this.successMessage.set(toastMsg);
      this.isFormOpen.set(false);
      this.resetFormFields();
      return;
    }

    this.isSubmitting.set(true);
    this.profileApi.addFamilyMember(payload).subscribe({
      next: () => {
        this.isSubmitting.set(false);
        this.state.notify(toastMsg);
        this.successMessage.set(toastMsg);
        this.isFormOpen.set(false);
        this.resetFormFields();
        this.loadFamilyMembers();
      },
      error: (err: unknown) => {
        this.isSubmitting.set(false);
        const apiErr = toApiError(err);
        if (apiErr.status === 401) {
          this.errorMessage.set(
            this.addMode() === 'create'
              ? 'Este e-mail já pertence a uma conta existente no Ribbit e a senha informada não confere. Use outro e-mail para criar uma nova conta filha ou acesse a aba "Vincular por E-mail" com a senha correta dessa conta.'
              : 'A senha informada para a conta existente está incorreta.',
          );
        } else {
          this.errorMessage.set(apiErr.message);
        }
      },
    });
  }

  removeChildAccount(member: UserApiDto): void {
    this.errorMessage.set('');
    this.successMessage.set('');

    if (!this.profileApi || !readAuthToken()) {
      this.familyMembers.update((list) => list.filter((m) => m.user_id !== member.user_id));
      if (this.editingControlsMemberId() === member.user_id) {
        this.closeParentalControls();
      }
      this.state.notify(`Conta filha de ${member.display_name} desvinculada do plano.`);
      return;
    }

    this.removingMemberId.set(member.user_id);
    this.profileApi.removeFamilyMember(member.user_id).subscribe({
      next: () => {
        this.removingMemberId.set(null);
        if (this.editingControlsMemberId() === member.user_id) {
          this.closeParentalControls();
        }
        this.state.notify(`Conta filha de ${member.display_name} desvinculada do plano.`);
        this.loadFamilyMembers();
      },
      error: (err: unknown) => {
        this.removingMemberId.set(null);
        this.errorMessage.set(toApiError(err).message);
      },
    });
  }

  // --- Parental Controls (Genres & Artists Banning) ---

  openParentalControls(member: UserApiDto): void {
    if (this.isSavingControls()) return;
    if (this.editingControlsMemberId() === member.user_id) {
      this.closeParentalControls();
      return;
    }
    this.editingControlsMemberId.set(member.user_id);
    this.draftBlockedGenres.set([...(member.blocked_genres ?? [])]);
    this.draftBlockedArtists.set([...(member.blocked_artists ?? [])]);
    this.customGenreInput.set('');
    this.artistBanInput.set('');
    this.controlsError.set('');
    this.successMessage.set('');
  }

  closeParentalControls(): void {
    this.editingControlsMemberId.set(null);
    this.draftBlockedGenres.set([]);
    this.draftBlockedArtists.set([]);
    this.customGenreInput.set('');
    this.artistBanInput.set('');
    this.controlsError.set('');
  }

  isDraftGenreBlocked(genre: string): boolean {
    return containsCaseInsensitive(this.draftBlockedGenres(), genre);
  }

  toggleDraftGenre(genre: string): void {
    const current = this.draftBlockedGenres();
    if (containsCaseInsensitive(current, genre)) {
      this.draftBlockedGenres.set(removeCaseInsensitive(current, genre));
      return;
    }
    this.draftBlockedGenres.set([...current, genre.trim()]);
  }

  onCustomGenreInput(event: Event): void {
    this.customGenreInput.set((event.target as HTMLInputElement).value);
  }

  addCustomBlockedGenre(event?: Event): void {
    event?.preventDefault();
    const cleaned = this.customGenreInput().trim();
    if (!cleaned) return;
    if (!containsCaseInsensitive(this.draftBlockedGenres(), cleaned)) {
      this.draftBlockedGenres.update((list) => [...list, cleaned]);
    }
    this.customGenreInput.set('');
  }

  removeDraftGenre(genre: string): void {
    this.draftBlockedGenres.update((list) => removeCaseInsensitive(list, genre));
  }

  getExtraDraftGenres(): readonly string[] {
    return this.draftBlockedGenres().filter(
      (genre) => !containsCaseInsensitive(this.availableGenres, genre),
    );
  }

  onArtistBanInput(event: Event): void {
    this.artistBanInput.set((event.target as HTMLInputElement).value);
  }

  addBlockedArtist(event?: Event): void {
    event?.preventDefault();
    const cleaned = this.artistBanInput().trim();
    if (!cleaned) return;
    if (!containsCaseInsensitive(this.draftBlockedArtists(), cleaned)) {
      this.draftBlockedArtists.update((list) => [...list, cleaned]);
    }
    this.artistBanInput.set('');
  }

  removeDraftArtist(artist: string): void {
    this.draftBlockedArtists.update((list) => removeCaseInsensitive(list, artist));
  }

  saveParentalControls(member: UserApiDto): void {
    this.controlsError.set('');
    this.errorMessage.set('');
    this.successMessage.set('');

    const payload: UpdateMemberParentalControlsApiRequest = {
      blocked_genres: [...this.draftBlockedGenres()],
      blocked_artists: [...this.draftBlockedArtists()],
    };
    const toastMsg = `Restrições parentais atualizadas para ${member.display_name}.`;

    if (!this.profileApi || !readAuthToken()) {
      this.familyMembers.update((list) =>
        list.map((item) =>
          item.user_id === member.user_id
            ? {
                ...item,
                blocked_genres: payload.blocked_genres,
                blocked_artists: payload.blocked_artists,
              }
            : item,
        ),
      );
      this.state.notify(toastMsg);
      this.successMessage.set(toastMsg);
      this.closeParentalControls();
      return;
    }

    this.isSavingControls.set(true);
    this.profileApi.updateFamilyMemberParentalControls(member.user_id, payload).subscribe({
      next: (updatedMember) => {
        this.isSavingControls.set(false);
        this.familyMembers.update((list) =>
          list.map((item) => (item.user_id === updatedMember.user_id ? updatedMember : item)),
        );
        this.state.notify(toastMsg);
        this.successMessage.set(toastMsg);
        this.closeParentalControls();
      },
      error: (err: unknown) => {
        this.isSavingControls.set(false);
        const apiErr = toApiError(err);
        if (apiErr.status === 404 || apiErr.status === 405) {
          this.controlsError.set(
            `O backend ainda não possui o endpoint de persistência de restrições parentais para contas filhas (PUT /api/profile/family/members/{id}/parental-controls): ${apiErr.message}`,
          );
        } else {
          this.controlsError.set(apiErr.message);
        }
      },
    });
  }

  goToPlans(): void {
    this.state.setPage('plans');
    if (this.router) {
      void this.router.navigate(['/plans']).catch(() => false);
    }
  }

  goToProfile(): void {
    this.state.setPage('profile');
    if (this.router) {
      void this.router.navigate(['/profile']).catch(() => false);
    }
  }

  private resetFormFields(): void {
    this.childDisplayName.set('');
    this.childEmail.set('');
    this.childPassword.set('');
    this.childBirthDate.set('');
    this.existingChildIdentifier.set('');
    this.existingChildPassword.set('');
  }
}
