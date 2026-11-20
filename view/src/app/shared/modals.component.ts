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
  CommunityReview,
  DeckPlaylistApiRequest,
  Song,
  SubscriptionPlan,
} from '@ribbit/shared-types';
import { FrogComponent, type FrogMood } from './frog.component';
import { IconComponent } from './icon.component';
import { RibbitStateService } from '../core/ribbit-state.service';
import type { ReviewSortOption } from '../core/services/song.service';

interface WordCloudItem {
  readonly name: string;
}

export const MAX_FAVORITE_GENRES = 3;

export const BACKEND_GENRES: readonly string[] = [
  'Rock',
  'Pop',
  'Hip Hop',
  'Grunge',
  'Indie',
  'Jazz',
  'Metal',
  'Electronic',
  'Funk',
  'Rap',
  'Trap',
  'Lo-fi',
  'Ambient',
  'Country',
  'Techno',
];

function readNamedInputValue(form: HTMLFormElement, name: string): string {
  const item = form.elements.namedItem(name) as
    | HTMLInputElement
    | HTMLSelectElement
    | HTMLTextAreaElement
    | null;
  return item?.value?.trim() ?? '';
}

/** Central modal overlay handling playlist creation, filters, track reviews, Jams, 403 upgrade notices, and mock checkout. */
@Component({
  selector: 'app-modals',
  standalone: true,
  imports: [IconComponent, FrogComponent],
  templateUrl: './modals.component.html',
  styleUrl: './modals.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModalsComponent {
  protected readonly state = inject(RibbitStateService);
  private readonly router = inject(Router, { optional: true });

  protected readonly allGenres: readonly string[] = BACKEND_GENRES;

  protected readonly blockableGenres: readonly string[] = BACKEND_GENRES;

  protected readonly searchGenreOptions: readonly string[] = ['Todos', ...BACKEND_GENRES];

  protected readonly availableFilters: readonly string[] = [
    'Referência',
    'Gênero',
    'País',
    'Duração',
    'Data Início / Fim',
    'Lineup',
  ];

  protected readonly wordCloudGenres: readonly WordCloudItem[] = BACKEND_GENRES.map((name) => ({
    name,
  }));

  readonly onboardingStep = signal<number>(1);
  readonly selectedWordCloudGenres = signal<readonly string[]>([]);
  readonly tutorialDemoAction = signal<'idle' | 'like' | 'love' | 'reject'>('idle');
  readonly tutorialTopic = signal<'swipe' | 'playlists' | 'jams' | 'family'>('swipe');
  readonly lastToggledGenre = signal<string>('Rock');
  readonly ribbyCustomSpeech = signal<string>('');

  readonly ribbyMood = computed<FrogMood>(() => {
    const demo = this.tutorialDemoAction();
    if (demo === 'love' || demo === 'like') return 'excited';
    const step = this.onboardingStep();
    if (step === 1) return 'wave';
    if (step === 2) return 'talk';
    return 'celebrate';
  });

  readonly ribbySpeech = computed<string>(() => {
    const custom = this.ribbyCustomSpeech();
    if (custom) return custom;
    const step = this.onboardingStep();
    if (step === 1) {
      const topic = this.tutorialTopic();
      if (topic === 'playlists') {
        return 'Nas Playlists Contextuais, você escolhe uma playlist de referência ou intervalo de datas e eu monto um deck sob medida pra você aprovar no swipe!';
      }
      if (topic === 'jams') {
        return 'Nas Jams Colaborativas, você cria uma sala ao vivo com seus amigos: todo mundo vota nas faixas e o som só entra na fila quando a galera aprova!';
      }
      if (topic === 'family') {
        return 'No Plano Família, a Conta Pai gerencia até 5 Contas Filhas com proteção automática contra músicas explícitas para menores de 18 anos!';
      }
      return 'Ei! Que bom que você pulou aqui no Lago! Eu sou o Ribby. Testa aí embaixo como funciona o nosso Swipe Musical ou clique nos temas pra eu te contar os segredos!';
    }
    if (step === 2) {
      const count = this.selectedWordCloudGenres().length;
      if (count === 0) {
        return 'Toque em até 3 bolhas que têm a sua cara — ou siga direto sem marcar nenhuma para explorar todo o catálogo!';
      }
      return `Boa! "${this.lastToggledGenre()}" tem uma vibe única! Já anotei ${count}/${MAX_FAVORITE_GENRES} estilo(s) pra calibrar as suas descobertas.`;
    }
    const chosen = this.selectedWordCloudGenres();
    if (chosen.length === 0) {
      return `Tudo pronto, ${this.state.userName()}! Seu radar está aberto para todos os gêneros do catálogo. Para onde vamos saltar agora?`;
    }
    return `Tudo sintonizado, ${this.state.userName()}! Seu radar já está vibrando com ${chosen.join(', ')}. Para onde vamos saltar agora?`;
  });

  protected readonly activeFilters = signal<readonly string[]>(['Referência', 'Gênero']);
  readonly jamDeckSource = signal<'livre' | 'curtidas' | 'playlist'>('livre');
  protected readonly rating = signal<number>(5);
  protected readonly paymentMethod = signal<'card' | 'pix'>('card');
  protected readonly searchGenreDraft = signal<string>('Todos');
  protected readonly searchArtistDraft = signal<string>('');
  protected readonly searchStartDateDraft = signal<string>('');
  protected readonly searchEndDateDraft = signal<string>('');
  protected readonly searchMinRatingDraft = signal<number | null>(null);
  protected readonly starScale: readonly number[] = [1, 2, 3, 4, 5];

  constructor() {
    effect(() => {
      const modal = this.state.activeModal();
      if (modal === 'search-filters') {
        this.searchGenreDraft.set(this.state.searchFilterGenre());
        this.searchArtistDraft.set(this.state.searchFilterArtist());
        this.searchStartDateDraft.set(this.state.searchFilterStartDate());
        this.searchEndDateDraft.set(this.state.searchFilterEndDate());
        this.searchMinRatingDraft.set(this.state.searchFilterMinRating());
      } else if (modal === 'details') {
        this.rating.set(5);
      }
    });
  }

  readonly currentSong = computed<Song>(() => this.state.currentSong());
  readonly detailsSong = computed<Song>(() => this.state.detailsTargetSong());
  readonly trackReviews = computed<readonly CommunityReview[]>(() =>
    this.state.activeTrackReviews(),
  );
  readonly checkoutPlan = computed<SubscriptionPlan | null>(() => this.state.pendingCheckoutPlan());

  readonly playlistViewName = computed<string>(() => {
    const modal = this.state.activeModal();
    if (modal && modal.startsWith('playlist-view:')) {
      return modal.split('playlist-view:')[1] ?? 'Playlist';
    }
    return 'Playlist';
  });

  readonly playlistViewSongs = computed<readonly Song[]>(() => {
    const name = this.playlistViewName();
    const matched = this.state.playlists().find((p) => p.name === name);
    return matched?.songs ?? this.state.songs().slice(0, 4);
  });

  onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.closeModal();
    }
  }

  closeModal(): void {
    this.state.setModal(null);
  }

  isPlaylistViewModal(): boolean {
    const modal = this.state.activeModal();
    return modal !== null && modal.startsWith('playlist-view');
  }

  onSaveQueueSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const queueName = readNamedInputValue(form, 'queueName') || 'Fim de tarde sem pressa';
    const description = readNamedInputValue(form, 'queueDescription');
    this.state.createPlaylist(
      queueName,
      18,
      description ? { description } : {},
      this.state.queueSongs(),
    );
    this.closeModal();
    this.state.setPage('playlists');
    void this.router?.navigate(['/playlists']).catch(() => false);
  }

  selectSearchGenre(genre: string): void {
    this.searchGenreDraft.set(genre);
  }

  onSearchArtistInput(event: Event): void {
    this.searchArtistDraft.set((event.target as HTMLInputElement).value);
  }

  onSearchStartDateInput(event: Event): void {
    this.searchStartDateDraft.set((event.target as HTMLInputElement).value);
  }

  onSearchEndDateInput(event: Event): void {
    this.searchEndDateDraft.set((event.target as HTMLInputElement).value);
  }

  onSearchMinRatingChange(event: Event): void {
    const raw = (event.target as HTMLSelectElement).value.trim();
    if (!raw) {
      this.searchMinRatingDraft.set(null);
      return;
    }
    const parsed = Number(raw);
    this.searchMinRatingDraft.set(
      Number.isFinite(parsed) && parsed >= 1 && parsed <= 5 ? parsed : null,
    );
  }

  applyFilters(): void {
    this.state.searchFilterGenre.set(this.searchGenreDraft());
    this.state.searchFilterArtist.set(this.searchArtistDraft().trim());
    this.state.searchFilterStartDate.set(this.searchStartDateDraft());
    this.state.searchFilterEndDate.set(this.searchEndDateDraft());
    this.state.searchFilterMinRating.set(this.searchMinRatingDraft());
    this.state.searchFilterYear.set(undefined);
    this.closeModal();
    this.state.notify('Filtros de busca aplicados.');
  }

  isGenreSelected(genre: string): boolean {
    return this.state.selectedGenres().includes(genre);
  }

  toggleSelectedGenre(genre: string): void {
    const list = this.state.selectedGenres();
    if (list.includes(genre)) {
      this.state.setSelectedGenres(list.filter((g) => g !== genre));
      return;
    }
    if (list.length >= MAX_FAVORITE_GENRES) {
      this.state.notify(`Selecione no máximo ${MAX_FAVORITE_GENRES} gêneros favoritos.`);
      return;
    }
    this.state.setSelectedGenres([...list, genre]);
  }

  isGenreBlocked(genre: string): boolean {
    return this.state.blockedGenres().includes(genre);
  }

  toggleBlockedGenre(genre: string): void {
    const list = this.state.blockedGenres();
    const updated = list.includes(genre) ? list.filter((g) => g !== genre) : [...list, genre];
    this.state.setBlockedGenres(updated);
  }

  saveFrequencies(): void {
    this.state.saveFavoriteGenres(this.state.selectedGenres());
    this.closeModal();
    this.state.notify('Sua frequência foi atualizada.');
  }

  isFilterActive(filter: string): boolean {
    return this.activeFilters().includes(filter);
  }

  toggleFilter(filter: string): void {
    const list = this.activeFilters();
    this.activeFilters.set(
      list.includes(filter) ? list.filter((f) => f !== filter) : [...list, filter],
    );
  }

  onCreatePlaylistSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const name = readNamedInputValue(form, 'name') || 'Minha nova frequência';
    const rawDuration = Number(readNamedInputValue(form, 'duration'));
    const duration = Number.isFinite(rawDuration) && rawDuration >= 10 ? rawDuration : 45;
    const extraFilters = this.extractPlaylistFilters(form);

    this.state.createPlaylist(name, duration, extraFilters);
    this.closeModal();
    this.state.setPage('playlists');
    void this.router?.navigate(['/playlists']).catch(() => false);
  }

  addToExistingPlaylist(index: number): void {
    this.state.addSongToPlaylist(index);
    this.closeModal();
  }

  openCreateFromAdd(): void {
    this.state.setModal('playlist');
  }

  onJamDeckSourceChange(event: Event): void {
    const val = (event.target as HTMLSelectElement).value as 'livre' | 'curtidas' | 'playlist';
    this.jamDeckSource.set(val);
  }

  onCreateJamSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const roomName = readNamedInputValue(form, 'roomName') || this.state.jamState().roomName;
    const durationMinutes = this.parseJamDuration(form);
    const threshold = Number(readNamedInputValue(form, 'threshold')) || 3;
    const deckSource = (readNamedInputValue(form, 'deck_source') ||
      this.jamDeckSource() ||
      'livre') as 'livre' | 'curtidas' | 'playlist';
    const sourcePlaylistId = this.parseJamSourcePlaylist(form, deckSource);
    const maxSuperlikes = Number(readNamedInputValue(form, 'max_superlikes')) || 5;

    this.state.createJamRoom({
      room_name: roomName,
      duration_minutes: durationMinutes,
      skip_votes_threshold: threshold,
      deck_source: deckSource,
      source_playlist_id: sourcePlaylistId,
      max_superlikes: maxSuperlikes,
    });
    this.closeModal();
    this.state.setPage('jams');
    void this.router?.navigate(['/jams']).catch(() => false);
  }

  private parseJamDuration(form: HTMLFormElement): number {
    const hours = Number(readNamedInputValue(form, 'hours')) || 0;
    const minutes = Number(readNamedInputValue(form, 'minutes')) || 0;
    return Math.max(15, hours * 60 + minutes);
  }

  private parseJamSourcePlaylist(
    form: HTMLFormElement,
    deckSource: 'livre' | 'curtidas' | 'playlist',
  ): number | null {
    if (deckSource !== 'playlist') {
      return null;
    }
    const raw = readNamedInputValue(form, 'source_playlist_id');
    const parsed = Number(raw);
    return parsed > 0 ? parsed : null;
  }

  rateSong(stars: number): void {
    this.rating.set(stars);
  }

  onCommentSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const input = form.elements.namedItem('commentText') as HTMLInputElement;
    const text = input.value.trim();
    const currentRating = this.rating();
    if (currentRating >= 1 && currentRating <= 5) {
      this.state.publishTrackReview(currentRating, text);
      input.value = '';
    }
  }

  onTrackReviewSortChange(event: Event): void {
    const sortBy = (event.target as HTMLSelectElement).value as ReviewSortOption;
    this.state.loadReviewsForTrack(this.detailsSong(), sortBy);
  }

  deleteReview(reviewId: number): void {
    this.state.deleteTrackReview(reviewId);
  }

  isOwnReview(review: CommunityReview): boolean {
    const uid = this.state.userId();
    return uid !== null && review.userId === uid;
  }

  selectPaymentMethod(method: 'card' | 'pix'): void {
    this.paymentMethod.set(method);
  }

  onCheckoutSubmit(event: Event): void {
    event.preventDefault();
    this.state.confirmMockPlanCheckout(this.paymentMethod());
  }

  goToPlansFromUpgrade(): void {
    this.closeModal();
    this.state.setPage('plans');
    void this.router?.navigate(['/plans']).catch(() => false);
  }

  goToSettingsFromSpotify(): void {
    this.closeModal();
    this.state.setPage('settings');
    void this.router?.navigate(['/settings']).catch(() => false);
  }

  addBySwipe(): void {
    this.closeModal();
    this.state.setPage('discover');
    void this.router?.navigate(['/discover']).catch(() => false);
    this.state.notify('Descubra músicas e use + para adicionar à playlist.');
  }

  confirmDeleteAccount(): void {
    this.state.deleteAccount();
  }

  goToExploreRadar(): void {
    this.closeModal();
    this.state.setPage('explore');
    void this.router?.navigate(['/explore']).catch(() => false);
  }

  private extractPlaylistFilters(
    form: HTMLFormElement,
  ): Omit<DeckPlaylistApiRequest, 'name' | 'duration_minutes'> {
    const res: Record<string, unknown> = {};
    if (this.isFilterActive('Gênero')) {
      const g = readNamedInputValue(form, 'genre');
      if (g) res['genre'] = g;
    }
    const artists = this.extractPlaylistArtists(form);
    if (artists.length === 1) res['artist'] = artists[0];
    else if (artists.length > 1) res['artist'] = artists;

    const country = readNamedInputValue(form, 'country');
    if (country) res['country'] = country;
    const description = readNamedInputValue(form, 'description');
    if (description) res['description'] = description;

    const years = this.extractPlaylistYears(form);
    if (years !== undefined) res['year'] = years;

    const { referencePlaylistId, sourcePlaylistId } = this.extractPlaylistSources(form);
    if (referencePlaylistId !== undefined) res['reference_playlist_id'] = referencePlaylistId;
    if (sourcePlaylistId !== undefined) res['source_playlist_id'] = sourcePlaylistId;

    Object.assign(res, this.extractPlaylistDates(form));

    return res as Omit<DeckPlaylistApiRequest, 'name' | 'duration_minutes'>;
  }

  private extractPlaylistDates(form: HTMLFormElement): { startDate?: string; endDate?: string } {
    const startDate = readNamedInputValue(form, 'startDate');
    const endDate = readNamedInputValue(form, 'endDate');
    return {
      ...(startDate ? { startDate } : {}),
      ...(endDate ? { endDate } : {}),
    };
  }

  private extractPlaylistArtists(form: HTMLFormElement): string[] {
    if (!this.isFilterActive('Lineup')) {
      return [];
    }
    const lineup = readNamedInputValue(form, 'lineup');
    return lineup
      ? lineup
          .split(',')
          .map((a) => a.trim())
          .filter(Boolean)
      : [];
  }

  private isDateFilterActive(): boolean {
    return (
      this.isFilterActive('Data Início / Fim') ||
      this.isFilterActive('Data Início e Fim') ||
      this.isFilterActive('Data') ||
      this.isFilterActive('Época')
    );
  }

  private extractPlaylistYears(form: HTMLFormElement): number[] | undefined {
    if (!this.isDateFilterActive()) {
      return undefined;
    }
    const startDate = readNamedInputValue(form, 'startDate');
    const endDate = readNamedInputValue(form, 'endDate');
    if (!startDate && !endDate) {
      return undefined;
    }
    const startYear = startDate ? Number(startDate.split('-')[0]) : 1970;
    const endYear = endDate ? Number(endDate.split('-')[0]) : new Date().getUTCFullYear();
    if (!Number.isNaN(startYear) && !Number.isNaN(endYear) && startYear <= endYear) {
      return Array.from({ length: endYear - startYear + 1 }, (_, i) => startYear + i);
    }
    return undefined;
  }

  private extractPlaylistSources(form: HTMLFormElement): {
    referencePlaylistId?: number;
    sourcePlaylistId?: number;
  } {
    const rawRef = this.isFilterActive('Referência')
      ? readNamedInputValue(form, 'referencePlaylistId') ||
        readNamedInputValue(form, 'source_playlist_id') ||
        readNamedInputValue(form, 'sourcePlaylistId')
      : '';
    const refNum = Number(rawRef);
    const referencePlaylistId = Number.isFinite(refNum) && refNum > 0 ? refNum : undefined;

    const rawSource =
      readNamedInputValue(form, 'source_playlist_id') ||
      readNamedInputValue(form, 'sourcePlaylistId') ||
      rawRef;
    const sourceNum = Number(rawSource);
    const hasSource = Number.isFinite(sourceNum) && sourceNum > 0;
    const sourcePlaylistId = hasSource ? sourceNum : referencePlaylistId;

    return { referencePlaylistId, sourcePlaylistId };
  }

  nextOnboardingStep(): void {
    this.ribbyCustomSpeech.set('');
    this.onboardingStep.update((s) => Math.min(3, s + 1));
  }

  prevOnboardingStep(): void {
    this.ribbyCustomSpeech.set('');
    this.onboardingStep.update((s) => Math.max(1, s - 1));
  }

  goToOnboardingStep(step: number): void {
    this.ribbyCustomSpeech.set('');
    this.onboardingStep.set(Math.max(1, Math.min(3, step)));
  }

  selectTutorialTopic(topic: 'swipe' | 'playlists' | 'jams' | 'family'): void {
    this.ribbyCustomSpeech.set('');
    this.tutorialTopic.set(topic);
  }

  triggerDemoSwipe(action: 'like' | 'love' | 'reject'): void {
    this.tutorialDemoAction.set(action);
    if (action === 'like') {
      this.ribbyCustomSpeech.set(
        'Deslizou pra direita! A música vai direto pras suas Curtidas (ou pra Playlist que você marcou no seletor)!',
      );
    } else if (action === 'love') {
      this.ribbyCustomSpeech.set(
        'Superlike! Deslizou pra cima quando a música arrepia: ela entra nas suas Amadas com destaque especial!',
      );
    } else {
      this.ribbyCustomSpeech.set(
        'Deslizou pra esquerda! Sem estresse: eu entendo o recado e não repito mais essa faixa no seu lago.',
      );
    }
    setTimeout(() => {
      if (this.tutorialDemoAction() === action) {
        this.tutorialDemoAction.set('idle');
      }
    }, 850);
  }

  pokeRibby(): void {
    const phrases = [
      'Ribbit! Sabia que você pode usar uma playlist sua como referência pra criar outra?',
      'Ribbit! Dica de ouro: na Descoberta você escolhe na lateral direita se o swipe salva nas Curtidas ou direto numa Playlist!',
      'Ribbit! Nas Jams, se a galera der Superlike suficiente, a música fura a fila na hora!',
    ];
    const random = phrases[Math.floor(Math.random() * phrases.length)] ?? phrases[0]!;
    this.ribbyCustomSpeech.set(random);
  }

  isWordCloudSelected(genre: string): boolean {
    return this.selectedWordCloudGenres().includes(genre);
  }

  toggleWordCloudGenre(genre: string): void {
    this.ribbyCustomSpeech.set('');
    const list = this.selectedWordCloudGenres();
    if (list.includes(genre)) {
      this.selectedWordCloudGenres.set(list.filter((g) => g !== genre));
      return;
    }
    if (list.length >= MAX_FAVORITE_GENRES) {
      this.ribbyCustomSpeech.set(
        `Você pode escolher no máximo ${MAX_FAVORITE_GENRES} gêneros! Desmarque um se quiser trocar.`,
      );
      this.state.notify(`Selecione no máximo ${MAX_FAVORITE_GENRES} gêneros.`);
      return;
    }
    this.lastToggledGenre.set(genre);
    this.selectedWordCloudGenres.set([...list, genre]);
  }

  savePreferencesAndNext(): void {
    this.ribbyCustomSpeech.set('');
    const chosen = this.selectedWordCloudGenres().slice(0, MAX_FAVORITE_GENRES);
    this.state.saveFavoriteGenres(chosen);
    if (typeof localStorage !== 'undefined') {
      const email = this.state.userEmail() || 'user';
      localStorage.setItem(`ribbit:onboarding_done:${email}`, 'true');
    }
    this.onboardingStep.set(3);
  }

  finishOnboarding(): void {
    this.ribbyCustomSpeech.set('');
    const chosen = this.selectedWordCloudGenres().slice(0, MAX_FAVORITE_GENRES);
    this.state.saveFavoriteGenres(chosen);
    if (typeof localStorage !== 'undefined') {
      const email = this.state.userEmail() || 'user';
      localStorage.setItem(`ribbit:onboarding_done:${email}`, 'true');
    }
    this.closeModal();
    this.onboardingStep.set(1);
  }

  finishAndNavigate(page: string): void {
    this.finishOnboarding();
    this.state.setPage(page);
    if (this.router) {
      void this.router.navigate([`/${page}`]).catch(() => false);
    }
  }
}
