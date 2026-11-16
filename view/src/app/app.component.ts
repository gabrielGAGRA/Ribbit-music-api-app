import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs/operators';
import type { NavigationItem, Song } from '@ribbit/shared-types';
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
  private readonly router = inject(Router, { optional: true });

  readonly isAdminRoute = signal<boolean>(
    typeof window !== 'undefined' && window.location.pathname.startsWith('/admin'),
  );

  protected readonly navigationItems: readonly NavigationItem[] = [
    { id: 'discover', label: 'Descoberta', sub: 'The Pond', icon: 'pond' },
    { id: 'playlists', label: 'Playlists', sub: 'Your Studio', icon: 'music' },
    { id: 'jams', label: 'Jams', sub: 'Better together', icon: 'users' },
    { id: 'explore', label: 'Explorar', sub: 'Find your next favorite', icon: 'search' },
    { id: 'profile', label: 'Meu perfil', sub: 'My Ribbit', icon: 'user' },
  ];

  readonly userInitials = computed<string>(() => {
    const parts = this.state
      .userName()
      .trim()
      .split(/\s+/)
      .filter((item) => item.length > 0);
    if (parts.length >= 2) {
      return `${parts[0]![0] ?? ''}${parts[1]![0] ?? ''}`.toUpperCase();
    }
    return this.state.userName().slice(0, 2).toUpperCase() || 'RB';
  });

  readonly isProfileArea = computed<boolean>(() =>
    ['profile', 'dashboard', 'likes', 'loved', 'rejected', 'plans', 'family'].includes(
      this.state.activePage(),
    ),
  );

  readonly breadcrumbLabel = computed<string>(() => {
    if (this.state.activePage() === 'settings') return 'Configurações';
    if (this.state.activePage() === 'family') return 'Plano Família';
    if (this.isProfileArea()) return 'Meu perfil';
    const nav = this.navigationItems.find((item) => item.id === this.state.activePage());
    return nav ? nav.label : 'Descoberta';
  });

  readonly currentHeading = computed<PageHeading>(() => {
    const page = this.state.activePage();
    return PAGE_HEADINGS[page] ?? PAGE_HEADINGS['profile']!;
  });

  readonly likedCount = computed<number>(() => this.state.likedSongs().length);
  readonly lovedCount = computed<number>(() => this.state.lovedSongs().length);
  readonly rejectedCount = computed<number>(() => this.state.rejectedSongs().length);

  readonly dailyDiscoveries = computed<number>(() =>
    Math.min(this.likedCount() + this.rejectedCount(), 20),
  );

  readonly dailyProgressPercent = computed<number>(() =>
    Math.min(this.dailyDiscoveries() * 5, 100),
  );

  readonly recentDiscoveries = computed<readonly Song[]>(() => {
    const liked = this.state.likedSongs();
    return liked.length > 0 ? liked.slice(0, 3) : this.state.songs().slice(0, 3);
  });

  constructor() {
    if (this.router) {
      this.isAdminRoute.set(this.router.url.startsWith('/admin'));
      this.router.events
        .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
        .subscribe((event) => {
          const isAdmin = event.urlAfterRedirects.startsWith('/admin');
          this.isAdminRoute.set(isAdmin);
          if (isAdmin) return;
          const path = this.resolveActivePageFromUrl(event.urlAfterRedirects);
          if (path && path !== this.state.activePage()) {
            this.state.setPage(path);
          }
        });
    }
  }

  resolveActivePageFromUrl(url: string): string {
    const rawSegment = url.replace(/^\//, '').split(/[/?#]/)[0] || 'discover';
    return rawSegment === 'callback' ? 'settings' : rawSegment;
  }

  isNavItemActive(id: string): boolean {
    if (id === 'profile') return this.isProfileArea();
    return this.state.activePage() === id;
  }

  changePage(id: string): void {
    this.state.setPage(id);
    if (this.router) {
      void this.router.navigate([`/${id}`]).catch(() => false);
    }
  }

  openCreatePlaylist(): void {
    this.state.setModal('playlist');
  }

  openJamModal(): void {
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

  openFilters(): void {
    this.state.setModal('filters');
  }

  openNotifications(): void {
    this.state.setModal('notifications');
  }

  openTutorial(): void {
    this.state.setModal('onboarding');
  }
}
