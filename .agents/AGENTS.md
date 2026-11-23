# Agent Instructions

## Anti-Overengineering

Before writing new code, walk this ladder in order and stop at the first rung that solves the problem cleanly:

1. YAGNI — Does this need to exist at all?
2. Codebase reuse — Is it already implemented in this repo?
3. Standard library / platform — Can the language handle it natively?
4. Installed dependency — Does an existing package already cover it?
5. One-liner — Can it be expressed cleanly in a single line?
6. Minimum viable code — Write the smallest clean implementation; avoid single-caller wrappers and speculative abstractions.
7. Protected boundaries — Never cut trust-boundary validation, security checks, error handling, accessibility, or tests for risky logic.

For breaking changes, ask before if should keep legacy compatibility.

## Delivery & Verification

- Run the relevant quality gate and tests from `app/AGENTS.md`, `view/AGENTS.md`, or `.agents/rules/tests-guide.md` before finishing.
- Keep replies concise and direct.
