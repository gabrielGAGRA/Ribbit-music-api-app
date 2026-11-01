import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
} from '@angular/core';
import { RibbitStateService } from '../../core/ribbit-state.service';
import { PlanService } from '../../core/services/plan.service';
import { safeInject } from '../../core/safe-inject';
import { IconComponent } from '../../shared/icon.component';
import { IconName, SubscriptionPlan } from '@ribbit/shared-types';

@Component({
  selector: 'app-plans',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './plans.component.html',
  styleUrl: './plans.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlansComponent {
  protected readonly planService: PlanService = safeInject(PlanService, new PlanService());

  readonly annualPlans = signal<boolean>(true);
  readonly activeSlide = signal<number>(0);

  readonly computedPlans = computed<readonly SubscriptionPlan[]>(() => {
    const annual = this.annualPlans();
    return [
      {
        name: 'Free',
        displayName: 'Ribbit Free',
        price: 'R$ 0',
        copy: 'Para descobrir no seu ritmo.',
        features: [
          'Swipes ilimitados',
          'Playlists manuais',
          'Prévia de 30 segundos',
        ],
      },
      {
        name: 'Individual',
        displayName: 'Ribbit Pro',
        price: annual ? 'R$ 14,90' : 'R$ 18,90',
        copy: 'Sua experiência completa.',
        featured: true,
        features: [
          'Tudo do plano Free',
          'Sem anúncios',
          'Áudio completo e offline',
          'Playlists inteligentes',
        ],
      },
      {
        name: 'Família',
        displayName: 'Ribbit Jam',
        price: annual ? 'R$ 27,90' : 'R$ 34,90',
        copy: 'Até seis perfis, cada um no seu ritmo.',
        features: [
          'Até 6 contas',
          'Jams privadas ilimitadas',
          'Controle familiar',
          'Recomendações separadas',
        ],
      },
    ];
  });

  constructor(
    protected readonly state: RibbitStateService = inject(RibbitStateService),
  ) {}

  setAnnual(annual: boolean): void {
    this.annualPlans.set(annual);
  }

  setSlide(slide: number): void {
    this.activeSlide.set(slide);
  }

  getPlanIcon(name: string): IconName {
    if (name === 'Free') return 'pond';
    if (name === 'Individual') return 'star';
    return 'users';
  }

  selectPlan(name: string): void {
    this.state.setPlan(name);
    this.state.notify(
      name === 'Free'
        ? 'Plano Free selecionado.'
        : `Ribbit ${name} ativado em modo demonstrativo.`,
    );
  }
}
