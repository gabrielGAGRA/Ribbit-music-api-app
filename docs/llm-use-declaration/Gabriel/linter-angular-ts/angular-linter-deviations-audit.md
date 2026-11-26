Dos desvios encontrados fora do linter com script, nao tem como adicionar no proprio linter como regra? Evitando false positive ou false negative
Vamos corrigir:

---

Desvios encontrados fora do linter:
Membros de template sem protected (Angular §4 / TS §5): 167 sinais/computeds/inputs/outputs em componentes declarados sem modificador de acesso (ficando public implicitamente).
Type assertions as sem comentário justificando segurança (TS §4): 68 ocorrências em produção, a maioria event.target as HTMLInputElement/HTMLSelectElement, além de casts de DTO em api-error.ts e auth-token.storage.ts.
Componentes pesados e serviços monolíticos (Angular §4): ribbit-state.service.ts tem 1561 linhas, admin-state.service.ts tem 1030 linhas e 12 componentes passam de 200 linhas, com destaque para auth.component.ts (714), modals.component.ts (637), family.component.ts (575) e playlists.component.ts (503).
Mais de um conceito por arquivo (Angular §1): dynamic-style.directive.ts agrupa 3 diretivas (WidthPercentDirective, TransformStyleDirective, WaveBarStyleDirective) e admin-state.service.ts exporta AdminDomainError junto ao service.
RxJS e ciclo de vida (Angular §2–§3): admin-shell.component.ts faz .subscribe() no construtor (embora dê unsubscribe, o guia recomenda toSignal()/takeUntilDestroyed()), e admin-moderation.component.ts usa Subject para debounce de busca.
Pontuais menores: 7 passagens de função nomeada para .filter() (notSame em ribbit-state.service.ts e Boolean em modals.component.ts), handler nomeado por evento DOM onSubmit em auth.component.ts, 11 componentes/serviços sem .spec.ts colocalizado e 1 console.error no bootstrap em main.ts (permitido temporariamente pela regra TS §7).

---------

Created audit_view.py

import collections
import glob
import os
import re

ts_files = sorted(glob.glob('view/src/**/*.ts', recursive=True))
non_spec_ts = [f for f in ts_files if not f.endswith('.spec.ts')]
spec_ts = [f for f in ts_files if f.endswith('.spec.ts')]
html_files = sorted(glob.glob('view/src/**/*.html', recursive=True))

# Check CRLF prevalence (explains oxfmt --check)
crlf_count = sum(
    1 for f in ts_files + html_files if b'\r\n' in open(f, 'rb').read()
)
print(
    f'Files: {len(ts_files)} TS ({len(non_spec_ts)} prod, {len(spec_ts)} spec), '
    f'{len(html_files)} HTML | CRLF files: {crlf_count}/{len(ts_files) + len(html_files)}'
)

checks = collections.defaultdict(list)

