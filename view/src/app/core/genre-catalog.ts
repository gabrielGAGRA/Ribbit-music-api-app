/** DB-backed genre catalog dictionary, formatting, and alias matching helpers. */

export const GENRE_CATALOG_DICT: Readonly<Record<string, readonly string[]>> = {
  Rock: [
    'rock',
    'hard rock',
    'rock-n-roll',
    'rockabilly',
    'psych-rock',
    'prog-rock/art rock',
    'rock y alternativo',
    'jam bands',
    'indie rock',
    'garage',
    'new wave',
    'classic rock',
    'soft rock',
    'pop rock',
    'punk rock',
    'psychedelic rock',
    'progressive rock',
    'garage rock',
    'roc',
  ],
  Pop: [
    'pop',
    'power-pop',
    'synth-pop',
    'french pop',
    'arabic pop',
    'indian pop',
    'bollywood',
    'indie pop',
    'afro-pop',
    'christmas: pop',
    'dance pop',
    'electropop',
    'dream pop',
    'art pop',
    'chamber pop',
    'synthpop',
  ],
  'Hip Hop': [
    'hip-hop',
    'hip hop',
    'hiphop',
    'rap',
    'alternative rap',
    'hardcore rap',
    'west coast rap',
    'hip-hop in russian',
    'trap',
    'boom bap',
    'gangsta rap',
  ],
  Funk: ['funk', 'baile funk', 'funk carioca', 'funk brasileiro', 'p-funk', 'g-funk'],
  Alternative: [
    'alternative',
    'alternativo',
    'adult alternative',
    'alternative rock',
    'emo',
    'rock y alternativo',
  ],
  'R&B': ['r&b', 'r b', 'rnb', 'contemporary r&b', 'christmas: r&b', 'soul', 'neo-soul', 'motown'],
  Sertanejo: ['sertanejo', 'sertanejo universitario'],
  Dance: [
    'dance',
    'disco',
    'club',
    'house',
    'deep-house',
    'chicago-house',
    'progressive-house',
    'afro house',
    'groove',
    'amapiano',
  ],
  MPB: ['mpb', 'brazilian', 'musica popular brasileira'],
  Country: [
    'country',
    'honky-tonk',
    'bluegrass',
    'traditional country',
    'americana',
    'christmas: country',
  ],
  Latin: [
    'latin',
    'latina',
    'música tropical',
    'musica tropical',
    'música mexicana',
    'musica mexicana',
    'reggaeton',
    'salsa',
    'bachata',
  ],
  Pagode: ['pagode'],
  Soundtrack: [
    'soundtrack',
    'tv soundtrack',
    'disney',
    'anime',
    'show-tunes',
    'musicals',
    'trilha sonora',
    'ost',
    'score',
  ],
  Electronic: [
    'electronic',
    'eletrônica',
    'eletronica',
    'electronica',
    'detroit-techno',
    'techno',
    'electro',
    'edm',
    'idm',
    'idm/experimental',
    'ambient',
    'industrial',
    'breakbeat',
    'dubstep',
    'trip-hop',
    'downtempo',
    'drum-and-bass',
    "jungle/drum'n'bass",
    'dnb',
    'trance',
    'chill',
    'new-age',
    'new age',
    'synthwave',
    'house',
    'deep-house',
    'chicago-house',
    'progressive-house',
    'afro house',
    'lo-fi',
    'lofi',
  ],
  Indie: ['indie', 'indie pop', 'indie rock', 'indie folk'],
  Folk: ['folk', 'acoustic', 'singer/songwriter', 'afro-folk', 'indie folk'],
  Reggae: ['reggae', 'dub', 'dancehall', 'modern dancehall', 'ska'],
  Metal: [
    'metal',
    'grindcore',
    'heavy metal',
    'black metal',
    'death metal',
    'thrash metal',
    'power metal',
    'doom metal',
    'metalcore',
    'nu metal',
    'progressive metal',
  ],
  'K-Pop': ['k-pop', 'k pop', 'j-pop', 'j pop'],
  Forró: ['forro', 'forró', 'piseiro', 'xote'],
  Samba: ['samba'],
  Punk: ['punk', 'punk rock', 'pop punk', 'post-punk', 'hardcore', 'hardcore punk', 'emo'],
  Jazz: ['jazz', 'contemporary jazz', 'smooth jazz', 'bebop', 'swing', 'lounge'],
  Axé: ['axe', 'axé'],
  'Bossa Nova': ['bossa nova'],
  Soul: ['soul', 'neo-soul', 'motown'],
  Blues: ['blues', 'delta blues', 'electric blues', 'blues rock'],
  Gospel: ['gospel', 'praise & worship'],
  Grunge: ['grunge', 'post-grunge'],
  Classical: [
    'classical',
    'clássica',
    'classica',
    'erudita',
    'classical crossover',
    'opera',
    'piano',
    'instrumental',
    'orchestral',
    'symphony',
    'baroque',
  ],
};

