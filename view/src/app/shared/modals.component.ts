import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import type {
  CommunityReview,
  DeckPlaylistApiRequest,
  Song,
  SubscriptionPlan,
} from '@ribbit/shared-types';
import { IconComponent } from './icon.component';
import { RibbitStateService } from '../core/ribbit-state.service';

function mapDecadeLabelToYear(decade: string): number | undefined {
  switch (decade) {
    case 'Anos 2020':
      return 2022;
    case 'Anos 2010':
      return 2015;
    case 'Anos 2000':
      return 2005;
    case 'Anos 90':
      return 1995;
    case 'Anos 80':
      return 1985;
    default:
      return undefined;
  }
}

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
  imports: [IconComponent],
  templateUrl: './modals.component.html',
  styleUrl: './modals.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModalsComponent {
  protected readonly state = inject(RibbitStateService);
  private readonly router = inject(Router, { optional: true });

  protected readonly allGenres: readonly string[] = [
    'Indie',
    'R&B / Soul',
    'Eletrônica',
    'Indie Folk',
    'Indie Pop',
    'Dream Pop',
    'Rock',
    'MPB',
    'Hip-hop',
    'Jazz',
  ];

  protected readonly blockableGenres: readonly string[] = [
    'Indie Folk',
    'Eletrônica',
    'R&B / Soul',
    'Indie Pop',
    'Dream Pop',
    'Rock',
    'Hip-hop',
  ];

  protected readonly searchGenreOptions: readonly string[] = [
    'Todos',
    'Indie',
    'Pop',
    'Rock',
    'Eletrônica',
    'R&B / Soul',
    'MPB',
  ];

  protected readonly availableFilters: readonly string[] = [
    'Referência',
    'Gênero',
    'Duração',
    'Evento',
    'Lineup',
    'Época',
  ];

  protected readonly activeFilters = signal<readonly string[]>(['Referência', 'Gênero']);
  protected readonly rating = signal<number>(5);
  protected readonly paymentMethod = signal<'card' | 'pix'>('card');
  protected readonly searchGenreDraft = signal<string>('Todos');
  protected readonly searchDecadeDraft = signal<string>('Todas as épocas');

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

  onSearchDecadeChange(event: Event): void {
    this.searchDecadeDraft.set((event.target as HTMLSelectElement).value);
  }

  applyFilters(): void {
    this.state.searchFilterGenre.set(this.searchGenreDraft());
    this.state.searchFilterYear.set(mapDecadeLabelToYear(this.searchDecadeDraft()));
    this.closeModal();
    this.state.notify('Filtros de busca aplicados.');
  }

  isGenreSelected(genre: string): boolean {
    return this.state.selectedGenres().includes(genre);
  }

  toggleSelectedGenre(genre: string): void {
    const list = this.state.selectedGenres();
    const updated = list.includes(genre) ? list.filter((g) => g !== genre) : [...list, genre];
    this.state.setSelectedGenres(updated);
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

  onCreateJamSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const roomName = readNamedInputValue(form, 'roomName') || this.state.jamState().roomName;
    const hours = Number(readNamedInputValue(form, 'hours')) || 0;
    const minutes = Number(readNamedInputValue(form, 'minutes')) || 0;
    const threshold = Number(readNamedInputValue(form, 'threshold')) || 3;
    const durationMinutes = Math.max(15, hours * 60 + minutes);

    this.state.createJamRoom({
      room_name: roomName,
      duration_minutes: durationMinutes,
      skip_votes_threshold: threshold,
    });
    this.closeModal();
    this.state.setPage('jams');
    void this.router?.navigate(['/jams']).catch(() => false);
  }

  rateSong(stars: number): void {
    this.rating.set(stars);
  }

  onCommentSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const input = form.elements.namedItem('commentText') as HTMLInputElement;
    const text = input.value.trim();
    if (text) {
      this.state.publishTrackReview(this.rating(), text);
      input.value = '';
    }
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
    const genre = this.isFilterActive('Gênero') ? readNamedInputValue(form, 'genre') : '';
    const lineup = this.isFilterActive('Lineup') ? readNamedInputValue(form, 'lineup') : '';
    const firstArtist = lineup.split(',')[0]?.trim() ?? '';
    const decade = this.isFilterActive('Época') ? readNamedInputValue(form, 'decade') : '';
    const releaseYear = mapDecadeLabelToYear(decade);

    return {
      ...(genre ? { genre } : {}),
      ...(firstArtist ? { artist: firstArtist } : {}),
      ...(releaseYear !== undefined ? { release_year: releaseYear } : {}),
    };
  }
}
