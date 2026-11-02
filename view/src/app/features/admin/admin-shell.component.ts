import type { OnDestroy } from '@angular/core';
import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import type { Subscription } from 'rxjs';
import { filter } from 'rxjs/operators';
import type { NavigationItem } from '@ribbit/shared-types';
import { safeInject } from '../../core/safe-inject';
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
      'Consulte assinantes por plano, promova novos administradores e gerencie credenciais privilegiadas.',
  },
  plans: {
    eyebrow: 'MONETIZAÇÃO & TIERS',
    titlePrefix: 'Configuração de ',
    titleHighlight: 'planos de assinatura.',
    description:
      'Ajuste nomenclatura, mensalidade e cotas máximas de perfis vinculados com validação de capacidade.',
  },
  moderation: {
    eyebrow: 'CURADORIA & CONFORMIDADE',
    titlePrefix: 'Moderação de catálogo e ',
    titleHighlight: 'avaliações.',
    description:
      'Pesquise faixas ativas, aplique bloqueios ou classificação +18 e remova avaliações abusivas.',
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
export class AdminShellComponent implements OnDestroy {
  protected readonly adminState = safeInject(AdminStateService, new AdminStateService());
  private readonly router = safeInject<Router | null>(Router, null);
  private readonly routeSubscription: Subscription | null;

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

  protected readonly adminInitials = computed<string>(() => {
    const name = this.adminState.currentAdmin()?.display_name ?? 'Admin';
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
      this.routeSubscription = this.router.events
        .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
        .subscribe((event) => {
          this.syncSectionFromUrl(event.urlAfterRedirects);
        });
    } else {
      this.routeSubscription = null;
    }
  }

  ngOnDestroy(): void {
    this.routeSubscription?.unsubscribe();
  }

  protected navigateSection(sectionId: string): void {
    this.activeSection.set(sectionId);
    if (this.router) {
      this.router.navigate(['/admin', sectionId]).catch(() => {});
    }
  }

  protected resetDemo(): void {
    this.adminState.resetDemoData();
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
