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
  FamilyMember,
  UpdateMemberParentalControlsApiRequest,
} from '@ribbit/shared-types';
import { toApiError } from '../../core/api-error';
import { computeInitials } from '../../core/api-mappers';
import { readAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlanService } from '../../core/plan.service';
import { WidthPercentDirective } from '../../shared/width-percent.directive';
import { readInputValue } from '../../shared/dom-event-values';
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

  protected readonly familyMembers = signal<readonly FamilyMember[]>([]);
  protected readonly isLoading = signal<boolean>(false);
  protected readonly errorMessage = signal<string>('');
  protected readonly successMessage = signal<string>('');

  protected readonly isFormOpen = signal<boolean>(false);
  protected readonly addMode = signal<'create' | 'link'>('create');
  protected readonly isSubmitting = signal<boolean>(false);
  protected readonly removingMemberId = signal<number | null>(null);

  // Create new child account fields
  protected readonly childDisplayName = signal<string>('');
  protected readonly childEmail = signal<string>('');
  protected readonly childPassword = signal<string>('');
  protected readonly childBirthDate = signal<string>('');

  // Link existing child account field (email or numeric ID) and credentials
  protected readonly existingChildIdentifier = signal<string>('');
  protected readonly existingChildPassword = signal<string>('');

  // Parental controls editor state (banned genres & artists per child)
  protected readonly editingControlsMemberId = signal<number | null>(null);
  private readonly draftBlockedGenres = signal<readonly string[]>([]);
  protected readonly draftBlockedArtists = signal<readonly string[]>([]);
  protected readonly customGenreInput = signal<string>('');
  protected readonly artistBanInput = signal<string>('');
  protected readonly isSavingControls = signal<boolean>(false);
  protected readonly controlsError = signal<string>('');

  protected readonly isChildAccount = computed<boolean>(
    () => this.state.primaryAccountId() !== null,
  );

  protected readonly isFamilyPlan = computed<boolean>(() => {
    if (this.state.isAdmin()) return true;
    const planName = this.state.currentPlan().toLowerCase();
    if (planName.includes('famíl') || planName.includes('famil')) {
      return true;
    }
    const currentPlanId = this.state.currentPlanId();
    const plans = this.planService?.rawPlans() ?? [];
    const matched = plans.find((p) => p.plan_id === currentPlanId);
    return (matched?.max_profiles ?? 1) > 1;
  });

  protected readonly familyTierLabel = computed<string>(() => {
    if (this.isChildAccount()) return 'Conta Filha Vinculada';
    if (this.state.isAdmin()) return 'Administrador · Plano Família Gratuito';
    if (this.isFamilyPlan()) return 'Plano Família Ativo';
    return `Plano Atual: ${this.state.currentPlan()}`;
  });

  protected readonly maxProfiles = computed<number>(() => {
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

  protected readonly maxChildAccounts = computed<number>(() => Math.max(1, this.maxProfiles() - 1));

  protected readonly usedProfilesCount = computed<number>(() => 1 + this.familyMembers().length);

  protected readonly occupancyPercent = computed<number>(() =>
    Math.min(100, Math.round((this.usedProfilesCount() / this.maxProfiles()) * 100)),
  );

  protected readonly availableSlots = computed<readonly number[]>(() => {
    const remaining = Math.max(0, this.maxChildAccounts() - this.familyMembers().length);
    return Array.from({ length: remaining }, (_, idx) => idx + 1);
  });

  protected readonly parentInitials = computed<string>(() =>
    this.computeInitials(this.state.userName()),
  );

  protected readonly calculatedChildAge = computed<number | null>(() => {
    const raw = this.childBirthDate().trim();
    return raw ? calculateAgeFromBirthDate(raw) : null;
  });

  protected readonly isNewChildMinor = computed<boolean>(() => {
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

  protected computeInitials(name: string): string {
    return computeInitials(name, 'CF');
  }

  protected isMemberMinor(member: FamilyMember): boolean {
    if (member.age !== null && member.age > 0 && member.age < 18) {
      return true;
    }
    if (member.birthDate) {
      const age = calculateAgeFromBirthDate(member.birthDate);
      return age !== null && age < 18;
    }
    return false;
  }

  protected getMemberAgeLabel(member: FamilyMember): string {
    if (member.age !== null && member.age > 0) {
      return `${member.age} anos`;
    }
    if (member.birthDate) {
      const age = calculateAgeFromBirthDate(member.birthDate);
      if (age !== null) return `${age} anos`;
    }
    return 'Idade não informada';
  }

  private loadFamilyMembers(): void {
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

  protected openAddChildForm(mode: 'create' | 'link' = 'create'): void {
    this.addMode.set(mode);
    this.isFormOpen.set(true);
    this.errorMessage.set('');
    this.successMessage.set('');
  }

  protected closeAddChildForm(): void {
    this.isFormOpen.set(false);
    this.errorMessage.set('');
    this.resetFormFields();
  }

  protected switchAddMode(mode: 'create' | 'link'): void {
    this.addMode.set(mode);
    this.errorMessage.set('');
  }

  protected updateChildDisplayName(event: Event): void {
    this.childDisplayName.set(readInputValue(event));
  }

  protected updateChildEmail(event: Event): void {
    this.childEmail.set(readInputValue(event));
  }

  protected updateChildPassword(event: Event): void {
    this.childPassword.set(readInputValue(event));
  }

  protected updateChildBirthDate(event: Event): void {
    this.childBirthDate.set(readInputValue(event));
  }

  protected updateExistingChildIdentifier(event: Event): void {
    this.existingChildIdentifier.set(readInputValue(event));
  }

  protected updateExistingChildPassword(event: Event): void {
    this.existingChildPassword.set(readInputValue(event));
  }

  protected submitAddChild(event?: Event): void {
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
      const mockChild: FamilyMember = {
        userId: Math.floor(Math.random() * 900) + 100,
        email: payload.email ?? `dependente_${payload.dependent_user_id ?? 1}@ribbit.app`,
        displayName: payload.display_name ?? `Conta Filha #${payload.dependent_user_id ?? 1}`,
        age: this.calculatedChildAge() ?? 16,
        planId: this.state.currentPlanId(),
        birthDate: payload.birth_date ?? null,
        primaryAccountId: this.state.userId() ?? 1,
        blockedGenres: [],
        blockedArtists: [],
        isAdmin: false,
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

  protected removeChildAccount(member: FamilyMember): void {
    this.errorMessage.set('');
    this.successMessage.set('');

    if (!this.profileApi || !readAuthToken()) {
      this.familyMembers.update((list) => list.filter((m) => m.userId !== member.userId));
      if (this.editingControlsMemberId() === member.userId) {
        this.closeParentalControls();
      }
      this.state.notify(`Conta filha de ${member.displayName} desvinculada do plano.`);
      return;
    }

    this.removingMemberId.set(member.userId);
    this.profileApi.removeFamilyMember(member.userId).subscribe({
      next: () => {
        this.removingMemberId.set(null);
        if (this.editingControlsMemberId() === member.userId) {
          this.closeParentalControls();
        }
        this.state.notify(`Conta filha de ${member.displayName} desvinculada do plano.`);
        this.loadFamilyMembers();
      },
      error: (err: unknown) => {
        this.removingMemberId.set(null);
        this.errorMessage.set(toApiError(err).message);
      },
    });
  }

  // --- Parental Controls (Genres & Artists Banning) ---

  protected openParentalControls(member: FamilyMember): void {
    if (this.isSavingControls()) return;
    if (this.editingControlsMemberId() === member.userId) {
      this.closeParentalControls();
      return;
    }
    this.editingControlsMemberId.set(member.userId);
    this.draftBlockedGenres.set([...member.blockedGenres]);
    this.draftBlockedArtists.set([...member.blockedArtists]);
    this.customGenreInput.set('');
    this.artistBanInput.set('');
    this.controlsError.set('');
    this.successMessage.set('');
  }

  protected closeParentalControls(): void {
    this.editingControlsMemberId.set(null);
    this.draftBlockedGenres.set([]);
    this.draftBlockedArtists.set([]);
    this.customGenreInput.set('');
    this.artistBanInput.set('');
    this.controlsError.set('');
  }

  protected isDraftGenreBlocked(genre: string): boolean {
    return containsCaseInsensitive(this.draftBlockedGenres(), genre);
  }

  protected toggleDraftGenre(genre: string): void {
    const current = this.draftBlockedGenres();
    if (containsCaseInsensitive(current, genre)) {
      this.draftBlockedGenres.set(removeCaseInsensitive(current, genre));
      return;
    }
    this.draftBlockedGenres.set([...current, genre.trim()]);
  }

  protected updateCustomGenreInput(event: Event): void {
    this.customGenreInput.set(readInputValue(event));
  }

  protected addCustomBlockedGenre(event?: Event): void {
    event?.preventDefault();
    const cleaned = this.customGenreInput().trim();
    if (!cleaned) return;
    if (!containsCaseInsensitive(this.draftBlockedGenres(), cleaned)) {
      this.draftBlockedGenres.update((list) => [...list, cleaned]);
    }
    this.customGenreInput.set('');
  }

  protected removeDraftGenre(genre: string): void {
    this.draftBlockedGenres.update((list) => removeCaseInsensitive(list, genre));
  }

  protected hasParentalBlocks(member: FamilyMember): boolean {
    const hasGenres = member.blockedGenres.length > 0;
    const hasArtists = member.blockedArtists.length > 0;
    return hasGenres || hasArtists;
  }

  protected getExtraDraftGenres(): readonly string[] {
    return this.draftBlockedGenres().filter(
      (genre) => !containsCaseInsensitive(this.availableGenres, genre),
    );
  }

  protected updateArtistBanInput(event: Event): void {
    this.artistBanInput.set(readInputValue(event));
  }

  protected addBlockedArtist(event?: Event): void {
    event?.preventDefault();
    const cleaned = this.artistBanInput().trim();
    if (!cleaned) return;
    if (!containsCaseInsensitive(this.draftBlockedArtists(), cleaned)) {
      this.draftBlockedArtists.update((list) => [...list, cleaned]);
    }
    this.artistBanInput.set('');
  }

  protected removeDraftArtist(artist: string): void {
    this.draftBlockedArtists.update((list) => removeCaseInsensitive(list, artist));
  }

  protected saveParentalControls(member: FamilyMember): void {
    this.controlsError.set('');
    this.errorMessage.set('');
    this.successMessage.set('');

    const payload: UpdateMemberParentalControlsApiRequest = {
      blocked_genres: [...this.draftBlockedGenres()],
      blocked_artists: [...this.draftBlockedArtists()],
    };
    const toastMsg = `Restrições parentais atualizadas para ${member.displayName}.`;

    if (!this.profileApi || !readAuthToken()) {
      this.familyMembers.update((list) =>
        list.map((item) =>
          item.userId === member.userId
            ? {
                ...item,
                blockedGenres: payload.blocked_genres,
                blockedArtists: payload.blocked_artists,
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
    this.profileApi.updateFamilyMemberParentalControls(member.userId, payload).subscribe({
      next: (updatedMember) => {
        this.isSavingControls.set(false);
        this.familyMembers.update((list) =>
          list.map((item) => (item.userId === updatedMember.userId ? updatedMember : item)),
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

  protected goToPlans(): void {
    this.state.setPage('plans');
    if (this.router) {
      void this.router.navigate(['/plans']).catch(() => false);
    }
  }

  protected goToProfile(): void {
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
