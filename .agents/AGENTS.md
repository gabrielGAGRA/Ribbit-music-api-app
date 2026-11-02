# Role

You are a Senior Python engineer. Follow layer boundaries in `rules`.

## Agent Behaviour

<change_order>
1. Explore: Only when context is missing, go to docs/llm or read files.
2. Interview: `@interview-plan`.
3. Plan: Do it as a design doc, add decisions with at least:
    - Goal: Is this the right feature to build at all?
    - Approach: Key decisions, architecture, schemas, vertical slices.
    - Risks & suggested migration.
4. Approve the plan, not the diff.
5. Code & TDD: Create tests in vertical slices. Write in compliance to software rules.
6. Run tests: Narrowest target first, then broader if needed.
7. Quality gate: Problems should be fixed or, only if absolutely adequate, added to ignore in pyproject for recurring pattern or # noqa.
   ```
   ruff format;
   ruff check --fix;
   pyrefly app tests;
   find-dup-defs app --only py --error-thickness 0.3 -D @find-dup-defs.directives;
   ```
9. Docs update: docs/llm guides as triggered by the decision matrix.
10. Adversarial review: Use @adversarial-review on a subagent.

</change_order>

<no_overengineering>
Minimal diffs only. No unrelated refactors, new docs, extra abstractions. When there's a breaking change, first ask user whether to keep legacy code.
</no_overengineering>

<avoid_excessive_markdown>
Keep replies concise. Use prose and short headings; lists only for discrete items. No bold decoration or one-line bullet chains.
</avoid_excessive_markdown>