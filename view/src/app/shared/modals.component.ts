import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { Router } from '@angular/router';
import { safeInject } from '../core/safe-inject';
import { RibbitStateService } from '../core/ribbit-state.service';
import { MOCK_REVIEWS } from '../core/mocks/reviews.mock';
import { IconComponent } from './icon.component';
import { Song, CommunityReview } from '@ribbit/shared-types';

@Component({
  selector: 'app-modals',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './modals.component.html',
  styleUrl: './modals.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModalsComponent {
  private readonly router: Router | null = safeInject(Router, null);

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
  ];

  protected readonly availableFilters: readonly string[] = [
    'Referência',
    'Gênero',
    'Duração',
    'Evento',
    'Lineup',
    'Época',
  ];

  protected readonly communityReviews: readonly CommunityReview[] = MOCK_REVIEWS;

  protected readonly activeFilters = signal<readonly string[]>([
    'Referência',
    'Gênero',
  ]);
  protected readonly rating = signal<number>(0);

  readonly currentSong = computed<Song>(() => this.state.currentSong());

  readonly playlistViewName = computed<string>(() => {
    const modal = this.state.activeModal();
    if (modal && modal.startsWith('playlist-view:')) {
      return modal.split('playlist-view:')[1];
    }
    return 'Playlist';
  });

  readonly playlistViewSongs = computed<readonly Song[]>(() => {
    return this.state.songs().slice(0, 4);
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
  ) {}

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
    const nameInput = form.elements.namedItem('queueName') as HTMLInputElement;
    this.state.createPlaylist(nameInput.value || 'Fim de tarde sem pressa', 18);
    this.closeModal();
    this.state.setPage('playlists');
    void this.router?.navigate(['/playlists']);
    this.state.notify('Fila salva como playlist permanente.');
  }

  applyFilters(): void {
    this.closeModal();
    this.state.notify('Filtros de busca aplicados.');
  }

  isGenreSelected(genre: string): boolean {
    return this.state.selectedGenres().includes(genre);
  }

  toggleSelectedGenre(genre: string): void {
    const list = this.state.selectedGenres();
    const updated = list.includes(genre)
      ? list.filter((g) => g !== genre)
      : [...list, genre];
    this.state.setSelectedGenres(updated);
  }

  isGenreBlocked(genre: string): boolean {
    return this.state.blockedGenres().includes(genre);
  }

  toggleBlockedGenre(genre: string): void {
    const list = this.state.blockedGenres();
    const updated = list.includes(genre)
      ? list.filter((g) => g !== genre)
      : [...list, genre];
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
    const nameInput = form.elements.namedItem('name') as HTMLInputElement;
    const durationInput = form.elements.namedItem('duration') as HTMLInputElement | null;
    const dur = durationInput ? Number(durationInput.value) || 45 : 45;
    this.state.createPlaylist(nameInput.value, dur);
    this.closeModal();
    this.state.setPage('playlists');
    void this.router?.navigate(['/playlists']);
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
    const roomInput = form.elements.namedItem('roomName') as HTMLInputElement;
    const hoursInput = form.elements.namedItem('hours') as HTMLInputElement;
    const minInput = form.elements.namedItem('minutes') as HTMLInputElement;
    const threshInput = form.elements.namedItem('threshold') as HTMLInputElement;

    const current = this.state.jamState();
    this.state.jamState.set({
      ...current,
      active: true,
      roomName: roomInput.value || current.roomName,
      durationHours: Number(hoursInput.value) || current.durationHours,
      durationMinutes: Number(minInput.value) || current.durationMinutes,
      voteThreshold: Number(threshInput.value) || current.voteThreshold,
    });

    this.closeModal();
    this.state.setPage('jams');
    void this.router?.navigate(['/jams']);
    this.state.notify('Jam de demonstração criada. Código: RIBBIT-729');
  }

  rateSong(stars: number): void {
    this.rating.set(stars);
    this.state.notify(`Avaliação de ${stars} estrelas registrada.`);
  }

  onCommentSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const input = form.elements.namedItem('commentText') as HTMLInputElement;
    if (input.value.trim()) {
      this.state.addComment(input.value);
      input.value = '';
    }
  }

  deleteMyComment(index: number): void {
    this.state.deleteComment(index);
  }

  addBySwipe(): void {
    this.closeModal();
    this.state.setPage('discover');
    void this.router?.navigate(['/discover']);
    this.state.notify('Descubra músicas e use + para adicionar à playlist.');
  }

  confirmDeleteAccount(): void {
    this.state.deleteAccount();
  }

  goToExploreRadar(): void {
    this.closeModal();
    this.state.setPage('explore');
    void this.router?.navigate(['/explore']);
  }
}
