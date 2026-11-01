import {
  Component,
  ChangeDetectionStrategy,
  inject,
  input,
  signal,
  computed,
} from '@angular/core';
import { Router } from '@angular/router';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { SongService } from '../../core/services/song.service';
import { safeInject } from '../../core/safe-inject';
import { AudioPlayerService } from '../../core/audio-player.service';
import { IconComponent } from '../../shared/icon.component';
import { Song, IconName } from '@ribbit/shared-types';

@Component({
  selector: 'app-collection',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './collection.component.html',
  styleUrl: './collection.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CollectionComponent {
  private readonly router: Router | null = safeInject(Router, null);
  protected readonly songService: SongService = safeInject(SongService, new SongService());

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
    const history = this.state.history();
    const allSongs = this.state.songs();
    const defaults =
      k === 'like' ? [0, 1, 2, 3] : k === 'love' ? [1, 3, 4] : [4, 5];

    const historyItems = history
      .filter((item) => (k === 'like' ? item.kind !== 'reject' : item.kind === k))
      .map((item) => item.index % allSongs.length);

    const indexes = [...new Set([...historyItems, ...defaults])].filter((idx) => {
      const decision = history.find((item) => item.index === idx);
      if (!decision) return true;
      return k === 'like' ? decision.kind !== 'reject' : decision.kind === k;
    });

    return indexes.map((idx) => allSongs[idx]);
  });

  readonly totalCount = computed<number>(() => {
    const k = this.kind();
    const base = k === 'like' ? 128 : k === 'love' ? 32 : 18;
    return this.songsList().length + base;
  });

  readonly filteredItems = computed<readonly Song[]>(() => {
    const q = this.query().toLowerCase().trim();
    const list = this.songsList();
    if (!q) return list;
    return list.filter((item) =>
      `${item.title} ${item.artist}`.toLowerCase().includes(q),
    );
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
    protected readonly player: AudioPlayerService = inject(AudioPlayerService),
  ) {}

  onSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.query.set(target.value);
  }

  onSummaryAction(): void {
    if (this.kind() === 'reject') {
      const updated = this.state.history().filter((item) => item.kind !== 'reject');
      this.state.history.set(updated);
      this.state.notify('Suas rejeições foram revisadas.');
    } else {
      this.player.play();
      this.state.notify('Reproduzindo sua coleção em modo demonstrativo.');
    }
  }

  onSongClick(song: Song): void {
    const idx = this.state.songs().indexOf(song);
    if (idx >= 0) {
      this.state.currentIndex.set(idx);
      this.player.resetProgress();
      this.state.setPage('discover');
      void this.router?.navigate(['/discover']);
    }
  }

  onItemAction(song: Song): void {
    const idx = this.state.songs().indexOf(song);
    const updated = this.state.history().filter((decision) => decision.index !== idx);
    this.state.history.set(updated);

    if (this.kind() === 'reject') {
      this.state.currentIndex.set(idx);
      this.state.setPage('discover');
      void this.router?.navigate(['/discover']);
      this.state.notify('Essa faixa voltou para o The Pond.');
    } else {
      this.state.notify('Faixa removida da coleção.');
    }
  }
}