for f in non_spec_ts:
    norm = f.replace('\\', '/')
    txt = open(f, encoding='utf-8').read()
    lines = txt.splitlines()

    # 1. Multiple Angular/class declarations per file
    decs = re.findall(r'@(?:Component|Directive|Injectable|Pipe)\b', txt)
    classes = re.findall(r'export\s+class\s+(\w+)', txt)
    if len(decs) > 1 or len(classes) > 1:
        checks['multi-concept-file'].append(
            f'{norm}: {len(decs)} decorators, classes={classes}'
        )

    # 2. export default
    if re.search(r'\bexport\s+default\b', txt):
        checks['export-default'].append(norm)

    # 3. Generic filenames
    base = os.path.basename(norm)
    if base in {'helpers.ts', 'utils.ts', 'common.ts', 'index.ts'}:
        checks['generic-filename'].append(norm)

    # 4. Line-level checks
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if re.search(r'\b(BehaviorSubject|ReplaySubject|Subject)\b', l):
            checks['rxjs-subject'].append(f'{norm}:{i}: {s}')
        if re.search(r'\b(ChangeDetectorRef|markForCheck|detectChanges)\b', l):
            checks['manual-cdr'].append(f'{norm}:{i}: {s}')
        if re.search(r'\b(parseInt|parseFloat)\s*\(', l):
            checks['parseInt-parseFloat'].append(f'{norm}:{i}: {s}')
        if re.search(r'\bconsole\.(log|warn|error|info|debug)\b', l):
            checks['console-usage'].append(f'{norm}:{i}: {s}')
        if re.search(
            r'(eslint-disable|oxlint-disable|@ts-expect-error|@ts-ignore|@ts-nocheck)',
            l,
        ):
            checks['lint-suppressions'].append(f'{norm}:{i}: {s}')
        if re.search(
            r'\b(handleClick|onClick|onChange|onInput|onSubmit|onKeydown|onKeyDown|onKeyUp|handleInput|handleChange|handleSubmit)\s*\(',
            l,
        ):
            checks['dom-event-handler-name'].append(f'{norm}:{i}: {s}')
        if re.search(r'\.\w+\(\)\.(push|pop|splice|sort|reverse)\(', l):
            checks['signal-in-place-mutation'].append(f'{norm}:{i}: {s}')
        if re.search(r'\b(private|protected|public|readonly)\s+_\w+', l):
            checks['leading-underscore-member'].append(f'{norm}:{i}: {s}')
        if re.search(r'^\s*#\w+', l):
            checks['hash-private'].append(f'{norm}:{i}: {s}')
        if re.search(r'\btype\s+\w+\s*=\s*[^;]*\|\s*(null|undefined)\b', l):
            checks['nullable-type-alias'].append(f'{norm}:{i}: {s}')
        if (
            re.search(r'\b\w+\s*:\s*[^;?=\n]+\|\s*undefined\b', l)
            and not re.search(r'\?\s*:', l)
            and '=>' not in l
            and 'function ' not in l
            and '):' not in l
        ):
            checks['explicit-undefined-field'].append(f'{norm}:{i}: {s}')
        if re.search(r'\.\s*(map|filter|forEach)\s*\(\s*[a-zA-Z_$][\w$]*\s*\)', l):
            checks['named-fn-callback'].append(f'{norm}:{i}: {s}')
        if (
            re.search(r'\bas\s+[A-Z][\w<>\[\]\s|&]*', l)
            and 'import ' not in l
            and 'export ' not in l
        ):
            prev = lines[i - 2] if i >= 2 else ''
            if '//' not in l and '/*' not in l and '//' not in prev and '*/' not in prev:
                checks['uncommented-as-assertion'].append(f'{norm}:{i}: {s}')
        if re.search(r'@(?:param|returns|return)\s*\{[^}]+\}', l):
            checks['jsdoc-types'].append(f'{norm}:{i}: {s}')
        if re.search(r'\btypeof\s+\w+\s*===\s*[\'"]string[\'"]', l):
            checks['typeof-string-check'].append(f'{norm}:{i}: {s}')
        if re.search(r'\{\s*\[[\w\s]+:\s*string\]\s*:', l):
            checks['index-signature-dict'].append(f'{norm}:{i}: {s}')
        if re.search(r'\bsubscribe\s*\(', l):
            checks['raw-subscribe'].append(f'{norm}:{i}: {s}')
        if re.search(r'catch\s*(\([^)]*\))?\s*\{\s*\}', l):
            checks['empty-catch'].append(f'{norm}:{i}: {s}')
        if re.search(r'\bany\b', l) and not s.startswith('//') and not s.startswith('*'):
            if re.search(r':\s*any\b|\bas\s+any\b|<any>', l):
                checks['explicit-any'].append(f'{norm}:{i}: {s}')

    # 5. Component size & member modifiers
    if norm.endswith('.component.ts'):
        if len(lines) > 200:
            checks['large-component-ts'].append(f'{norm}: {len(lines)} lines')
        for i, l in enumerate(lines, 1):
            s = l.strip()
            if re.match(
                r'^\s+(?:readonly\s+)?\w+\s*=\s*(?:signal|computed|input|output|model)\b',
                l,
            ) and not re.match(r'^\s+(?:private|protected|public)\s+', l):
                checks['implicit-public-signal-on-component'].append(
                    f'{norm}:{i}: {s}'
                )
            if re.match(
                r'^\s+(?:(?:private|protected|public)\s+)?(?!readonly\b)\w+\s*=\s*(?:signal|computed|input|output|model|inject)\b',
                l,
            ):
                checks['non-readonly-angular-field'].append(f'{norm}:{i}: {s}')

    # 6. @Injectable without providedIn: root
    if '@Injectable(' in txt and "providedIn: 'root'" not in txt and 'providedIn: "root"' not in txt:
        checks['injectable-not-root'].append(norm)

    # 7. Missing colocated spec for components/services
    if norm.endswith(('.component.ts', '.service.ts')):
        expected_spec = norm[:-3] + '.spec.ts'
        if not os.path.exists(expected_spec):
            checks['missing-spec'].append(norm)

