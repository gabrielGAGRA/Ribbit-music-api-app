# Frontend (`view/`)

Angular 22 + TypeScript (strict TS 7 typecheck) SPA using standalone components, Signals, Zoneless `OnPush`, and modern control flow (`@if`, `@for`, `@switch`).

## Layout

- `view/src/app/features/`: feature areas for listener screens and `admin/*` console; co-locate component `.ts`, `.html`, `.css`, and `.spec.ts`.
- `view/src/app/core/`: global state services, API/auth interceptors, guards, audio player.
- `view/src/app/shared/`: reusable UI components.
- `view/src/types/`: shared TypeScript interfaces (`@ribbit/shared-types`).

## Quality Gate & Tests

Run from repository root after edits in `view/`:

```bash
npm run format
npm run lint:fix
npm run typecheck
npm test
```

Tooling: Oxfmt (`.oxfmtrc.json`), type-aware Oxlint (`.oxlintrc.json`), Angular ESLint (`eslint.config.mjs`), TypeScript 7 (`tsconfig.json`), and Vitest (`vitest.config.ts`). Do not restate mechanical lint rules in prose.

Judgment rules & conventions: `docs/llm/view/angular-style-guide.md` and `docs/llm/view/typescript-engineering-rules.md`.
For UI design, UX critique, auditing, or visual polish, use `@frontend-design` and `@impeccable`.
