import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';
import { BACKEND_GENRES, MAX_FAVORITE_GENRES, ModalsComponent } from './modals.component';
import { authInterceptor } from '../core/auth.interceptor';
import { clearAuthStorage, writeAuthToken } from '../core/auth-token.storage';
import { RibbitStateService } from '../core/ribbit-state.service';

describe('ModalsComponent', () => {
  it('extracts lineup as array of artists, country, description and playlist reference', () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });

    const component = TestBed.runInInjectionContext(() => new ModalsComponent());

    const form = document.createElement('form');
    form.innerHTML = `
      <input name="name" value="Festival Folk" />
      <input name="duration" value="60" />
      <input name="genre" value="Indie" />
      <textarea name="lineup">The Paper Kites, Tycho, Masego</textarea>
      <input name="country" value="BR" />
      <input name="description" value="Uma playlist para festivais de fim de semana" />
      <input name="referencePlaylistId" value="42" />
    `;

    // Make Lineup and Referência active
    (component as unknown as { toggleFilter: (f: string) => void }).toggleFilter('Lineup');

    const filters = (
      component as unknown as {
        extractPlaylistFilters: (f: HTMLFormElement) => Record<string, unknown>;
      }
    ).extractPlaylistFilters(form);

    expect(filters['genre']).toBe('Indie');
    expect(filters['artist']).toEqual(['The Paper Kites', 'Tycho', 'Masego']);
    expect(filters['country']).toBe('BR');
    expect(filters['description']).toBe('Uma playlist para festivais de fim de semana');
    expect(filters['reference_playlist_id']).toBe(42);
    expect(filters['source_playlist_id']).toBe(42);
  });

  it('omits duration when Duração filter is inactive and includes reference_source when selected', () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });

    const state = TestBed.inject(RibbitStateService);
    const component = TestBed.runInInjectionContext(() => new ModalsComponent());
    const createSpy = vi.spyOn(state, 'createPlaylist').mockImplementation(() => undefined);

    const form = document.createElement('form');
    form.innerHTML = `
      <input name="name" value="Sem Limite" />
      <select name="referencePlaylistId">
        <option value="12" selected>Base</option>
      </select>
      <select name="referenceSource">
        <option value="curtidas" selected>Minhas Curtidas</option>
      </select>
    `;

    component['createPlaylistFromForm']({
      preventDefault: () => undefined,
      target: form,
    } as unknown as Event);

    expect(createSpy).toHaveBeenCalledWith('Sem Limite', null, {
      reference_playlist_id: 12,
      source_playlist_id: 12,
      reference_source: 'curtidas',
    });

    createSpy.mockClear();
    component['toggleFilter']('Duração');
    const durationForm = document.createElement('form');
    durationForm.innerHTML = `
      <input name="name" value="Com Limite" />
      <input name="duration" value="25" />
    `;
    component['createPlaylistFromForm']({
      preventDefault: () => undefined,
      target: durationForm,
    } as unknown as Event);

    expect(createSpy).toHaveBeenCalledWith('Com Limite', 25, expect.any(Object));
  });

  it('submits Jam creation with deck_source, max_superlikes and source_playlist_id', () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });

    const state = TestBed.inject(RibbitStateService);
    const component = TestBed.runInInjectionContext(() => new ModalsComponent());

    let capturedPayload: unknown = null;
    state.createJamRoom = (payload) => {
      capturedPayload = payload;
    };

    const form = document.createElement('form');
    form.innerHTML = `
      <input name="roomName" value="Sala Indie Rock" />
      <input name="hours" value="2" />
      <input name="minutes" value="15" />
      <input name="threshold" value="4" />
      <select name="deck_source">
        <option value="playlist" selected>Playlist</option>
      </select>
      <select name="source_playlist_id">
        <option value="99" selected>Minha Playlist</option>
      </select>
      <input name="max_superlikes" value="8" />
    `;

    component['createJamFromForm']({
      preventDefault: () => {},
      target: form,
    } as unknown as Event);

    expect(capturedPayload).toEqual({
      room_name: 'Sala Indie Rock',
      duration_minutes: 135,
      skip_votes_threshold: 4,
      deck_source: 'playlist',
      source_playlist_id: 99,
      max_superlikes: 8,
    });
  });

  it('updates jamDeckSource on selection change', () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });

    const component = TestBed.runInInjectionContext(() => new ModalsComponent());
    expect(component['jamDeckSource']()).toBe('livre');

    const select = document.createElement('select');
    const option = document.createElement('option');
    option.value = 'curtidas';
    option.text = 'Curtidas';
    option.selected = true;
    select.appendChild(option);
    select.value = 'curtidas';
    component['updateJamDeckSource']({ target: select } as unknown as Event);
    expect(component['jamDeckSource']()).toBe('curtidas');
  });

  describe('Ribbit Onboarding & Word Cloud', () => {
    it('should navigate across steps 1, 2, and 3', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const component = TestBed.runInInjectionContext(() => new ModalsComponent());
      expect(component['onboardingStep']()).toBe(1);

      component['nextOnboardingStep']();
      expect(component['onboardingStep']()).toBe(2);

      component['prevOnboardingStep']();
      expect(component['onboardingStep']()).toBe(1);

      component['prevOnboardingStep']();
      expect(component['onboardingStep']()).toBe(1);
    });

    it('should toggle word cloud genres and enforce a maximum of 3 selected genres', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const component = TestBed.runInInjectionContext(() => new ModalsComponent());
      expect(component['selectedWordCloudGenres']()).toEqual([]);
      expect(BACKEND_GENRES).toContain('Rock');
      expect(BACKEND_GENRES).toContain('Pop');
      expect(BACKEND_GENRES).toContain('Hip Hop');
      expect(BACKEND_GENRES).toContain('Grunge');

      component['toggleWordCloudGenre']('Rock');
      component['toggleWordCloudGenre']('Pop');
      component['toggleWordCloudGenre']('Hip Hop');
      expect(component['selectedWordCloudGenres']()).toEqual(['Rock', 'Pop', 'Hip Hop']);
      expect(component['selectedWordCloudGenres']().length).toBe(MAX_FAVORITE_GENRES);

      // Attempting to select a 4th genre should not exceed 3
      component['toggleWordCloudGenre']('Grunge');
      expect(component['isWordCloudSelected']('Grunge')).toBe(false);
      expect(component['selectedWordCloudGenres']()).toEqual(['Rock', 'Pop', 'Hip Hop']);
      expect(component['ribbySpeech']()).toContain('máximo 3 gêneros');

      // Deselecting one allows selecting another
      component['toggleWordCloudGenre']('Pop');
      expect(component['isWordCloudSelected']('Pop')).toBe(false);
      component['toggleWordCloudGenre']('Grunge');
      expect(component['isWordCloudSelected']('Grunge')).toBe(true);
      expect(component['selectedWordCloudGenres']()).toEqual(['Rock', 'Hip Hop', 'Grunge']);
    });

    it('should allow advancing to step 3 without selecting any genre', () => {
      localStorage.clear();
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const state = TestBed.inject(RibbitStateService);
      const component = TestBed.runInInjectionContext(() => new ModalsComponent());

      expect(component['selectedWordCloudGenres']()).toEqual([]);
      component['savePreferencesAndNext']();

      expect(component['onboardingStep']()).toBe(3);
      expect(state.favoriteGenres()).toEqual([]);
      expect(component['ribbySpeech']()).toContain('todos os gêneros');
      localStorage.clear();
    });

    it('should save preferences and advance to step 3 on savePreferencesAndNext', () => {
      localStorage.clear();
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const state = TestBed.inject(RibbitStateService);
      const component = TestBed.runInInjectionContext(() => new ModalsComponent());

      component['selectedWordCloudGenres'].set(['Indie', 'Jazz', 'Rock']);
      component['savePreferencesAndNext']();

      expect(component['onboardingStep']()).toBe(3);
      expect(state.favoriteGenres()).toEqual(['Indie', 'Jazz', 'Rock']);
      const email = state.userEmail() || 'user';
      expect(localStorage.getItem(`ribbit:onboarding_done:${email}`)).toBe('true');
      localStorage.clear();
    });

    it('should finish onboarding, save preferences, close modal and reset step', () => {
      localStorage.clear();
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const state = TestBed.inject(RibbitStateService);
      state.setModal('onboarding');
      const component = TestBed.runInInjectionContext(() => new ModalsComponent());

      component['selectedWordCloudGenres'].set(['Rock', 'Eletrônica']);
      component['finishOnboarding']();

      expect(state.favoriteGenres()).toEqual(['Rock', 'Eletrônica']);
      expect(state.activeModal()).toBeNull();
      expect(component['onboardingStep']()).toBe(1);
      const email = state.userEmail() || 'user';
      expect(localStorage.getItem(`ribbit:onboarding_done:${email}`)).toBe('true');
      localStorage.clear();
    });

    it('should update Ribby speech and mood dynamically on interactive demo swipes and topics', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const component = TestBed.runInInjectionContext(() => new ModalsComponent());
      expect(component['ribbyMood']()).toBe('wave');

      component['selectTutorialTopic']('family');
      expect(component['ribbySpeech']()).toContain('Conta Pai');

      component['triggerDemoSwipe']('love');
      expect(component['tutorialDemoAction']()).toBe('love');
      expect(component['ribbyMood']()).toBe('excited');
      expect(component['ribbySpeech']()).toContain('Superlike');
    });

    it('extracts explicit startDate, endDate and reference playlist in playlist creation', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const component = TestBed.runInInjectionContext(() => new ModalsComponent());

      const form = document.createElement('form');
      form.innerHTML = `
        <input name="name" value="Anos 2010 a 2015" />
        <input name="startDate" value="2010-05-01" />
        <input name="endDate" value="2015-11-30" />
        <input name="referencePlaylistId" value="15" />
      `;

      (component as unknown as { toggleFilter: (f: string) => void }).toggleFilter(
        'Data Início / Fim',
      );

      const filters = (
        component as unknown as {
          extractPlaylistFilters: (f: HTMLFormElement) => Record<string, unknown>;
        }
      ).extractPlaylistFilters(form);

      expect(filters['startDate']).toBe('2010-05-01');
      expect(filters['endDate']).toBe('2015-11-30');
      expect(filters['year']).toEqual([2010, 2011, 2012, 2013, 2014, 2015]);
      expect(filters['reference_playlist_id']).toBe(15);
      expect(filters['source_playlist_id']).toBe(15);
    });

    it('includes País in availableFilters and renders the country input field in playlist creation modal', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const component = TestBed.runInInjectionContext(() => new ModalsComponent());
      const helper = component as unknown as {
        availableFilters: readonly string[];
        isFilterActive: (f: string) => boolean;
        toggleFilter: (f: string) => void;
      };

      expect(helper.availableFilters).toContain('País');
      expect(helper.isFilterActive('País')).toBe(false);
      helper.toggleFilter('País');
      expect(helper.isFilterActive('País')).toBe(true);
    });

    it('extracts genre and year together when both Gênero and Data Início / Fim are active', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const component = TestBed.runInInjectionContext(() => new ModalsComponent());
      const form = document.createElement('form');
      form.innerHTML = `
        <input name="name" value="Rock Recente" />
        <select name="genre">
          <option value="Rock" selected>Rock</option>
          <option value="Pop">Pop</option>
        </select>
        <input name="startDate" value="2018-01-01" />
        <input name="endDate" value="2020-12-31" />
      `;

      const helper = component as unknown as {
        toggleFilter: (f: string) => void;
        isFilterActive: (f: string) => boolean;
        extractPlaylistFilters: (f: HTMLFormElement) => Record<string, unknown>;
      };
      if (!helper.isFilterActive('Gênero')) helper.toggleFilter('Gênero');
      if (!helper.isFilterActive('Data Início / Fim')) helper.toggleFilter('Data Início / Fim');

      const filters = helper.extractPlaylistFilters(form);
      expect(filters['genre']).toBe('Rock');
      expect(filters['year']).toEqual([2018, 2019, 2020]);
      expect(
        (component as unknown as { availableFilters: readonly string[] }).availableFilters,
      ).not.toContain('Evento');
    });

    it('applies artist search filter along with genre and decade filters', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const state = TestBed.inject(RibbitStateService);
      const component = TestBed.runInInjectionContext(() => new ModalsComponent());

      component['selectSearchGenre']('Rock');
      component['updateSearchArtistDraft']({
        target: { value: '  Queen  ' },
      } as unknown as Event);
      component['updateSearchStartDateDraft']({
        target: { value: '2015-01-01' },
      } as unknown as Event);
      component['updateSearchEndDateDraft']({
        target: { value: '2020-12-31' },
      } as unknown as Event);
      component['updateSearchMinRating']({
        target: { value: '4' },
      } as unknown as Event);
      component['applyFilters']();

      expect(state.searchFilterGenre()).toBe('Rock');
      expect(state.searchFilterArtist()).toBe('Queen');
      expect(state.searchFilterStartDate()).toBe('2015-01-01');
      expect(state.searchFilterEndDate()).toBe('2020-12-31');
      expect(state.searchFilterMinRating()).toBe(4);
    });

    it('allows star-only review submission without comment text', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const state = TestBed.inject(RibbitStateService);
      const publishSpy = vi.spyOn(state, 'publishTrackReview').mockImplementation(() => undefined);
      const component = TestBed.runInInjectionContext(() => new ModalsComponent());

      component['rateSong'](4);
      const input: { value: string } = { value: '   ' };
      const form = {
        elements: { namedItem: () => input },
      } as unknown as HTMLFormElement;

      component['submitTrackComment']({
        preventDefault: () => undefined,
        target: form,
      } as unknown as Event);

      expect(publishSpy).toHaveBeenCalledWith(4, '');
    });

    it('keeps filter genres sorted alphabetically and exposes unavailable-track modal markup', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const component = TestBed.runInInjectionContext(() => new ModalsComponent());
      const expectedSorted = [...BACKEND_GENRES].sort((a, b) =>
        a.localeCompare(b, 'pt-BR', { sensitivity: 'base' }),
      );
      expect(BACKEND_GENRES).toEqual(expectedSorted);
      expect(component['searchGenreOptions'][0]).toBe('Todos');
      expect(component['searchGenreOptions'].slice(1)).toEqual(expectedSorted);

      const template = readFileSync(resolve(__dirname, './modals.component.html'), 'utf8');
      expect(template).toContain("state.activeModal() === 'track-unavailable'");
      expect(template).toContain('não está mais disponível');
    });

    it('handles modal navigation, onboarding steps, word cloud, search drafts, and checkout controls', () => {
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const state = TestBed.inject(RibbitStateService);
      const component = TestBed.runInInjectionContext(() => new ModalsComponent());

      component['closeModal']();
      expect(state.activeModal()).toBeNull();

      component['selectSearchGenre']('Jazz');
      const input = document.createElement('input');
      input.value = 'Miles';
      component['updateSearchArtistDraft']({ target: input } as unknown as Event);
      input.value = '2020';
      component['updateSearchStartDateDraft']({ target: input } as unknown as Event);
      input.value = '2024';
      component['updateSearchEndDateDraft']({ target: input } as unknown as Event);
      input.value = '4';
      component['updateSearchMinRating']({ target: input } as unknown as Event);

      const wasPopSelected = component['isGenreSelected']('Pop');
      component['toggleSelectedGenre']('Pop');
      expect(component['isGenreSelected']('Pop')).toBe(!wasPopSelected);
      const wasMetalBlocked = component['isGenreBlocked']('Metal');
      component['toggleBlockedGenre']('Metal');
      expect(component['isGenreBlocked']('Metal')).toBe(!wasMetalBlocked);

      component['selectPaymentMethod']('pix');
      expect(component['paymentMethod']()).toBe('pix');

      component['nextOnboardingStep']();
      expect(component['onboardingStep']()).toBe(2);
      component['prevOnboardingStep']();
      expect(component['onboardingStep']()).toBe(1);
      component['goToOnboardingStep'](2);
      expect(component['onboardingStep']()).toBe(2);
      component['pokeRibby']();
      component['toggleWordCloudGenre']('Indie');
      expect(component['isWordCloudSelected']('Indie')).toBe(true);
      component['finishOnboarding']();
      expect(state.activeModal()).toBeNull();

      component['goToPlansFromUpgrade']();
      expect(state.activePage()).toBe('plans');
      component['goToSettingsFromSpotify']();
      expect(state.activePage()).toBe('settings');
      component['goToExploreRadar']();
      expect(state.activePage()).toBe('explore');

      component['openCreateFromAdd']();
      expect(state.activeModal()).toBe('playlist');

      component['addBySwipe']();
      expect(state.activePage()).toBe('discover');

      component['finishAndNavigate']('discover');
      expect(state.activePage()).toBe('discover');

      component['selectTutorialTopic']('playlists');
      component['selectTutorialTopic']('jams');
      component['selectTutorialTopic']('swipe');
      component['triggerDemoSwipe']('like');
      component['triggerDemoSwipe']('reject');

      state.userId.set(5);
      component['rateSong'](5);
      expect(
        component['isOwnReview']({
          id: 1,
          userId: 5,
          author: 'Me',
          initials: 'ME',
          text: 'Hi',
          likes: 0,
          age: 'agora',
          date: Date.now(),
        }),
      ).toBe(true);

      const sel = document.createElement('select');
      sel.innerHTML = '<option value="likes">likes</option>';
      sel.value = 'likes';
      component['updateTrackReviewSort']({ target: sel } as unknown as Event);

      const overlay = document.createElement('div');
      component['closeOnBackdrop']({
        target: overlay,
        currentTarget: overlay,
      } as unknown as MouseEvent);
      expect(state.activeModal()).toBeNull();

      component['applyFilters']();
      component['saveFrequencies']();
      component['confirmDeleteAccount']();
      component['submitCheckout'](new Event('submit'));
      component['addToExistingPlaylist'](0);

      const qForm = document.createElement('form');
      qForm.innerHTML = '<input name="name" value="Queue Mix" />';
      component['saveQueueAsPlaylist']({
        preventDefault: () => undefined,
        target: qForm,
      } as unknown as Event);

      const pForm = document.createElement('form');
      pForm.innerHTML = '<input name="name" value="Custom Mix" />';
      component['createPlaylistFromForm']({
        preventDefault: () => undefined,
        target: pForm,
      } as unknown as Event);
    });

    it('matches lowercase backend genres, prevents favorite/blocked contradictions, and syncs drafts on modal open', () => {
      localStorage.clear();
      TestBed.configureTestingModule({
        providers: [
          provideHttpClient(withInterceptors([authInterceptor])),
          provideHttpClientTesting(),
        ],
      });

      const state = TestBed.inject(RibbitStateService);
      const component = TestBed.runInInjectionContext(() => new ModalsComponent());

      // Simulate lowercase backend genres already loaded in state
      state.favoriteGenres.set(['hip hop', 'mpb']);
      state.selectedGenres.set(['hip hop', 'mpb']);
      state.blockedGenres.set(['forro']);

      expect(component['isGenreSelected']('Hip Hop')).toBe(true);
      expect(component['isGenreSelected']('MPB')).toBe(true);
      expect(component['isGenreBlocked']('Forró')).toBe(true);

      // Deselecting a lowercase favorite works
      component['toggleSelectedGenre']('Hip Hop');
      expect(component['isGenreSelected']('Hip Hop')).toBe(false);

      // Selecting a blocked genre as favorite on paid plan unblocks it automatically
      state.setPlan('Individual');
      component['toggleSelectedGenre']('Forró');
      expect(component['isGenreSelected']('Forró')).toBe(true);
      expect(component['isGenreBlocked']('Forró')).toBe(false);

      // Blocking a favorite genre on paid plan removes it from selected favorites
      component['toggleBlockedGenre']('MPB');
      expect(component['isGenreBlocked']('MPB')).toBe(true);
      expect(component['isGenreSelected']('MPB')).toBe(false);

      // Blocking on Free plan keeps favorite intact (since 403 upgrade prompt applies)
      state.setPlan('Free');
      state.selectedGenres.set(['Rock']);
      state.blockedGenres.set([]);
      component['toggleBlockedGenre']('Rock');
      expect(component['isGenreSelected']('Rock')).toBe(true);

      // Opening onboarding hydrates word cloud with persisted favorites
      state.favoriteGenres.set(['Rock', 'Jazz']);
      state.setModal('onboarding');
      TestBed.flushEffects();
      expect(component['selectedWordCloudGenres']()).toEqual(['Rock', 'Jazz']);

      // Opening filters with auth token resets discarded draft back to persisted favorites
      writeAuthToken('tok-123');
      state.setSelectedGenres(['Pop']);
      state.setModal('filters');
      TestBed.flushEffects();
      expect(state.selectedGenres()).toEqual(['Rock', 'Jazz']);
      clearAuthStorage();
      localStorage.clear();
    });
  });
});
