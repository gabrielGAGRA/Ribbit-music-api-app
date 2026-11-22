---
trigger: model_decision
description: Use when writing, editing, or running backend, frontend, or E2E tests.
globs: tests/**, view/**/*.spec.ts, playwright.config.ts, vitest.config.ts
---

# Tests Guide

Run the narrowest relevant test target first, then broaden to full suites or coverage checks as needed.

## Suites & Commands

| Layer | Location | Command | Notes |
| --- | --- | --- | --- |
| Backend unit & integration | `tests/unit/`, `tests/integration/`, `tests/test_init_db.py` | `pytest <path>` / `pytest --cov=app --cov-report=term-missing --cov-fail-under=85` | Markers: `unit`, `integration` (`pyproject.toml`); fakes in `tests/utils/fakes.py`. |
| Frontend unit | `view/**/*.spec.ts` (co-located) | `npm test` | Vitest + jsdom (`vitest.config.ts`). |
| Browser E2E | `tests/e2e/**/*.e2e.ts` | `npm run test:e2e` | Playwright (`playwright.config.ts`); spins up isolated backend (`e2e.db`) + `ng serve`. |

## Conventions

- Write tests in small vertical slices alongside production changes; verify failures fail for the right reason.
- Backend tests allow `assert`, test fixtures, and local imports.
- Keep tests deterministic and isolated from external.
