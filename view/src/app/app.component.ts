import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { EMPTY } from 'rxjs';
import { filter } from 'rxjs/operators';
import type { NavigationItem, Playlist } from '@ribbit/shared-types';
import { computeInitials } from './core/api-mappers';
import { AudioPlayerService } from './core/audio-player.service';
import { RibbitStateService } from './core/ribbit-state.service';
import { AuthComponent } from './features/auth/auth.component';
import { FrogComponent } from './shared/frog.component';
import { IconComponent } from './shared/icon.component';
import { ModalsComponent } from './shared/modals.component';
import { ToastComponent } from './shared/toast.component';

interface PageHeading {
  readonly eyebrow: string;
  readonly titlePrefix?: string;
  readonly titleHighlight?: string;
  readonly description: string;
}

const DEFAULT_PAGE_HEADING: PageHeading = {
  eyebrow: 'MY RIBBIT',
  description: '',
};

const PAGE_HEADINGS: Record<string, PageHeading> = {
  discover: {
    eyebrow: 'FIND YOUR NEXT FAVORITE',
    description: '',
  },
  playlists: {
    eyebrow: 'YOUR STUDIO',
    titlePrefix: 'Seu momento. ',
    titleHighlight: 'Sua playlist.',
    description: 'Uma trilha sonora para cada versão de você.',
  },
  jams: {
    eyebrow: 'THE POND',
    titlePrefix: 'A mesma música. ',
    titleHighlight: 'Juntos.',
    description: 'Conecte seus gostos e descubra com seus amigos.',
  },
  explore: {
    eyebrow: 'COMUNIDADE',
    titlePrefix: 'Tem um mundo ',
    titleHighlight: 'pra ouvir.',
    description: 'Busque faixas, explore lançamentos e acompanhe os reviews da comunidade.',
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
  family: {
    eyebrow: 'PLANO FAMÍLIA',
    titlePrefix: 'Conta Pai e ',
    titleHighlight: 'Contas Filhas.',
    description: 'Gerencie os perfis dependentes, vagas e proteção etária do seu grupo familiar.',
  },
};

/** Root application shell hosting sidebar navigation, active feature outlet, right rail, and bottom player. */
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
  protected readonly state = inject(RibbitStateService);
  private readonly player = inject(AudioPlayerService);
  private readonly router = inject(Router, { optional: true });

  protected readonly isAdminRoute = signal<boolean>(
    typeof window !== 'undefined' && window.location.pathname.startsWith('/admin'),
  );

  protected readonly navigationItems: readonly NavigationItem[] = [
    { id: 'discover', label: 'Descoberta', sub: 'Find your next favorite', icon: 'pond' },
    { id: 'playlists', label: 'Playlists', sub: 'Your Studio', icon: 'music' },
    { id: 'jams', label: 'Jams', sub: 'The Pond', icon: 'users' },
    { id: 'explore', label: 'Comunidade', sub: 'Reviews & Busca', icon: 'search' },
    { id: 'profile', label: 'Meu perfil', sub: 'My Ribbit', icon: 'user' },
  ];

  protected readonly userInitials = computed<string>(() => computeInitials(this.state.userName()));

  private readonly isProfileArea = computed<boolean>(() =>
    ['profile', 'dashboard', 'likes', 'loved', 'rejected', 'plans', 'family'].includes(
      this.state.activePage(),
    ),
  );

  protected readonly breadcrumbLabel = computed<string>(() => {
    if (this.state.activePage() === 'settings') return 'Configurações';
    if (this.state.activePage() === 'family') return 'Plano Família';
    if (this.isProfileArea()) return 'Meu perfil';
    const nav = this.navigationItems.find((item) => item.id === this.state.activePage());
    return nav ? nav.label : 'Descoberta';
  });

  protected readonly currentHeading = computed<PageHeading>(() => {
    const page = this.state.activePage();
    return PAGE_HEADINGS[page] ?? DEFAULT_PAGE_HEADING;
  });

  protected readonly likedCount = computed<number>(() => this.state.likedSongs().length);
  protected readonly lovedCount = computed<number>(() => this.state.lovedSongs().length);
  protected readonly rejectedCount = computed<number>(() => this.state.rejectedSongs().length);
  protected readonly sidebarPlaylists = computed<readonly Playlist[]>(() =>
    this.state.playlists().slice(0, 2),
  );

  protected formatCappedCount(count: number): string {
    return count > 99 ? '99+' : String(count);
  }

  private readonly navigationEnd = toSignal(
    this.router
      ? this.router.events.pipe(
          filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        )
      : EMPTY,
    { initialValue: null },
  );

  constructor() {
    let previousPage = this.state.activePage();
    effect(() => {
      const currentPage = this.state.activePage();
      const authView = this.state.authView();
      if (currentPage !== previousPage || authView !== 'app') {
        previousPage = currentPage;
        this.player.pause();
      }
    });

    if (this.router) {
      this.isAdminRoute.set(this.router.url.startsWith('/admin'));
    }
    effect(() => {
      const event = this.navigationEnd();
      if (!event) return;
      const isAdmin = event.urlAfterRedirects.startsWith('/admin');
      this.isAdminRoute.set(isAdmin);
      if (isAdmin) return;
      const path = this.resolveActivePageFromUrl(event.urlAfterRedirects);
      if (path && path !== this.state.activePage()) {
        this.state.setPage(path);
      }
    });
  }

  private resolveActivePageFromUrl(url: string): string {
    const rawSegment = url.replace(/^\//, '').split(/[/?#]/)[0] || 'discover';
    return rawSegment === 'callback' ? 'settings' : rawSegment;
  }

  protected isNavItemActive(id: string): boolean {
    if (id === 'profile') return this.isProfileArea();
    return this.state.activePage() === id;
  }

  protected changePage(id: string): void {
    if (id === 'playlists') {
      this.state.resetPlaylistsView();
    }
    this.state.setPage(id);
    if (this.router) {
      void this.router.navigate([`/${id}`]).catch(() => false);
    }
  }

  protected openCreatePlaylist(): void {
    this.state.setModal('playlist');
  }

  protected openJamModal(): void {
    if (!this.state.isSpotifyLinked()) {
      this.state.promptSpotifyConnection(
        'Conecte sua conta do Spotify para criar uma Jam no Pond.',
      );
      return;
    }
    if (!this.state.spotifyPremium()) {
      this.state.notify('Uma conta Spotify Premium é necessária para criar uma Jam no Pond.');
      return;
    }
    this.state.setModal('jam');
  }

  protected openNotifications(): void {
    this.state.setModal('notifications');
  }

  protected setTheme(theme: 'light' | 'dark'): void {
    this.state.setTheme(theme);
  }
}
