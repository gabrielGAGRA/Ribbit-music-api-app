import { MetricItem, RankedGenre } from '@ribbit/shared-types';

export const MOCK_METRICS: readonly MetricItem[] = [
  { value: '256', label: 'Descobertas', detail: '+18 esta semana', icon: 'sparkles' },
  { value: '18', label: 'Novos artistas', detail: '+6 este mês', icon: 'user' },
  { value: '12', label: 'Gêneros explorados', detail: '3 fora da bolha', icon: 'globe' },
  { value: '86%', label: 'Taxa de match', detail: 'Sua frequência', icon: 'heart' },
];

export const MOCK_FAVORITE_GENRES: readonly RankedGenre[] = [
  { genre: 'Indie', percentage: 82, rank: '1' },
  { genre: 'R&B / Soul', percentage: 64, rank: '2' },
  { genre: 'Eletrônica', percentage: 46, rank: '3' },
  { genre: 'Dream Pop', percentage: 30, rank: '4' },
];
