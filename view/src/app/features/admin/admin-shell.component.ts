import type { OnInit } from '@angular/core';
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
import type { NavigationItem } from '@ribbit/shared-types';
import { FrogComponent } from '../../shared/frog.component';
import { IconComponent } from '../../shared/icon.component';
import { AdminStateService } from './admin-state.service';

interface AdminSectionMeta {
  readonly eyebrow: string;
  readonly titlePrefix: string;
  readonly titleHighlight: string;
  readonly description: string;
}

const ADMIN_SECTIONS: Readonly<Record<string, AdminSectionMeta>> = {
  dashboard: {
    eyebrow: 'PAINEL EXECUTIVO & AUDIÊNCIA',
    titlePrefix: 'Pulso financeiro e ',
    titleHighlight: 'audiência da plataforma.',
    description:
      'Indicadores consolidados de assinaturas, receita líquida estimada e preferências de bloqueio.',
  },
  users: {
    eyebrow: 'CONTAS & GOVERNANÇA',
    titlePrefix: 'Usuários registrados e ',
    titleHighlight: 'administradores.',
    description:
      'Consulte assinantes por plano, cadastre novos administradores e gerencie permissões privilegiadas.',
  },
  plans: {
    eyebrow: 'MONETIZAÇÃO & TIERS',
    titlePrefix: 'Configuração de ',
    titleHighlight: 'planos de assinatura.',
    description:
      'Ajuste nomenclatura, mensalidade e cotas máximas de perfis vinculados com validação no servidor.',
  },
  moderation: {
    eyebrow: 'CURADORIA & CONFORMIDADE',
    titlePrefix: 'Moderação de catálogo e ',
    titleHighlight: 'avaliações.',
    description:
      'Pesquise faixas ativas, aplique bloqueios, edite gêneros ou classificação +18 e gerencie o catálogo.',
  },
};

/** Dedicated full-width layout shell for /admin/* routes without listener audio player or right-rail. */
@Component({
  selector: 'app-admin-shell',
  standalone: true,
  imports: [RouterOutlet, FrogComponent, IconComponent],
  templateUrl: './admin-shell.component.html',
  styleUrl: './admin-shell.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminShellComponent implements OnInit {
  protected readonly adminState = inject(AdminStateService);
  private readonly router = inject(Router, { optional: true });
  private readonly navigationEnd = toSignal(
    this.router
      ? this.router.events.pipe(
          filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        )
      : EMPTY,
    { initialValue: null },
  );

  protected readonly navItems: readonly NavigationItem[] = [
    { id: 'dashboard', label: 'Visão Executiva', sub: 'Receita & Audiência', icon: 'chart' },
    { id: 'users', label: 'Usuários & Admins', sub: 'Contas e papéis', icon: 'users' },
    { id: 'plans', label: 'Planos & Preços', sub: 'Tiers de assinatura', icon: 'sparkles' },
    { id: 'moderation', label: 'Moderação', sub: 'Catálogo & Reviews', icon: 'shield' },
  ];

  protected readonly activeSection = signal<string>('dashboard');

  protected readonly sectionMeta = computed<AdminSectionMeta>(() => {
    return (
      ADMIN_SECTIONS[this.activeSection()] ??
      ADMIN_SECTIONS['dashboard'] ?? {
        eyebrow: 'VISÃO GERAL',
        titlePrefix: 'Dashboard ',
        titleHighlight: 'executivo.',
        description: 'Métricas da plataforma.',
      }
    );
  });

  protected readonly currentNavLabel = computed<string>(() => {
    const found = this.navItems.find((item) => item.id === this.activeSection());
    return found ? found.label : 'Visão Executiva';
  });

  protected readonly hasSyncError = computed<boolean>(() => Boolean(this.adminState.syncError()));

  protected readonly adminInitials = computed<string>(() => {
    const name = this.adminState.currentAdmin()?.displayName ?? 'Admin';
    const parts = name
      .trim()
      .split(/\s+/)
      .filter((part) => part.length > 0);
    const first = parts[0];
    const second = parts[1];
    if (first && second) {
      return `${first[0] ?? 'A'}${second[0] ?? 'D'}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase() || 'AD';
  });

  constructor() {
    if (this.router) {
      this.syncSectionFromUrl(this.router.url);
    }
    effect(() => {
      const event = this.navigationEnd();
      if (event) {
        this.syncSectionFromUrl(event.urlAfterRedirects);
      }
    });
  }

  ngOnInit(): void {
    if (
      this.adminState.isAuthenticated() &&
      !this.adminState.hasHydrated() &&
      !this.adminState.isLoading()
    ) {
      this.adminState.hydrateFromBackend();
    }
  }

  protected navigateSection(sectionId: string): void {
    this.activeSection.set(sectionId);
    if (this.router) {
      this.router.navigate(['/admin', sectionId]).catch(() => {});
    }
  }

  protected refreshBackend(): void {
    this.adminState.hydrateFromBackend();
  }

  protected openListenerApp(): void {
    if (this.router) {
      this.router.navigate(['/discover']).catch(() => {});
    }
  }

  protected signOutAdmin(): void {
    this.adminState.logoutAdmin();
    if (this.router) {
      this.router.navigate(['/admin/login']).catch(() => {});
    }
  }

  private syncSectionFromUrl(url: string): void {
    const segments = url.replace(/^\//, '').split('/');
    const candidate = segments[1]?.split('?')[0];
    if (candidate && candidate in ADMIN_SECTIONS) {
      this.activeSection.set(candidate);
    }
  }
}
