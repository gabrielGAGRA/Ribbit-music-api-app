---
trigger: model_decision
description: Use when writing or editing view tests and running verification gates - test execution, typecheck, linting, and formatting.
globs: view/**/*.{ts,html,spec.ts}
---

# View Verification & Tests

## 1. Quality Gates (Linting & Typecheck)

Execute after changes in `view/`:

```bash
# Typecheck com o compilador nativo do TypeScript 7
npm run typecheck

# Executar ambos (TypeScript com Oxlint + Angular com ESLint)
npm run lint

# Executar apenas o lint do Angular (@angular-eslint: componentes e templates)
npm run lint:angular

# Executar apenas o lint do TypeScript (Oxlint type-aware em Go)
npm run lint:ts

# Corrigir problemas automaticamente (ambos)
npm run lint:fix

# Corrigir problemas automaticamente apenas do Angular
npm run lint:angular:fix

# Checar formatação com Oxfmt
npm run format:check

# Auto-formatar arquivos com Oxfmt
npm run format
```

- **Oxlint** ([.oxlintrc.json](file:///c:/Users/gabri/Documents/PROJETOS/POLI/Lab_Engenharia_Software/.oxlintrc.json)): General TypeScript correctness, syntax, type safety, imports, and JSDoc via `oxlint-tsgolint`.
- **ESLint** ([eslint.config.mjs](file:///c:/Users/gabri/Documents/PROJETOS/POLI/Lab_Engenharia_Software/eslint.config.mjs)): Angular-specific rules (components, selectors, signals, standalone) and HTML templates (`@angular-eslint`). Redundant general rules are disabled via `eslint-plugin-oxlint`.
- **TypeScript 7** ([tsconfig.json](file:///c:/Users/gabri/Documents/PROJETOS/POLI/Lab_Engenharia_Software/tsconfig.json)): Strict type checking (`noEmit`).

---

## 2. Unit Tests

Unit tests are co-located with source files as `*.spec.ts`.

| Directory / File | Scope |
| --- | --- |
| `view/**/*.spec.ts` | Angular unit tests (components, services, pipes, directives) |

```bash
# Run unit tests (headless for CI / local verification)
npm test

# Run unit tests in watch mode
npm run test:watch
```

- Target coverage: 85% global threshold (`statements`, `branches`, `functions`, `lines`).
- Mocks/spies are restored automatically between tests (`autoRestoreSpies: true`).

Categories & conventions: [angular-style-guide.md](file:///c:/Users/gabri/Documents/PROJETOS/POLI/Lab_Engenharia_Software/docs/llm/view/angular-style-guide.md) and [typescript-engineering-rules.md](file:///c:/Users/gabri/Documents/PROJETOS/POLI/Lab_Engenharia_Software/docs/llm/view/typescript-engineering-rules.md).