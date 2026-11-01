import { SubscriptionPlan } from '@ribbit/shared-types';

export const MOCK_PLANS: readonly SubscriptionPlan[] = [
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
    price: 'R$ 18,90',
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
    price: 'R$ 34,90',
    copy: 'Até seis perfis, cada um no seu ritmo.',
    features: [
      'Até 6 contas',
      'Jams privadas ilimitadas',
      'Controle familiar',
      'Recomendações separadas',
    ],
  },
];
