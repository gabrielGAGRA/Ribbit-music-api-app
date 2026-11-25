import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NO_ERRORS_SCHEMA, provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { authInterceptor } from '../../core/auth.interceptor';
import { clearAuthStorage, writeAuthToken } from '../../core/auth-token.storage';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';
import { FamilyComponent } from './family.component';

describe('FamilyComponent', () => {
  let httpMock: HttpTestingController;
  let state: RibbitStateService;
  let component: FamilyComponent;

  beforeEach(() => {
    clearAuthStorage();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    httpMock = TestBed.inject(HttpTestingController);
    state = TestBed.inject(RibbitStateService);
    component = TestBed.runInInjectionContext(() => new FamilyComponent());
  });

  afterEach(() => {
    httpMock.verify();
    clearAuthStorage();
  });

  it('loads child accounts when parent user is on Family plan', () => {
    writeAuthToken('parent-jwt');
    state.currentPlan.set('Família');
    state.currentPlanId.set(3);

    component['loadFamilyMembers']();

    const req = httpMock.expectOne('/api/profile/family/members');
    expect(req.request.method).toBe('GET');
    req.flush([
      {
        user_id: 77,
        email: 'filha@familia.com',
        display_name: 'Sofia Silva',
        age: 14,
        plan_id: 3,
        birth_date: '2012-04-10',
        primary_account_id: 1,
        blocked_genres: ['Metal'],
        blocked_artists: ['Artist X'],
        is_admin: false,
      },
    ]);

    expect(component['familyMembers']().length).toBe(1);
    expect(component['isMemberMinor'](component['familyMembers']()[0]!)).toBe(true);
    expect(component['usedProfilesCount']()).toBe(2);
  });

  it('creates a new child account using email via POST /api/profile/family/members and reloads list', () => {
    writeAuthToken('parent-jwt');
    state.currentPlan.set('Família');

    component['openAddChildForm']('create');
    component['childDisplayName'].set('Pedro Silva');
    component['childEmail'].set('pedro@familia.com');
    component['childPassword'].set('senha123');
    component['childBirthDate'].set('2013-08-20');

    expect(component['isNewChildMinor']()).toBe(true);

    component['submitAddChild']();

    const postReq = httpMock.expectOne('/api/profile/family/members');
    expect(postReq.request.method).toBe('POST');
    expect(postReq.request.body).toEqual({
      display_name: 'Pedro Silva',
      email: 'pedro@familia.com',
      password: 'senha123',
      birth_date: '2013-08-20',
    });

    postReq.flush({
      user_id: 88,
      email: 'pedro@familia.com',
      display_name: 'Pedro Silva',
      age: 13,
      plan_id: 3,
      birth_date: '2013-08-20',
      primary_account_id: 1,
    });

    const reloadReq = httpMock.expectOne('/api/profile/family/members');
    reloadReq.flush([
      {
        user_id: 88,
        email: 'pedro@familia.com',
        display_name: 'Pedro Silva',
        age: 13,
        plan_id: 3,
        birth_date: '2013-08-20',
        primary_account_id: 1,
      },
    ]);

    expect(component['isFormOpen']()).toBe(false);
    expect(component['familyMembers']().length).toBe(1);
  });

  it('prevents double-submission when isSubmitting is already true', () => {
    writeAuthToken('parent-jwt');
    component['openAddChildForm']('create');
    component['childDisplayName'].set('Lucas');
    component['childEmail'].set('lucas@familia.com');
    component['childPassword'].set('Password123!');
    component['isSubmitting'].set(true);

    component['submitAddChild']();

    httpMock.expectNone('/api/profile/family/members');
  });

  it('shows contextual Portuguese error when creating a child account hits 401 for an already-registered email', () => {
    writeAuthToken('parent-jwt');
    component['openAddChildForm']('create');
    component['childDisplayName'].set('Lucas');
    component['childEmail'].set('jaexiste@familia.com');
    component['childPassword'].set('Password123!');

    component['submitAddChild']();

    const addReq = httpMock.expectOne('/api/profile/family/members');
    addReq.flush(
      { error: 'AuthenticationRequiredError', message: 'Invalid credentials.' },
      { status: 401, statusText: 'Unauthorized' },
    );

    expect(component['isSubmitting']()).toBe(false);
    expect(component['isFormOpen']()).toBe(true);
    expect(component['errorMessage']()).toContain('já pertence a uma conta existente');
  });

  it('validates password requirement when linking an existing child account by email', () => {
    writeAuthToken('parent-jwt');
    state.currentPlan.set('Família');

    component['openAddChildForm']('link');
    component['existingChildIdentifier'].set('existente@familia.com');
    component['submitAddChild']();

    expect(component['errorMessage']()).toContain('Informe a senha da conta');
    httpMock.expectNone('/api/profile/family/members');
  });

  it('links an existing child account by email and credentials via POST /api/profile/family/members', () => {
    writeAuthToken('parent-jwt');
    state.currentPlan.set('Família');

    component['openAddChildForm']('link');
    component['existingChildIdentifier'].set('existente@familia.com');
    component['existingChildPassword'].set('Secret123!');
    component['submitAddChild']();

    const linkReq = httpMock.expectOne('/api/profile/family/members');
    expect(linkReq.request.method).toBe('POST');
    expect(linkReq.request.body).toEqual({
      email: 'existente@familia.com',
      password: 'Secret123!',
    });

    const childDto = {
      user_id: 56,
      email: 'existente@familia.com',
      display_name: 'Conta Por Email',
      age: 16,
      plan_id: 3,
      primary_account_id: 1,
      is_admin: false,
    };
    linkReq.flush(childDto);

    const reloadReq = httpMock.expectOne('/api/profile/family/members');
    reloadReq.flush([childDto]);

    expect(component['familyMembers']().length).toBe(1);
  });

  it('links an existing child account by numeric ID and unlinks a child account via DELETE', () => {
    writeAuthToken('parent-jwt');
    state.currentPlan.set('Família');

    component['openAddChildForm']('link');
    component['existingChildIdentifier'].set('55');
    component['submitAddChild']();

    const linkReq = httpMock.expectOne('/api/profile/family/members');
    expect(linkReq.request.method).toBe('POST');
    expect(linkReq.request.body).toEqual({ dependent_user_id: 55 });

    const childDto = {
      user_id: 55,
      email: 'existente@familia.com',
      display_name: 'Conta Existente',
      age: 20,
      plan_id: 3,
      primary_account_id: 1,
      is_admin: false,
    };
    linkReq.flush(childDto);

    const reloadReq = httpMock.expectOne('/api/profile/family/members');
    reloadReq.flush([childDto]);

    expect(component['familyMembers']().length).toBe(1);

    component['removeChildAccount'](component['familyMembers']()[0]!);

    const delReq = httpMock.expectOne('/api/profile/family/members/55');
    expect(delReq.request.method).toBe('DELETE');
    delReq.flush(childDto);

    const reloadAfterDel = httpMock.expectOne('/api/profile/family/members');
    reloadAfterDel.flush([]);

    expect(component['familyMembers']().length).toBe(0);
  });

  it('updates banned genres and artists for a child account via PUT /api/profile/family/members/{id}/parental-controls', () => {
    writeAuthToken('parent-jwt');
    state.currentPlan.set('Família');

    const childMember = {
      userId: 77,
      email: 'filha@familia.com',
      displayName: 'Sofia Silva',
      age: 14,
      planId: 3,
      birthDate: null,
      primaryAccountId: 1,
      blockedGenres: ['Metal'],
      blockedArtists: ['Artist A'],
      isAdmin: false,
    };
    component['familyMembers'].set([childMember]);

    component['openParentalControls'](childMember);
    expect(component['editingControlsMemberId']()).toBe(77);
    expect(component['isDraftGenreBlocked']('metal')).toBe(true);

    component['toggleDraftGenre']('Funk');
    component['customGenreInput'].set('Sertanejo');
    component['addCustomBlockedGenre']();
    component['artistBanInput'].set('Artist B');
    component['addBlockedArtist']();
    component['removeDraftArtist']('Artist A');

    component['saveParentalControls'](childMember);

    const putReq = httpMock.expectOne('/api/profile/family/members/77/parental-controls');
    expect(putReq.request.method).toBe('PUT');
    expect(putReq.request.body).toEqual({
      blocked_genres: ['Metal', 'Funk', 'Sertanejo'],
      blocked_artists: ['Artist B'],
    });

    putReq.flush({
      user_id: 77,
      email: 'filha@familia.com',
      display_name: 'Sofia Silva',
      age: 14,
      plan_id: 3,
      primary_account_id: 1,
      is_admin: false,
      blocked_genres: ['metal', 'funk', 'sertanejo'],
      blocked_artists: ['artist b'],
    });

    expect(component['editingControlsMemberId']()).toBeNull();
    expect(component['familyMembers']()[0]?.blockedGenres).toEqual(['metal', 'funk', 'sertanejo']);
    expect(component['familyMembers']()[0]?.blockedArtists).toEqual(['artist b']);
  });

  it('surfaces backend errors when saving parental controls fails', () => {
    writeAuthToken('parent-jwt');
    const childMember = {
      userId: 77,
      email: 'filha@familia.com',
      displayName: 'Sofia Silva',
      age: 14,
      planId: 3,
      birthDate: null,
      primaryAccountId: 1,
      blockedGenres: [],
      blockedArtists: [],
      isAdmin: false,
    };
    component['familyMembers'].set([childMember]);
    component['openParentalControls'](childMember);
    component['toggleDraftGenre']('Trap');

    component['saveParentalControls'](childMember);

    const putReq = httpMock.expectOne('/api/profile/family/members/77/parental-controls');
    putReq.flush({ detail: 'Not Found' }, { status: 404, statusText: 'Not Found' });

    expect(component['isSavingControls']()).toBe(false);
    expect(component['editingControlsMemberId']()).toBe(77);
    expect(component['controlsError']()).toContain('Not Found');
  });

  it('calculates exact age on 18th birthday without UTC off-by-one shift', () => {
    const today = new Date();
    const eighteenYearsAgo = `${today.getFullYear() - 18}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    component['childBirthDate'].set(eighteenYearsAgo);
    expect(component['calculatedChildAge']()).toBe(18);
    expect(component['isNewChildMinor']()).toBe(false);
  });
});

describe('FamilyComponent DOM', () => {
  let httpMock: HttpTestingController;
  let state: RibbitStateService;

  beforeEach(() => {
    TestBed.resetTestingModule();
    clearAuthStorage();
    const html = readFileSync(resolve(__dirname, './family.component.html'), 'utf8');
    const css = readFileSync(resolve(__dirname, './family.component.css'), 'utf8');
    TestBed.overrideComponent(IconComponent, {
      set: {
        template: '',
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [],
      },
    });
    TestBed.overrideComponent(FrogComponent, {
      set: {
        template: '',
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [],
      },
    });
    TestBed.overrideComponent(FamilyComponent, {
      set: {
        template: html,
        templateUrl: undefined,
        styleUrl: undefined,
        styles: [css],
        schemas: [NO_ERRORS_SCHEMA],
      },
    });
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    httpMock = TestBed.inject(HttpTestingController);
    state = TestBed.inject(RibbitStateService);
  });

  afterEach(() => {
    httpMock.verify();
    clearAuthStorage();
  });

  it('loads members only once on mount and prevents switching child editors while PUT is in flight', () => {
    writeAuthToken('parent-jwt');
    state.currentPlan.set('Família');
    state.currentPlanId.set(3);

    const fixture = TestBed.createComponent(FamilyComponent);
    fixture.detectChanges();

    const initialGet = httpMock.expectOne('/api/profile/family/members');
    const childA = {
      user_id: 10,
      email: 'a@familia.com',
      display_name: 'Child A',
      age: 13,
      plan_id: 3,
      primary_account_id: 1,
      blocked_genres: [],
      blocked_artists: [],
      is_admin: false,
    };
    const childB = {
      user_id: 20,
      email: 'b@familia.com',
      display_name: 'Child B',
      age: 15,
      plan_id: 3,
      primary_account_id: 1,
      blocked_genres: [],
      blocked_artists: [],
      is_admin: false,
    };
    initialGet.flush([childA, childB]);

    const mounted = fixture.componentInstance;
    const mappedChildA = mounted['familyMembers']()[0]!;
    const mappedChildB = mounted['familyMembers']()[1]!;
    mounted['openParentalControls'](mappedChildA);
    mounted['saveParentalControls'](mappedChildA);
    expect(mounted['isSavingControls']()).toBe(true);

    mounted['openParentalControls'](mappedChildB);
    expect(mounted['editingControlsMemberId']()).toBe(10);

    const putReq = httpMock.expectOne('/api/profile/family/members/10/parental-controls');
    putReq.flush(childA);
    expect(mounted['isSavingControls']()).toBe(false);
    expect(mounted['editingControlsMemberId']()).toBeNull();
  });

  it('renders FILHA badge and hides parent capacity bar for child accounts', () => {
    state.primaryAccountId.set(1);
    const fixture = TestBed.createComponent(FamilyComponent);
    fixture.detectChanges();

    const badge = fixture.nativeElement.querySelector('.parent-crown-badge') as HTMLElement | null;
    expect(badge?.textContent?.trim()).toBe('FILHA');
    expect(fixture.nativeElement.querySelector('.family-capacity-bar')).toBeNull();
  });

  it('unlocks Family plan management for administrators even when assigned Free plan', () => {
    writeAuthToken('admin-jwt');
    state.isAdmin.set(true);
    state.currentPlan.set('Free');
    state.currentPlanId.set(1);
    state.primaryAccountId.set(null);

    const fixture = TestBed.createComponent(FamilyComponent);
    fixture.detectChanges();

    httpMock.expectOne('/api/profile/family/members').flush([]);
    fixture.detectChanges();

    expect(fixture.componentInstance['isFamilyPlan']()).toBe(true);
    const root = fixture.nativeElement;
    if (!(root instanceof HTMLElement)) {
      throw new TypeError('Expected root HTMLElement');
    }
    expect(root.querySelector('.family-upgrade-banner')).toBeNull();
    expect(root.querySelector('.parent-crown-badge')?.textContent?.trim()).toBe('ADMIN');
  });
});
