# Angular Engineering Rules & Style Guide

Scope: Angular view only (`view/`). Formatting is handled by Oxfmt; mechanical syntax checks are enforced via `.oxlintrc.json` and `eslint.config.mjs` (standalone components, `OnPush`, `inject()` at top of class, Signals over `@Input`/`@Output`, `@if`/`@for`/`@switch` control flow, `[class.x]`/`[style.x]` bindings, `app-` selectors) and are not repeated in depth here. General TypeScript standards follow `typescript-engineering-rules.md`.

Gate: `npm run format`, `npm run lint:fix`, `npm run typecheck`.

---

## 1. Architecture & Component Model

- ALWAYS organize files by feature areas inside `view/src/app/features/`; NEVER group files by technical category (e.g., `components/`, `services/`, `directives/`).
  Why: Co-locating related units reduces context switching and isolates blast radius during refactors.
- ALWAYS keep application bootstrap inside `view/src/main.ts` using `bootstrapApplication()`.
  Why: Maintains a uniform, predictable entry point across applications.
- ALWAYS keep source files focused on a single concept (one component, directive, or service per file).
  Why: Prevents bloated files and keeps tests, templates, and styles aligned 1:1.

## 2. State Management & Reactivity

- ALWAYS use Signals (`signal()`, `computed()`, `effect()`, `input()`, `output()`, `model()`) for local and component-level reactive state; NEVER use `BehaviorSubject` or `Subject` for basic view state.
- ALWAYS treat signal state as immutable; update signals using `.set()` or `.update()`, NEVER mutate objects inside a signal in-place.
  Why: Direct object mutations bypass change notifications and break downstream `computed()` tracking.
- ALWAYS keep `computed()` signals pure; NEVER perform side effects inside a computed expression.
- ALWAYS prefer signal-based services for shared feature state. Use NgRx SignalStore for intermediate cross-feature state, and full NgRx only with explicit architectural justification.
  Why: Minimizes boilerplate and keeps state close to consumption points without unneeded global store overhead.

## 3. Dependency Injection

- ALWAYS inject dependencies using `inject()` at the top of the class; NEVER use constructor parameter injection.
- ALWAYS declare shared services with `{ providedIn: 'root' }` unless a component-scoped instance lifecycle is required.
- NEVER subscribe to Observables inside constructors or field initializers without lifecycle cleanup; bridge to signals via `toSignal()` in an injection context or use `takeUntilDestroyed()`.

## 4. Components, Templates & Change Detection

- ALWAYS design for Zoneless change detection with `ChangeDetectionStrategy.OnPush`.
- NEVER call `ChangeDetectorRef.markForCheck()` or `detectChanges()` when using signals properly.
  Why: Signal modifications notify the zoneless scheduler automatically; manual checks bypass the reactivity graph.
- ALWAYS provide a deterministic, unique `track` expression in `@for` blocks.
- ALWAYS keep components presentation-focused; delegate business logic, data transformations, and orchestration to services or pure functions.
  Why: Decouples UI from business logic and maximizes testability.
- NEVER write complex expressions or nested conditions in templates; extract them to `computed()` properties on the component.
  Why: Keeps templates declarative and maintainable.
- ALWAYS mark properties used only in templates as `protected` and Angular-initialized properties (`inject()`, `input()`, `output()`, `model()`, `viewChild()`) as `readonly`.
- ALWAYS name event handlers after the business action (`saveProfile()`), NEVER after the DOM trigger event (`handleClick()`).
  Why: Expresses intent directly in template bindings.
- ALWAYS keep lifecycle methods concise by delegating work to helper methods, and NEVER declare lifecycle hooks as `async` (`async ngOnInit()`).

## 5. Naming & Layout

- ALWAYS name files using lowercase hyphenated words matching the primary class identifier (`user-profile.component.ts` or `user-profile.ts` for `UserProfileComponent`).
  Why: Guarantees cross-platform filesystem compatibility and predictable module resolution.
- ALWAYS colocate a component's TypeScript, template (`.html`), and style (`.css`/`.scss`) files under the same base name.
  Why: Keeps component units cohesive and straightforward to locate.
- ALWAYS colocate unit test files with the code under test and name them with `.spec.ts`.
  Why: Ensures tests remain visible alongside source code and prevents isolated, forgotten test suites.
- NEVER use generic filenames like `helpers.ts`, `utils.ts`, or `common.ts`; use feature- or domain-descriptive names.
  Why: Prevents indiscriminate dumping of unrelated logic.
