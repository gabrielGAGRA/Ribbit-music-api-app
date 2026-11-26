@[c:\Users\gabri\Documents\PROJETOS\POLI\Lab_Engenharia_Software\docs\llm\view\angular-style-guide.md] @[c:\Users\gabri\Documents\PROJETOS\POLI\Lab_Engenharia_Software\.oxlintrc.json] @[c:\Users\gabri\Documents\PROJETOS\POLI\Lab_Engenharia_Software\eslint.config.mjs] 

You should keep most of Google’s modern Angular style guide, but tighten it around today’s state‑of‑the‑art (standalone + signals + inject) and push anything mechanically checkable into Angular ESLint / es‑angular rules so your docs stay thin and focused on “NEVER/ALWAYS + Why”.[[angular](https://angular.dev/style-guide)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)][[github](https://github.com/noneforge/eslint-config-angular)]
Below I’ll (1) summarize “modern Angular” in 2026, (2) mark what from angular-style-guide.md is worth keeping vs changing, and (3) suggest what to automate with lint and how it fits your existing TypeScript+oxlint setup.
Angular state of the art (2026)
Modern Angular (17–20+) assumes three big defaults for new code:
Standalone components by default. New components are standalone: true and imported directly via the imports array rather than via NgModule declarations.[[v18.angular](https://v18.angular.dev/guide/components/importing/)][[angular](https://angular.dev/guide/components)][[angular](https://angular.dev/guide/ngmodules/overview)]
Signals as the primary state model. signal(), computed(), and effect() are the standard way to express local and shared reactive state, with signal‑based input(), output(), and model() replacing decorator inputs/outputs.[[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)][[angular](https://angular.dev/essentials/signals)]
Modern DI with inject(). Angular’s own style guide now explicitly recommends inject() over constructor injection, both for readability and type inference.[[angular](https://angular.dev/style-guide)][[angular](https://angular.dev/guide/di)][[v17.angular](https://v17.angular.io/api/core/inject)]
Best‑practice teams in 2026 also:
Use OnPush/zoneless change detection as default for performance, leaning on the signals model instead of manual markForCheck().[[coderio](https://www.coderio.com/blog/reports/outsourcing-angular-development-guide/)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
Structure code by feature (feature folders, co‑located tests/templates/styles), not by type (components/, services/ folders).[[angular](https://angular.dev/style-guide)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
Enforce Angular‑specific rules via ESLint (@angular-eslint or configs like eslint-config-angular), on top of strict TypeScript/oxlint.[[github](https://github.com/noneforge/eslint-config-angular)][[coderio](https://www.coderio.com/blog/reports/outsourcing-angular-development-guide/)]
Your Angular rules should align with this picture and with your existing TS rules and SKILL governance.
What to keep from angular-style-guide.md
Google’s Angular style guide you imported is already the recent Angular 17+ version, so most of it is aligned with modern patterns. The good parts to keep (possibly slightly rephrased into ALWAYS/NEVER bullets) are:[[angular](https://angular.dev/style-guide)]
Naming and file layout
These are still solid and map well to feature‑based repos:
Hyphen‑separated file names that match the primary class identifier (user-profile.ts for UserProfile).
Tests colocated with the code under test and named with .spec.ts (user-profile.spec.ts).
Co‑locating component TS, template, and styles under the same basename (user-profile.ts, user-profile.html, user-profile.css).
Avoiding generic file names like helpers.ts or utils.ts and preferring feature‑oriented names.
These complement your TypeScript rules (descriptive names, no “helpers.ts”) without contradicting them.
Project structure
These conventions are still good:
All UI code under src/, non‑UI scripts/config outside.[[angular](https://angular.dev/style-guide)]
Bootstrap in src/main.ts, using the modern bootstrapApplication API.[[v17.angular](https://v17.angular.io/guide/standalone-components)][[angular](https://angular.io/guide/component-overview)]
Organize under src/ by feature areas, with nested sub‑features (e.g. movie-reel/show-times/film-details/).[[angular](https://angular.dev/style-guide)]
“One concept per file” for components/directives/services where possible.
You already enforce some structure with no-restricted-imports and ignorePatterns in oxlint, so this stays mostly as doc‑level guidance.
Components, directives, and templates
This section is very compatible with your TS rules and worth keeping:
Group Angular‑specific properties (injected deps, input, output, queries) at the top of the class, before methods.[[angular](https://angular.dev/style-guide)]
Keep components/directives focused on presentation, pushing reusable logic into services or pure functions.[[v18.angular](https://v18.angular.dev/style-guide/)]
Avoid overly complex template logic; move complicated conditions or calculations into computed properties in the class.[[v18.angular](https://v18.angular.dev/style-guide/)]
Use protected for members only used in templates, keeping public members as the DI/template API.
Use readonly for Angular‑initialized properties (input, output, model, queries) so template‑bound state isn’t mutated accidentally.
Prefer class/style bindings over ngClass/ngStyle for clarity and performance.[[angular](https://angular.dev/style-guide)]
Name event handlers for what they do (saveUserData()) rather than for the triggering event (handleClick()).
These integrate nicely with your TS Engineering rules (protected template members, prefer readonly, logging via injected logger, etc.), so the Angular doc can just reference the TS doc where they overlap.
What to change or add for 2026
The biggest gap in angular-style-guide.md is that it doesn’t fully encode “signals + standalone everything + new control flow” as hard rules, and it still treats some things as options that are effectively outdated in 2026.[[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)][[angular](https://angular.dev/style-guide)]
Architecture and component model
You should strengthen and update to:
ALWAYS use standalone components for new code. NgModules are for legacy; new components/classes should be standalone and imported via imports.[[angular](https://angular.dev/guide/ngmodules/overview)][[v18.angular](https://v18.angular.dev/guide/components/importing/)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
ALWAYS structure features around standalone components + signal‑based services, not shared NgModules or global services unless necessary.[[angular](https://angular.dev/essentials/signals)][[v18.angular](https://v18.angular.dev/guide/components/importing/)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
NEVER introduce new NgModules in greenfield Angular code; only keep or migrate legacy ones.[[angular](https://angular.dev/guide/ngmodules/overview)][[coderio](https://www.coderio.com/blog/reports/outsourcing-angular-development-guide/)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
These belong in your Angular doc as explicit ALWAYS/NEVER bullets, with the “Why” focusing on dependency graph clarity and performance.
State management and reactivity
You should add explicit rules around signals and control flow:
ALWAYS use signals for local component state (signal, computed, effect) instead of manual Subject/BehaviorSubject for simple cases.[[angular](https://angular.dev/essentials/signals)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
ALWAYS use signal‑based input() / output() / model() for new inputs/outputs, not @Input/@Output decorators.[[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
ALWAYS treat signals as immutable values and update via set()/update(), not mutating underlying objects directly.[[angular](https://angular.dev/essentials/signals)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
Prefer built‑in control flow (@if, @for, @switch) over *ngIf/*ngFor in new templates for performance and readability.[[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
For cross‑feature state (NgRx vs signals services), define house rules (e.g. “signals services by default, NgRx Signal Store for mid‑complexity, full NgRx only if justified”).[[coderio](https://www.coderio.com/blog/reports/outsourcing-angular-development-guide/)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
Dependency injection and services
Your DI section should explicitly reflect current DI best practices:
ALWAYS inject dependencies with inject() where possible, including in components and services.[[angular](https://angular.dev/guide/di)][[v17.angular](https://v17.angular.io/api/core/inject)][[angular](https://angular.dev/style-guide)]
Prefer providedIn: 'root' injectable services for shared state and singletons, and component providers for strictly local behavior.[[angular](https://angular.dev/guide/di)][[v18.angular](https://v18.angular.dev/style-guide/)]
NEVER subscribe in constructors or per‑component services; keep subscriptions in lifecycle hooks (ngOnInit) with takeUntilDestroyed() or signals bridging.[[angular](https://angular.dev/essentials/signals)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
This updates Google’s DI text from “prefer inject function” to a stricter ALWAYS/NEVER stance.[[angular](https://angular.dev/style-guide)]
Change detection and performance
You should explicitly codify change detection strategy:
ALWAYS use OnPush (or the zoneless default) for components; do not rely on the default legacy change detection.[[coderio](https://www.coderio.com/blog/reports/outsourcing-angular-development-guide/)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
NEVER call markForCheck() when you’re using signals correctly; signals should drive updates.[[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)][[angular](https://angular.dev/essentials/signals)]
ALWAYS lazy‑load heavy view chunks via @defer and prefer SSR + incremental hydration for public pages.[[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
These don’t exist yet in your imported guide but are now considered standard practice for serious Angular teams.[[coderio](https://www.coderio.com/blog/reports/outsourcing-angular-development-guide/)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
What to automate with lint (and how)
Given your SKILL and TS + oxlint setup, the rule of thumb is: anything that can be expressed as a syntactic pattern or simple metric goes into lint; docs are reserved for trade‑offs and architecture choices.
Here’s a concrete mapping for Angular‑specific rules:
Good candidates for full automation
Use ESLint (with @angular-eslint or es‑angular / eslint-config-angular) plus your existing TypeScript/oxlint:
Rule (doc wording)
Automation strategy
ALWAYS prefer inject() over constructor injection
Enable a prefer‑inject rule (provided by configs like eslint-config-angular) to flag constructor DI when inject is available.[[angular](https://angular.dev/style-guide)][[github](https://github.com/noneforge/eslint-config-angular)][[angular](https://angular.dev/guide/di)]
ALWAYS use standalone components for new code
Enable a prefer‑standalone / standalone‑only rule to reject new NgModule declarations and components with standalone: false.[[v18.angular](https://v18.angular.dev/guide/components/importing/)][[github](https://github.com/noneforge/eslint-config-angular)][[angular](https://angular.dev/guide/ngmodules/overview)]
ALWAYS enforce component/directive class suffixes
Use component-class-suffix and directive-class-suffix rules from Angular ESLint.[[github](https://github.com/noneforge/eslint-config-angular)]
ALWAYS use OnPush/zones‑free change detection
Use prefer-on-push-component-change-detection (or equivalent) to enforce ChangeDetectionStrategy.OnPush and modern zoneless defaults.[[github](https://github.com/noneforge/eslint-config-angular)]
ALWAYS use signal‑based inputs/outputs in new code
Use prefer-signals, no-uncalled-signals, or custom rules to ban decorator inputs/outputs on new components.[[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)][[github](https://github.com/noneforge/eslint-config-angular)][[angular](https://angular.dev/essentials/signals)]
ALWAYS use readonly for Angular‑initialized properties
You already enforce typescript/prefer-readonly; ensure it runs on Angular component classes.
Members used by templates are protected
You already have this in TS doc; back it with a template‑aware lint rule that tracks template accesses and enforces protected visibility.
Prefer class/style bindings over ngClass/ngStyle
Enable a rule banning ngClass/ngStyle except in whitelisted cases, or use config that prefers direct [class]/[style] bindings.[[angular](https://angular.dev/style-guide)][[github](https://github.com/noneforge/eslint-config-angular)]
Component selectors follow app- prefix and kebab‑case
Angular ESLint’s selector naming rules handle this, enforcing prefix and casing.[[github](https://github.com/noneforge/eslint-config-angular)]
Test files named *.spec.ts and colocated
Use ESLint file‑name rules or a custom lint to ensure *.spec.ts naming and directory proximity.
Most of these are already present in modern configs like eslint-config-angular, which you can adopt or mirror in your es‑angular setup.[[github](https://github.com/noneforge/eslint-config-angular)]
Rules that should stay mostly in docs
Some things are hard to lint precisely or would produce too many false positives:
“Avoid overly complex logic in templates” → you can measure template complexity and limit nesting, but the threshold is subjective; keep guidance in docs and use a gentle lint metric if needed.[[v18.angular](https://v18.angular.dev/style-guide/)]
“Keep components focused on presentation” vs services → static analysis can’t reliably deduce business vs presentation logic; this belongs in reviews and docs.[[v18.angular](https://v18.angular.dev/style-guide/)]
Feature‑based folder structure (no components/ mega‑folder) → you can block certain folder names, but migrations are context‑dependent; keep in docs with a few linted bans (e.g. no src/components/ root).[[angular](https://angular.dev/style-guide)]
State‑management choice (signals services vs NgRx vs Signal Store) → architecture topic, not per‑file lint.
Use SKILL’s pattern: doc explains the trade‑off; thin rule files just give you a checklist or pointers.
How this fits your existing TS + oxlint rules
Your typescript-engineering-rules.md already encodes strong TS invariants: no any, no blind as/!, protected template members, prefer readonly, error handling patterns, etc. The Angular rules should:
Reference, not duplicate, TS rules. For example: “Template‑only members follow the TS rule ‘Members used by a template are protected, never private’.”
Add Angular‑specific constraints: standalone, signals, inject, selector naming, template bindings.
Use the same NEVER/ALWAYS + Why cadence, with separate bullets when two approaches are allowed (e.g. “ALWAYS use signals for local state” vs “ALWAYS justify NgRx for complex cross‑feature state”).
Your oxlint config already bans default exports, enforces type‑imports, and prefers readonly; Angular lint rules will sit alongside that, mainly in eslint.config.mjs and the es‑angular configuration.
Suggested structure for the Angular rules doc
To stay consistent with SKILL and your TS doc, your angular-style-guide.md (or a new angular-engineering-rules.md) can be structured like:
Scope & Gate: “Scope: Angular view only (src/). Gate: npm run lint:angular, npm run typecheck.”
1. Architecture
ALWAYS use standalone components for new code (Why: simpler dependency graph, better lazy loading).
NEVER add new NgModules except for migrating legacy code (Why: outdated pattern).[[v18.angular](https://v18.angular.dev/guide/components/importing/)][[angular](https://angular.dev/guide/ngmodules/overview)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
2. State & Reactivity
ALWAYS use signals for local component state; NEVER use BehaviorSubject for simple view state (Why: less boilerplate, better performance).[[angular](https://angular.dev/essentials/signals)][[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
ALWAYS use signal‑based input()/output()/model() for new inputs/outputs.[[2muchcoffee](https://2muchcoffee.com/blog/angular-best-practices-2026/)]
3. Dependency Injection
ALWAYS inject with inject(); NEVER introduce new constructor‑injected dependencies without justification.[[v17.angular](https://v17.angular.io/api/core/inject)][[angular](https://angular.dev/guide/di)][[angular](https://angular.dev/style-guide)]
4. Components & Templates
ALWAYS group Angular‑specific properties at the top.
ALWAYS declare template‑only members as protected and readonly.
NEVER use ngClass/ngStyle in new templates; prefer class/style bindings.[[angular](https://angular.dev/style-guide)]
5. Naming & Layout
ALWAYS name files with hyphen‑separated words matching the main class (user-profile.ts).
ALWAYS colocate *.spec.ts tests with the component code.
Each bullet where lint is possible should have a small “Lint: yes/no” annotation internally so the adapter rule file knows what to enforce and what to just document.
If you want, next step I can draft the actual Angular rule bullets in your NEVER/ALWAYS style, and a minimal ESLint/es‑angular config snippet that turns on the key rules (standalone, signals, inject, selectors, OnPush) so your LLM docs can stay as thin architecture maps.