for f in html_files:
    norm = f.replace('\\', '/')
    lines = open(f, encoding='utf-8').read().splitlines()
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if re.search(r'\.(filter|map|reduce|sort|find)\s*\(', l):
            checks['complex-template-array-op'].append(f'{norm}:{i}: {s[:100]}')
        if l.count('?') >= 2 and ':' in l and '{{' in l:
            checks['nested-ternary-in-template'].append(f'{norm}:{i}: {s[:100]}')
        if re.search(
            r'\(\w+\)="(handleClick|onClick|onChange|onInput|onSubmit|onKeydown|onKeyDown)\(',
            l,
        ):
            checks['dom-event-handler-in-html'].append(f'{norm}:{i}: {s[:100]}')

# Also check oxlint/eslint suppressions in spec files
spec_suppressions = 0
for f in spec_ts:
    txt = open(f, encoding='utf-8').read()
    spec_suppressions += len(re.findall(r'(eslint-disable|oxlint-disable|@ts-expect-error)', txt))
print(f'Suppressions in spec files: {spec_suppressions}')

for k in sorted(checks):
    items = checks[k]
    print(f'\n[{k}] ({len(items)})')
    for it in items[:10]:
        print('  ', it)
    if len(items) > 10:
        print(f'   ... +{len(items) - 10} more')


Ran run view style-guide audit script
python C:\Users\gabri\.gemini\antigravity\brain\06afa113-3ee5-43e1-8edc-2a524e6c8adf\scratch\audit_view.py
Files: 75 TS (51 prod, 24 spec), 24 HTML | CRLF files: 95/99
Suppressions in spec files: 0

[console-usage] (1)
   view/src/main.ts:16: console.error(err);

[dom-event-handler-in-html] (2)
   view/src/app/features/auth/auth.component.html:75: <form (submit)="onSubmit($event)">
   view/src/app/features/auth/auth.component.html:107: <form (submit)="onSubmit($event)">

