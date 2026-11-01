import { CommunityReview } from '@ribbit/shared-types';

export const MOCK_REVIEWS: readonly CommunityReview[] = [
  {
    id: 1,
    author: 'Ana Clara',
    initials: 'AC',
    text: 'A produção cresce sem pressa e transforma o refrão em um lugar para voltar.',
    likes: 42,
    age: 'há 12 min',
    date: 6,
  },
  {
    id: 2,
    author: 'Mateus Reis',
    initials: 'MR',
    text: 'Perfeita para ouvir no fim da tarde. Entrou direto na minha playlist.',
    likes: 28,
    age: 'há 1 h',
    date: 5,
  },
  {
    id: 3,
    author: 'Bia Santos',
    initials: 'BS',
    text: 'Os detalhes da instrumentação ficam melhores a cada nova escuta.',
    likes: 17,
    age: 'ontem',
    date: 4,
  },
  {
    id: 4,
    author: 'Caio Lima',
    initials: 'CL',
    text: 'Uma descoberta delicada, mas com personalidade suficiente para surpreender.',
    likes: 9,
    age: 'há 2 dias',
    date: 3,
  },
];
