---
name: interview-plan
description: Grill the user while planning.
---

# Grill Me

The plan is where human taste does the most work, because the plan is what produces the code.

Where taste decides:
- **Goal** — Is this the right feature to build at all?
- **Risks** — Did it surface the data leak before any code?
- **Rollout** — Is the blast radius small enough to ship?

## How to run the interview

1. **One question at a time, each with a recommended answer.**

2. **Every question must be able to change the build.** Know what you would do differently for each plausible answer. If every answer leads to the same outcome, cut the question.

3. **Adapt depth to stakes.** Stop asking once the critical unknowns, risks, and boundaries are resolved.

## Question coverage

Draw questions from these areas to shape the plan:
- **Goal**: What triggered this request; what problem it solves; whether this is the right feature to build at all.
- **Approach**: Architecture, data flow, tech stack, constraints, and contracts.
- **Risks**: Security vulnerabilities, data leak vectors, failure modes, race conditions, regressions surfaced before writing code.
- **Migration**: Breaking changes, legacy code retention, data migrations, backward compatibility.
- **Rollout**: Blast radius containment, staging, feature flags, fallback strategy.
- **Scope & Taste**: Must-haves vs. out of scope, user experience standards, rejection criteria.