[dom-event-handler-name] (1)
   view/src/app/features/auth/auth.component.ts:613: onSubmit(event: Event): void {

[explicit-undefined-field] (4)
   view/src/app/core/ribbit-state.service.ts:1402: playlistId: number | undefined,
   view/src/app/core/services/song.service.ts:46: const optionalPairs: readonly [string, string | undefined][] = [
   view/src/app/features/admin/admin-state.service.ts:249: track: TrackApiDto | undefined,
   view/src/app/features/family/family.component.ts:334: birth_date: birthDate || undefined,

[generic-filename] (1)
   view/src/types/index.ts

[implicit-public-signal-on-component] (167)
   view/src/app/app.component.ts:119: readonly isAdminRoute = signal<boolean>(
   view/src/app/app.component.ts:131: readonly userInitials = computed<string>(() => {
   view/src/app/app.component.ts:143: readonly isProfileArea = computed<boolean>(() =>
   view/src/app/app.component.ts:149: readonly breadcrumbLabel = computed<string>(() => {
   view/src/app/app.component.ts:157: readonly currentHeading = computed<PageHeading>(() => {
   view/src/app/app.component.ts:162: readonly likedCount = computed<number>(() => this.state.likedSongs().length);
   view/src/app/app.component.ts:163: readonly lovedCount = computed<number>(() => this.state.lovedSongs().length);
   view/src/app/app.component.ts:164: readonly rejectedCount = computed<number>(() => this.state.rejectedSongs().length);
   view/src/app/app.component.ts:166: readonly dailyDiscoveries = computed<number>(() =>
   view/src/app/app.component.ts:170: readonly dailyProgressPercent = computed<number>(() =>
   ... +157 more

[large-component-ts] (12)
   view/src/app/app.component.ts: 255 lines
   view/src/app/features/admin/admin-moderation.component.ts: 365 lines
   view/src/app/features/admin/admin-users.component.ts: 240 lines
   view/src/app/features/auth/auth.component.ts: 714 lines
   view/src/app/features/discover/discover.component.ts: 228 lines
   view/src/app/features/explore/explore.component.ts: 334 lines
   view/src/app/features/family/family.component.ts: 575 lines
   view/src/app/features/jams/jams.component.ts: 212 lines
   view/src/app/features/playlists/playlists.component.ts: 503 lines
   view/src/app/features/profile/profile.component.ts: 220 lines
   ... +2 more

[missing-spec] (11)
   view/src/app/core/services/dashboard.service.ts
   view/src/app/core/services/plan.service.ts
   view/src/app/core/services/playlist.service.ts
   view/src/app/features/admin/admin-login.component.ts
   view/src/app/features/auth/auth-api.service.ts
   view/src/app/features/jams/jam.service.ts
   view/src/app/features/not-found/not-found.component.ts
   view/src/app/features/profile/collection.component.ts
   view/src/app/shared/frog.component.ts
   view/src/app/shared/icon.component.ts
   ... +1 more

[multi-concept-file] (2)
   view/src/app/features/admin/admin-state.service.ts: 1 decorators, classes=['AdminDomainError', 'AdminStateService']
   view/src/app/shared/dynamic-style.directive.ts: 3 decorators, classes=['WidthPercentDirective', 'TransformStyleDirective', 'WaveBarStyleDirective']

[named-fn-callback] (7)
   view/src/app/core/ribbit-state.service.ts:1358: this.likedSongs.update((list) => list.filter(notSame));
   view/src/app/core/ribbit-state.service.ts:1359: this.lovedSongs.update((list) => list.filter(notSame));
   view/src/app/core/ribbit-state.service.ts:1360: this.rejectedSongs.update((list) => list.filter(notSame));
   view/src/app/core/ribbit-state.service.ts:1368: kind === 'reject' ? list.filter(notSame) : [song, ...list.filter(notSame)],
   view/src/app/core/ribbit-state.service.ts:1371: kind === 'love' ? [song, ...list.filter(notSame)] : list.filter(notSame),
   view/src/app/core/ribbit-state.service.ts:1374: kind === 'reject' ? [song, ...list.filter(notSame)] : list.filter(notSame),
   view/src/app/shared/modals.component.ts:480: .filter(Boolean)

[nested-ternary-in-template] (1)
   view/src/app/features/auth/auth.component.html:269: {{ isRegister() ? 'Já faz parte do lago?' : 'Novo por aqui?' }}

[raw-subscribe] (92)
   view/src/app/app.component.ts:194: .subscribe((event) => {
   view/src/app/core/ribbit-state.service.ts:346: .subscribe();
   view/src/app/core/ribbit-state.service.ts:348: this.profileApi.getProfile().subscribe({
   view/src/app/core/ribbit-state.service.ts:373: .subscribe((res) => {
   view/src/app/core/ribbit-state.service.ts:407: this.songService.recordTrackAccess(trackId, source).subscribe({
   view/src/app/core/ribbit-state.service.ts:428: }).subscribe(({ blocked, favorites, theme }) => {
   view/src/app/core/ribbit-state.service.ts:448: this.songService.getNextDiscoverySong().subscribe({
   view/src/app/core/ribbit-state.service.ts:468: this.playlistService.getPlaylists().subscribe({
   view/src/app/core/ribbit-state.service.ts:486: }).subscribe(({ recent, allHistory }) => {
   view/src/app/core/ribbit-state.service.ts:494: this.songService.getSongs().subscribe({
   ... +82 more

[rxjs-subject] (3)
   view/src/app/features/admin/admin-moderation.component.ts:11: import { Subject, merge, of } from 'rxjs';
   view/src/app/features/admin/admin-moderation.component.ts:54: private readonly immediateSearch$ = new Subject<string>();
   view/src/app/features/admin/admin-moderation.component.ts:55: private readonly debouncedSearch$ = new Subject<string>();

[typeof-string-check] (4)
   view/src/app/core/api-error.ts:21: if (typeof detail === 'string' && detail.trim().length > 0) {
   view/src/app/core/ribbit-state.service.ts:58: ? parsed.filter((item): item is string => typeof item === 'string')
   view/src/app/core/ribbit-state.service.ts:933: typeof nameOrPlaylist === 'string'
   view/src/app/features/playlists/playlists.component.ts:375: typeof playlistOrName === 'string'

[uncommented-as-assertion] (68)
   view/src/app/core/api-error.ts:38: const typed = payload as FastApiErrorPayload;
   view/src/app/core/auth-token.storage.ts:65: return parsed as UserApiDto;
   view/src/app/features/admin/admin-dashboard.component.ts:109: this.costPerTrackInput.set((event.target as HTMLInputElement).value);
   view/src/app/features/admin/admin-dashboard.component.ts:113: this.infraFixedInput.set((event.target as HTMLInputElement).value);
   view/src/app/features/admin/admin-dashboard.component.ts:117: this.infraPerUserInput.set((event.target as HTMLInputElement).value);
   view/src/app/features/admin/admin-login.component.ts:40: const target = event.target as HTMLInputElement;
   view/src/app/features/admin/admin-login.component.ts:45: const target = event.target as HTMLInputElement;
   view/src/app/features/admin/admin-moderation.component.ts:91: const target = event.target as HTMLInputElement;
   view/src/app/features/admin/admin-moderation.component.ts:203: const target = event.target as HTMLInputElement;
   view/src/app/features/admin/admin-moderation.component.ts:226: const sortBy = (event.target as HTMLSelectElement).value as AdminTrackSortOption;
   ... +58 more