---
trigger: always_on
description: Use for rule priority, progressive disclosure navigation (when to read what), and the single registry of skill and plugin invocations.
---

# Meta Rules — Priority, Skills & Navigation

## 1. Rule Priority 

1. `.agents/AGENTS.md`
2. `.agents/rules/meta-rules.md`
3. Scoped subtree rules (`app/AGENTS.md`, `view/AGENTS.md`) — local architecture boundaries and verification gates.
4. `.agents/rules/tests-guide.md` — test pyramid, markers, and execution commands.
5. Deep passive guides (`docs/llm/app/*`, `docs/llm/view/*`) — coding judgment standards (read on demand before writing or reviewing code in that layer).

## 2. Skill & Workflow Invocation Registry

| Trigger / Intent | Action |
| --- | --- |
| Medium or ambiguous change (before coding) | `@interview-plan` |
| Big change, non-trivial feature or architectural change | EGM plugin (`/egm:egm-brainstorm` -> `/egm:egm-draft` -> `/egm:egm-review`) |
| Building, redesigning, auditing, or polishing frontend UI (`view/`) | `@frontend-design`, `@impeccable` |
| User asks for a PR or code review | `@code-review` |
| Risky diff before delivery | `@adversarial-review` (isolated subagent) |
| Commit, branch push, PR draft | `@commit` |

## 3. Navigation — When to Read What

| Question / Task | Where to Look |
| --- | --- |
| Python judgment rules | `docs/llm/app/python-engineering-rules.md` |
| Runtime configuration, environment variables, OAuth/GCS settings | `app/config.py`, `app/composition/` |
| HTTP contract, routers, Pydantic schemas, auth dependencies, error mapping | `app/presentation/routers/`, `app/presentation/schemas/`, `app/presentation/exception_handlers.py` |
| Frontend layout, Signals/Zoneless setup, quality gate | `view/AGENTS.md` |
| Angular component, template, DI, and Signals judgment rules | `docs/llm/view/angular-style-guide.md` |
| TypeScript typing, error handling, class visibility, and naming rules | `docs/llm/view/typescript-engineering-rules.md` |
| Backend unit/integration, frontend, and browser E2E tests | `.agents/rules/tests-guide.md`, `pyproject.toml`, `vitest.config.ts`, `playwright.config.ts` |
