---
name: commit 
description: >- 
  Use only when you are about to run any git write command.
---

# Git Commit Automation

## 1. Workflow (Step-by-Step)

### A. Commits

1.	Feature branch: If the current branch is a base main, offer to create a branch. Branches should separate every change by context, always offer to create when the goal changed (e.g. a refact changed to a feature).
	1.1.	Name with existing prefixes: feat/, fix/, refact/ + short kebab slug.
	1.2.	If accepted, give the user a PR title and body draft using the PR Message Draft Rules below.
2.	One logical purpose per commit.
3.	Draft following the Rules below.
4.	Commit with hooks disabled.


---

## 2. Rules of a Great Commit Message

Subject format (required):
`<type>[optional scope][optional !]: <description>`
	⁃	Types: feat, fix, build, chore, ci, docs, style, refactor, perf, test.
	⁃	Scope (optional): noun in parentheses, e.g. feat(parser):.
	⁃	Breaking change: append ! before : and add a BREAKING CHANGE: footer.
	⁃	Description: short summary in imperative mood, immediately after :

### 1. Separate subject from body with a blank line
Begin with a single summary line (subject), a blank line, then the body. 

### 2. Limit the subject line to 50 characters
Keep the subject around 50 characters; 72 is the hard limit. 
If you cannot summarize well in 50 characters, the commit may be too large — split it.

### 3. Capitalize the subject line

### 4. Do not end the subject line with a period

### 5. Use the imperative mood in the description
Write as a command. The description should complete: If applied, this commit will [description].
	⁃	refactor: Simplify filesystem adapter (correct)

### 6. Use the body to explain what and why, not how
The diff shows how. The body explains the problem, context, and side effects.

---

Example:
```
refactor: Remove unused catalog persistence port

The MemoryCatalogPersistence fake covered all test scenarios;
the redundant Protocol definition added noise and drifted from
the domain interface. No runtime behavior changes.
```

Breaking change example:
```
feat!: Drop support for Node 6

BREAKING CHANGE: use JavaScript features not available in Node 6.
```

---

## 3. PR Message Draft Rules

	⁃	Title: Same rules as the commit subject (type[scope]: description, imperative, capitalized description, ≤50–72 chars, no period).
	⁃	Body: Include:
	⁃	Summary — 1–3 bullets on what changed and why
	⁃	Test plan — checklist of verification steps run or to run

---

## 4. Execution Guardrails

	⁃	Hooks disabled: git -c core.hooksPath=.git/hooks-empty.
	⁃	No force push. Never push unless explicitly asked.
	-	Use a HEREDOC (bash) or here-string (PowerShell) so blank lines and wrapping survive.