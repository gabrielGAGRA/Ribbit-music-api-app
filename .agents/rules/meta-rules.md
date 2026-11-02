---
trigger: always_on
description: Use for rule priority, where to find docs, and when to invoke skills (planning, review, commit, and rule governance).
---

<!-- TEMPLATE: Inject-ready rule. Replace every FILL block with target-repo facts; delete this banner when done. -->

# Meta rules
## Priority (highest -> lowest)
1. AGENTS.md - persona and behavioral constraints
2. project-rules - repo scope, tech stack
3. agents-feature-checklist - change order (before, during, and after implementation)
4. project-architecture / project-domain-api - layout and sandbox explanations and pointers
5. project-tests - test layout and pointers
6. docs/llm/python-engineering-rules.md - coding standards (passive; read only when implementing)

## Skill Invocation (single registry)
| Trigger / Intent | Action |
| --- | --- |
| Commit, branch, or any git write | @commit |
| Create, edit, or self-heal agent rules / conventions | @project-rules-writing |
| User asks for a PR code review | @PR-code-review |
| Conflicts ith other commits made in the repository| @catchup |
| Ambiguous or relevant behavior change, before planning | @interview-plan |
| Any diff before delivery or git write | @adversarial-review |

## Navigation - when to read what
| Question | Read |
| --- | --- |
<!-- FILL: Navigation row — HTTP contract, validation, external I/O, AI message format. Discover: project-domain-api rule + routers/schemas. Keep: project-domain-api + docs/llm/domain-api-guide.md. -->
<!-- FILL: Navigation row — layer map / package layout. Discover: app/ tree. Keep: project-architecture + docs/llm/architecture-guide.md. -->
<!-- FILL: Navigation row — env, secrets, deploy runtime config. Discover: app/config.py, pipeline/, infra yaml. Keep: list concrete config paths. -->
| Python patterns, imports, DIP | docs/llm/software-engineering-rules.md |
<!-- FILL: Navigation row — test tree and pytest markers. Discover: tests/, pytest.ini. Keep: project-tests + docs/llm/tests-guide.md + tests/pytest.ini. -->
| Rule create / update / self-healing | @project-rules-writing skill |