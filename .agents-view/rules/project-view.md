---
trigger: model_decision
description: Use when editing Angular view code (view/**/*.ts, *.html) - TypeScript rules, lint/format/typecheck gate.
globs: view/**/*.{ts,html}
---

# View (Angular + TypeScript) Map

- Angular app lives in `view/`; the Python backend is `app/`.
- Tooling: `.oxlintrc.json` (oxlint type-aware, import, jsdoc), `eslint.config.mjs` (angular template linting), `tsconfig.json` (strict TypeScript 7), `.oxfmtrc.json` (oxfmt).
- Gate after every change: `npm run format`, `npm run lint:fix`, `npm run typecheck`.
- Only the judgement rules are written down; do not restate lint rules.

Deeper detail: `docs/llm/view/typescript-engineering-rules.md`, Angular conventions: `docs/llm/view/angular-style-guide.md`.