export const CATALOG_GENRES: readonly string[] = Object.keys(GENRE_CATALOG_DICT).sort((a, b) =>
  a.localeCompare(b, 'pt-BR', { sensitivity: 'base' }),
);

const PRIMARY_DISPLAY_LABELS: Readonly<Record<string, string>> = {
  rock: 'Rock',
  pop: 'Pop',
  'hip-hop': 'Hip Hop',
  'hip hop': 'Hip Hop',
  funk: 'Funk',
  alternative: 'Alternative',
  'r&b': 'R&B',
  rnb: 'R&B',
  sertanejo: 'Sertanejo',
  dance: 'Dance',
  mpb: 'MPB',
  country: 'Country',
  latin: 'Latin',
  pagode: 'Pagode',
  soundtrack: 'Soundtrack',
  electronic: 'Electronic',
  indie: 'Indie',
  folk: 'Folk',
  reggae: 'Reggae',
  metal: 'Metal',
  'k-pop': 'K-Pop',
  'j-pop': 'J-Pop',
  forro: 'Forró',
  forró: 'Forró',
  samba: 'Samba',
  punk: 'Punk',
  jazz: 'Jazz',
  axe: 'Axé',
  axé: 'Axé',
  'bossa nova': 'Bossa Nova',
  soul: 'Soul',
  blues: 'Blues',
  gospel: 'Gospel',
  grunge: 'Grunge',
  classical: 'Classical',
  idm: 'IDM',
  edm: 'EDM',
  'contemporary r&b': 'Contemporary R&B',
  'tv soundtrack': 'TV Soundtrack',
};

const PORTUGUESE_AND_SHORTHAND_MAP: Readonly<Record<string, string>> = {
  eletronica: 'electronic',
  alternativo: 'alternative',
  classica: 'classical',
  erudita: 'classical',
  latina: 'latin',
  hiphop: 'hip hop',
  rnb: 'r b',
  lofi: 'electronic',
  'trilha sonora': 'soundtrack',
  rap: 'hip hop',
  brazilian: 'mpb',
  'detroit techno': 'electronic',
};

/** Folds accents and punctuation into lowercase space-separated tokens. */
export function normalizeGenreText(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function buildNormalizedAliasMap(): ReadonlyMap<string, readonly string[]> {
  const map = new Map<string, readonly string[]>();
  for (const [canonical, aliases] of Object.entries(GENRE_CATALOG_DICT)) {
    const foldedCanonical = normalizeGenreText(canonical);
    const unique = Array.from(
      new Set(aliases.map((alias) => normalizeGenreText(alias)).filter((item) => item.length > 0)),
    );
    map.set(foldedCanonical, unique);
  }
  for (const [aliasKey, targetKey] of Object.entries(PORTUGUESE_AND_SHORTHAND_MAP)) {
    const targetAliases = map.get(targetKey);
    if (targetAliases) {
      map.set(aliasKey, targetAliases);
    }
  }
  return map;
}

const NORMALIZED_ALIAS_MAP = buildNormalizedAliasMap();

function titleCaseLowerGenre(value: string): string {
  return value.replace(/(^|[\s/-])([a-z\u00e0-\u00ff])/g, (_match, sep: string, ch: string) => {
    return `${sep}${ch.toUpperCase()}`;
  });
}

/** Converts a raw DB genre string into a clean UI display label. */
export function formatGenreLabel(rawGenre: string | null | undefined): string {
  const trimmed = (rawGenre ?? '').trim();
  if (!trimmed) {
    return 'Desconhecido';
  }
  const lower = trimmed.toLowerCase();
  const mapped = PRIMARY_DISPLAY_LABELS[lower];
  if (mapped) {
    return mapped;
  }
  if (trimmed === lower) {
    return titleCaseLowerGenre(trimmed);
  }
  return trimmed;
}

function hasTokenSubsequence(haystack: readonly string[], needle: readonly string[]): boolean {
  if (needle.length === 0 || needle.length > haystack.length) {
    return false;
  }
  for (let i = 0; i <= haystack.length - needle.length; i++) {
    const sliceMatch = needle.every((token, offset) => haystack[i + offset] === token);
    if (sliceMatch) {
      return true;
    }
  }
  return false;
}

/** Checks whether a track's genre matches a selected filter or blocked genre using DB aliases. */
export function matchesGenreFilter(trackGenre: string, selectedFilter: string): boolean {
  const normTrack = normalizeGenreText(trackGenre);
  const normFilter = normalizeGenreText(selectedFilter);
  if (!normTrack || !normFilter) {
    return false;
  }
  const aliases = NORMALIZED_ALIAS_MAP.get(normFilter) ?? [normFilter];
  const trackTokens = normTrack.split(' ');
  return aliases.some(
    (alias) => normTrack === alias || hasTokenSubsequence(trackTokens, alias.split(' ')),
  );
}
