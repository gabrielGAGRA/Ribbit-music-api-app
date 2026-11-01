import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay } from 'rxjs/operators';
import { SubscriptionPlan } from '@ribbit/shared-types';
import { MOCK_PLANS } from '../mocks/plans.mock';

@Injectable({ providedIn: 'root' })
export class PlanService {
  getPlans(annual: boolean = true): Observable<readonly SubscriptionPlan[]> {
    const plans: readonly SubscriptionPlan[] = [
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
    return of(plans).pipe(delay(100));
  }
}
