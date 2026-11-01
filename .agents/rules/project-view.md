---
trigger: model_decision
description: Use when editing Angular view code (app/web/src/**/*.{ts,html,css}, src/**/*.{ts,html}) - TypeScript rules, lint/format/typecheck gate.
globs: app/web/src/**/*.{ts,html,css}
---

# View (Angular + TypeScript) Map

- Angular app (`@ribbit/web`) lives in `app/web/src/`; root `src/` holds root type resets. No hexagonal layering on the view.
- Tooling: `.oxlintrc.json` (oxlint type-aware, import, jsdoc), `eslint.config.mjs` (angular template linting), `tsconfig.json` / `app/web/tsconfig.json`, `.oxfmtrc.json` (oxfmt), Vitest (`app/web/vitest.config.ts`).
- Gate after every change: `npm run test:web`, `npm run typecheck:web`, `npm run build:web`, plus root `npm run format`, `npm run lint:fix`, `npm run typecheck`.
- Only the judgement rules are written down; do not restate lint rules.

Deeper detail: `docs/llm/view/typescript-engineering-rules.md`, Angular conventions: `docs/llm/view/angular-style-guide.md`.
