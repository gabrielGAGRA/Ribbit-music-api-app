import {
  Component,
  ChangeDetectionStrategy,
  inject,
  computed,
} from '@angular/core';
import { Router, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import { safeInject } from './core/safe-inject';
import { RibbitStateService } from './core/ribbit-state.service';
import { AudioPlayerService } from './core/audio-player.service';
import { IconComponent } from './shared/icon.component';
import { FrogComponent } from './shared/frog.component';
import { ToastComponent } from './shared/toast.component';
import { ModalsComponent } from './shared/modals.component';
import { AuthComponent } from './features/auth/auth.component';
import { NavigationItem, Song } from '@ribbit/shared-types';

interface PageHeading {
  readonly eyebrow: string;
  readonly titlePrefix?: string;
  readonly titleHighlight?: string;
  readonly description: string;
}

const PAGE_HEADINGS: Record<string, PageHeading> = {
  discover: {
    eyebrow: 'THE POND',
    description: '',
  },
  playlists: {
    eyebrow: 'YOUR STUDIO',
    titlePrefix: 'Seu momento. ',
    titleHighlight: 'Sua playlist.',
    description: 'Uma trilha sonora para cada versão de você.',
  },
  jams: {
    eyebrow: 'BETTER TOGETHER',
    titlePrefix: 'A mesma música. ',
    titleHighlight: 'Juntos.',
    description: 'Conecte seus gostos e descubra com seus amigos.',
  },
  explore: {
    eyebrow: 'NOVOS HORIZONTES',
    titlePrefix: 'Tem um mundo ',
    titleHighlight: 'pra ouvir.',
    description: 'Explore artistas, gêneros e histórias que merecem um play.',
  },
  settings: {
    eyebrow: 'CONFIGURAÇÕES',
    titlePrefix: 'Sua conta, ',
    titleHighlight: 'suas regras.',
    description: 'Gerencie preferências musicais, conexões e detalhes do seu plano.',
  },
  profile: {
    eyebrow: 'MY RIBBIT',
    description: '',
  },
  dashboard: {
    eyebrow: 'SUA FREQUÊNCIA',
    titlePrefix: 'Seu ano em ',
    titleHighlight: 'movimento.',
    description: 'Artistas, gêneros e momentos que desenham o seu universo musical.',
  },
  likes: {
    eyebrow: 'CURTIDAS',
    titlePrefix: 'Gostou? Ficou ',
    titleHighlight: 'por aqui.',
    description: 'Todos os sons que ganharam um coração no seu caminho.',
  },
  loved: {
    eyebrow: 'AMADAS',
    titlePrefix: 'As que bateram ',
    titleHighlight: 'diferente.',
    description: 'Suas descobertas mais especiais, reunidas em um só lugar.',
  },
  rejected: {
    eyebrow: 'REJEITADAS',
    titlePrefix: 'Nem todo som é ',
    titleHighlight: 'o seu som.',
    description: 'Revise escolhas passadas e dê uma segunda chance quando quiser.',
  },
  plans: {
    eyebrow: 'RIBBIT PLUS',
    titlePrefix: 'Mais música. ',
    titleHighlight: 'Mais você.',
    description: 'Escolha o plano que acompanha o ritmo das suas descobertas.',
  },
};

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet,
    IconComponent,
    FrogComponent,
    ToastComponent,
    ModalsComponent,
    AuthComponent,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  private readonly router: Router | null = safeInject(Router, null);

  protected readonly navigationItems: readonly NavigationItem[] = [
    { id: 'discover', label: 'Descoberta', sub: 'The Pond', icon: 'pond' },
    { id: 'playlists', label: 'Playlists', sub: 'Your Studio', icon: 'music' },
    { id: 'jams', label: 'Jams', sub: 'Better together', icon: 'users' },
    { id: 'explore', label: 'Explorar', sub: 'Find your next favorite', icon: 'search' },
    { id: 'profile', label: 'Meu perfil', sub: 'My Ribbit', icon: 'user' },
  ];

  readonly currentSong = computed<Song>(() => this.state.currentSong());

  readonly userInitials = computed<string>(() => {
    const parts = this.state.userName().trim().split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return this.state.userName().slice(0, 2).toUpperCase();
  });

  readonly isProfileArea = computed<boolean>(() => {
    return ['profile', 'dashboard', 'likes', 'loved', 'rejected', 'plans'].includes(
      this.state.activePage(),
    );
  });

  readonly breadcrumbLabel = computed<string>(() => {
    if (this.state.activePage() === 'settings') return 'Configurações';
    if (this.isProfileArea()) return 'Meu perfil';
    const nav = this.navigationItems.find((n) => n.id === this.state.activePage());
    return nav ? nav.label : 'Descoberta';
  });

  readonly currentHeading = computed<PageHeading>(() => {
    const page = this.state.activePage();
    return PAGE_HEADINGS[page] || PAGE_HEADINGS['profile'];
  });

  readonly likedCount = computed<number>(() => {
    return (
      128 + this.state.history().filter((h) => h.kind !== 'reject').length
    );
  });

  readonly lovedCount = computed<number>(() => {
    return 32 + this.state.history().filter((h) => h.kind === 'love').length;
  });

  readonly rejectedCount = computed<number>(() => {
    return 18 + this.state.history().filter((h) => h.kind === 'reject').length;
  });

  readonly isCurrentSongLiked = computed<boolean>(() => {
    const idx = this.state.currentIndex();
    return this.state
      .history()
      .some((h) => h.index === idx && h.kind !== 'reject');
  });

  readonly dailyDiscoveries = computed<number>(() => {
    return Math.min(this.state.history().length + 8, 20);
  });

  readonly dailyProgressPercent = computed<number>(() => {
    return Math.min(this.dailyDiscoveries() * 5, 100);
  });

  readonly recentDiscoveries = computed<readonly Song[]>(() => {
    return this.state.songs().slice(1, 4);
  });

  readonly formattedPlayerTime = computed<string>(() => {
    const sec = Math.round(this.player.progress() * 0.3);
    return String(sec).padStart(2, '0');
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
    protected readonly player: AudioPlayerService = inject(AudioPlayerService),
  ) {
    if (this.router) {
      this.router.events
        .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
        .subscribe((event) => {
          const path = event.urlAfterRedirects.replace(/^\//, '').split('/')[0] || 'discover';
          if (path && path !== this.state.activePage()) {
            this.state.setPage(path);
          }
        });
    }
  }

  isNavItemActive(id: string): boolean {
    if (id === 'profile') return this.isProfileArea();
    return this.state.activePage() === id;
  }

  changePage(id: string): void {
    this.state.setPage(id);
    if (this.router) {
      void this.router.navigate([`/${id}`]);
    }
  }

  openCreatePlaylist(): void {
    this.state.setModal('playlist');
  }

  openJamModal(): void {
    this.state.setModal('jam');
  }

  openFilters(): void {
    this.state.setModal('filters');
  }

  openNotifications(): void {
    this.state.setModal('notifications');
  }

  togglePlayback(): void {
    this.player.togglePlay();
  }

  likeCurrentSong(): void {
    if (!this.state.isDeckEmpty()) {
      this.state.decide('like');
    }
  }

  undoSwipe(): void {
    this.state.undo();
  }

  nextSong(): void {
    if (!this.state.isDeckEmpty()) {
      this.state.decide('reject');
    }
  }

  onProgressChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.player.setProgress(Number(target.value));
  }

  onVolumeChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.player.setVolume(Number(target.value));
  }
}
