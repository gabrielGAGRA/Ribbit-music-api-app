import { describe, expect, it } from 'vitest';
import {
  CATALOG_GENRES,
  GENRE_CATALOG_DICT,
  formatGenreLabel,
  matchesGenreFilter,
} from './genre-catalog';

describe('genre-catalog', () => {
  it('exposes DB-backed canonical genres without stale fake pills', () => {
    expect(CATALOG_GENRES.length).toBe(30);
    expect(CATALOG_GENRES).toContain('Rock');
    expect(CATALOG_GENRES).toContain('Hip Hop');
    expect(CATALOG_GENRES).toContain('R&B');
    expect(CATALOG_GENRES).toContain('Sertanejo');
    expect(CATALOG_GENRES).toContain('Forró');
    expect(CATALOG_GENRES).toContain('Axé');
    expect(GENRE_CATALOG_DICT['Hip Hop']).toContain('hip-hop');
    expect(GENRE_CATALOG_DICT['Forró']).toContain('forro');
    const sorted = [...CATALOG_GENRES].sort((a, b) =>
      a.localeCompare(b, 'pt-BR', { sensitivity: 'base' }),
    );
    expect(CATALOG_GENRES).toEqual(sorted);
  });

  it('formats raw DB genre strings cleanly with Desconhecido fallback', () => {
    expect(formatGenreLabel('')).toBe('Desconhecido');
    expect(formatGenreLabel(null)).toBe('Desconhecido');
    expect(formatGenreLabel('hip-hop')).toBe('Hip Hop');
    expect(formatGenreLabel('r&b')).toBe('R&B');
    expect(formatGenreLabel('forro')).toBe('Forró');
    expect(formatGenreLabel('axe')).toBe('Axé');
    expect(formatGenreLabel('mpb')).toBe('MPB');
    expect(formatGenreLabel('k-pop')).toBe('K-Pop');
    expect(formatGenreLabel('bossa nova')).toBe('Bossa Nova');
    expect(formatGenreLabel('detroit-techno')).toBe('Detroit-Techno');
    expect(formatGenreLabel('Rock Clássico')).toBe('Rock Clássico');
  });

  it('matches aliases, punctuation variants, accents, and rejects non-matches', () => {
    expect(matchesGenreFilter('hip-hop', 'Hip Hop')).toBe(true);
    expect(matchesGenreFilter('r&b', 'R&B')).toBe(true);
    expect(matchesGenreFilter('forro', 'Forró')).toBe(true);
    expect(matchesGenreFilter('axe', 'Axé')).toBe(true);
    expect(matchesGenreFilter('detroit-techno', 'Electronic')).toBe(true);
    expect(matchesGenreFilter('música tropical', 'Latin')).toBe(true);
    expect(matchesGenreFilter('sertanejo', 'Rock')).toBe(false);
    expect(matchesGenreFilter('Desconhecido', 'Pop')).toBe(false);
  });
});
