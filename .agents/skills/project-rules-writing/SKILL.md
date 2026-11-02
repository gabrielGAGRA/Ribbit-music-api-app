---
name: project-rules-writing 
description: > 
  Create, update, or self-heal project rules and conventions.
---

# Project Rules Governance

## 1. Layer choice (Skill vs Rule vs Passive doc)

| Layer | Canonical path | Purpose | When to use |
| --- | --- | --- | --- |
| Skill | .agents/skills/ | Punctual multi-step workflows | Commit, reviews, rule governance (this skill), test coverage |
| Rule | .agents/rules/ | Always-on or glob-triggered orientation maps | Layout/domain/test context when matching files are open; ~25 lines |
| Passive doc | docs/llm/ | Deep knowledge base | On demand when a rule points to it, or when this skill/checklist requires it |

Rules point to passive docs. Do not create a rule adapter for broad docs.

## 2. Rule file map (prefer append over new files)

	⁃	meta-rules — routing, priority, skill registry (alwaysApply: true)
	⁃	project-rules — tech stack, venv (alwaysApply: true)
	⁃	AGENTS.md — persona, XML behaviour tags (root; not a rule file)
	⁃	agents-feature-checklist decides what do update when planning or implementing a change in the repo.
	⁃	Others are scoped maps

Keep 5–8 rule files.

## 3. Create / extend a rule category

	1.	Classify: orientation map (rule) vs punctual workflow (skill) vs passive doc only.
	2.	Heavy doc — docs/llm/<topic>-guide.md (or append): guidelines, examples, trade-offs.
	3.	Thin adapter — accessible platform rules folder (e.g. .agents/rules/<name>.mdc): frontmatter (description, globs, alwaysApply: false) + short map. Point to the heavy doc for edge cases.
	```markdown
	---
	description: >
	Use when [concrete trigger].
	globs: app/**/*.py
	alwaysApply: false
	---

	# [Title] Map

	[Short facts that avoid a routine doc read]

	Deeper detail: docs/llm/<guide>.md
	```
	4.	Update meta-rules navigation if this is a new category.

## 4. Update an existing standard

	1.	Edit heavy doc in docs/llm/ for detailed changes.
	2.	Edit thin adapter only if triggers (description, globs) or top invariants changed.

## 5. Self-healing

	1.	Root cause — why the failure happened (missing context, ambiguous rule, wrong stack assumption).
	2.	Before/after — concrete wrong vs correct pattern.
	3.	Rewrite — append to the correct docs/llm/ doc when generalising: