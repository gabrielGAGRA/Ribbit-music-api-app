import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { IconName, Song } from '@ribbit/shared-types';
import { AudioPlayerService } from '../../core/audio-player.service';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { IconComponent } from '../../shared/icon.component';

/** Renders full liked, loved, or rejected track collections with revision actions. */
@Component({
  selector: 'app-collection',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './collection.component.html',
  styleUrl: './collection.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CollectionComponent {
  protected readonly state = inject(RibbitStateService);
  protected readonly player = inject(AudioPlayerService);
  private readonly router = inject(Router, { optional: true });

  readonly kind = input<'like' | 'love' | 'reject'>('like');
  readonly query = signal<string>('');

  readonly accentClass = computed<string>(() => {
    const k = this.kind();
    return k === 'like' ? 'green' : k === 'love' ? 'pink' : 'red';
  });

  readonly iconName = computed<IconName>(() => {
    const k = this.kind();
    return k === 'like' ? 'heart' : k === 'love' ? 'star' : 'close';
  });

  readonly subtitle = computed<string>(() => {
    const k = this.kind();
    return k === 'like'
      ? 'músicas curtidas'
      : k === 'love'
        ? 'músicas amadas'
        : 'músicas rejeitadas';
  });

  readonly songsList = computed<readonly Song[]>(() => {
    const k = this.kind();
    if (k === 'like') return this.state.likedSongs();
    if (k === 'love') return this.state.lovedSongs();
    return this.state.rejectedSongs();
  });

  readonly totalCount = computed<number>(() => this.songsList().length);

  readonly filteredItems = computed<readonly Song[]>(() => {
    const q = this.query().toLowerCase().trim();
    const list = this.songsList();
    if (!q) return list;
    return list.filter((item) => `${item.title} ${item.artist}`.toLowerCase().includes(q));
  });

  onSearchInput(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  onSummaryAction(): void {
    const list = this.songsList();
    if (this.kind() === 'reject') {
      const firstRejected = list[0];
      if (!firstRejected) {
        this.state.notify('Nenhuma música rejeitada para revisar.');
        return;
      }
      this.state.reviseCollectionItem(firstRejected, 'reject');
      return;
    }

    const firstSong = list[0];
    if (firstSong) {
      this.state.discoverySong.set(firstSong);
      this.player.loadTrack(firstSong.previewUrl);
      this.player.play();
      this.state.notify(`Reproduzindo "${firstSong.title}".`);
    } else {
      this.state.notify('Sua coleção ainda está vazia.');
    }
  }

  onSongClick(song: Song): void {
    this.state.discoverySong.set(song);
    this.player.loadTrack(song.previewUrl);
    this.player.resetProgress();
    this.state.setPage('discover');
    void this.router?.navigate(['/discover']).catch(() => false);
  }

  onItemAction(song: Song): void {
    this.state.reviseCollectionItem(song, this.kind());
  }
}
