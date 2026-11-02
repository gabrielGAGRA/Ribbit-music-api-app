# Angular Engineering Rules & Style Guide

Scope: Angular view only (`view/`). Formatting is handled by Oxfmt; mechanical syntax checks are enforced via `.oxlintrc.json` and `eslint.config.mjs` and not repeated in depth. General TypeScript standards (immutability, error handling, typing) follow `typescript-engineering-rules.md`.

Gate: `npm run format`, `npm run lint:fix`, `npm run typecheck`.

---

## 1. Architecture & Component Model

- ALWAYS use standalone components, directives, and pipes; NEVER introduce new `NgModule`s.
  Why: Standalone primitives eliminate module indirection, enable fine-grained tree-shaking, and simplify the dependency graph. [Lint: yes (`@angular-eslint/prefer-standalone`)]
- ALWAYS organize files by feature areas inside `view/` (e.g., `view/movies/booking/`); NEVER group files by technical category (e.g., `components/`, `services/`, `directives/`).
  Why: Co-locating related units reduces context switching and isolates blast radius during refactors. [Lint: no]
- ALWAYS keep application bootstrap inside `view/main.ts` using `bootstrapApplication()`.
  Why: Maintains a uniform, predictable entry point across applications. [Lint: no]
- ALWAYS keep source files focused on a single concept (one component, directive, or service per file).
  Why: Prevents bloated files and keeps tests, templates, and styles aligned 1:1. [Lint: no]

## 2. State Management & Reactivity

- ALWAYS use Signals (`signal()`, `computed()`, `effect()`) for local and component-level reactive state; NEVER use `BehaviorSubject` or `Subject` for basic view state.
  Why: Signals provide synchronous, glitch-free reactivity with automatic dependency tracking and zero subscription leak risk. [Lint: yes (`@angular-eslint/prefer-signals`)]
- ALWAYS use signal-based inputs (`input()`, `input.required()`), outputs (`output()`), and two-way models (`model()`); NEVER use `@Input()`, `@Output()`, or `@Model()` decorators.
  Why: Provides compile-time type safety, cleaner reactivity, and avoids decorator-based lifecycle lag. [Lint: yes (`@angular-eslint/prefer-signals`, `@angular-eslint/prefer-signal-model`)]
- ALWAYS invoke signals as functions with parentheses `mySignal()` in templates and TS code; NEVER pass an uncalled signal reference where the value is expected.
  Why: An uncalled signal reference is an object/function that evaluates truthy, creating silent logical bugs. [Lint: yes (`@angular-eslint/no-uncalled-signals`)]
- ALWAYS treat signal state as immutable; update signals using `.set()` or `.update()`, NEVER mutate objects inside a signal in-place.
  Why: Direct object mutations bypass change notifications and break downstream `computed()` tracking. [Lint: no]
- ALWAYS keep `computed()` signals pure and return a value; NEVER perform side effects inside a computed expression.
  Why: Computed signals evaluate lazily and memoize values; side effects cause unpredictable, repeated executions. [Lint: yes (`@angular-eslint/computed-must-return`)]
- ALWAYS prefer signal-based services for shared feature state. Use NgRx SignalStore for intermediate cross-feature state, and full NgRx only with explicit architectural justification.
  Why: Minimizes boilerplate and keeps state close to consumption points without unneeded global store overhead. [Lint: no]

## 3. Dependency Injection

- ALWAYS inject dependencies using `inject()`; NEVER use constructor parameter injection for dependencies.
  Why: Guarantees cleaner type inference, eliminates constructor boilerplate, simplifies class inheritance, and plays cleanly with class field initializers. [Lint: yes (`@angular-eslint/prefer-inject`)]
- ALWAYS place `inject()` declarations at the top of the class before methods and other properties.
  Why: Surfacing dependencies at the class boundary standardizes readability. [Lint: yes (`@angular-eslint/inject-at-top`)]
- ALWAYS declare shared services with `{ providedIn: 'root' }` unless scoped instance lifecycle is required.
  Why: Guarantees tree-shakable singletons without polluting module providers. [Lint: yes]
- NEVER subscribe to Observables inside constructors or field initializers; bridge to signals via `toSignal()` in an injection context or manage lifecycles with `takeUntilDestroyed()`.
  Why: Prevents memory leaks and ensures cleanup upon component destruction. [Lint: yes (`@angular-eslint/no-implicit-take-until-destroyed`)]

## 4. Components, Templates & Change Detection

- ALWAYS design for Zoneless change detection with `ChangeDetectionStrategy.OnPush`.
  Why: Signals explicitly schedule DOM notifications, removing Zone.js runtime monkey-patching overhead and optimizing rendering performance. [Lint: yes (`@angular-eslint/prefer-on-push-component-change-detection`)]
- NEVER call `ChangeDetectorRef.markForCheck()` or `detectChanges()` when using signals properly.
  Why: Signal modifications notify the zoneless scheduler automatically; manual checks bypass the reactivity graph. [Lint: no]
- ALWAYS use modern built-in control flow (`@if`, `@for`, `@switch`); NEVER use legacy structural directives (`*ngIf`, `*ngFor`, `*ngSwitch`).
  Why: Built-in control flow is faster, provides proper TypeScript type-narrowing in templates, and does not require directive imports. [Lint: yes (`@angular-eslint/template/prefer-control-flow`)]
- ALWAYS provide a unique `track` key in `@for` blocks.
  Why: Eliminates DOM thrashing and preserves element state when lists update. [Lint: yes]
- ALWAYS use direct class and style bindings (`[class.foo]="..."`, `[style.color]="..."`); NEVER use `NgClass` or `NgStyle`.
  Why: Native attribute bindings are faster, avoid importing directive dependencies, and align with standard HTML. [Lint: yes (`no-restricted-imports`, `@angular-eslint/template/prefer-class-binding`, `@angular-eslint/template/prefer-style-binding`)]
- ALWAYS keep components presentation-focused; delegate business logic, data transformations, and orchestration to services or pure functions.
  Why: Decouples UI from business logic and maximizes testability. [Lint: no]
- NEVER write complex expressions or nested conditions in templates; extract them to `computed()` properties on the component.
  Why: Keeps template declarative and maintainable. [Lint: no]
- ALWAYS mark properties used only in templates as `protected` and Angular-initialized properties as `readonly`, in compliance with `typescript-engineering-rules.md`.
  Why: Prevents leaking template internal state into the public DI/query API and protects bound references against accidental reassignment. [Lint: yes (`@angular-eslint/prefer-output-readonly`, `typescript/prefer-readonly`)]
- ALWAYS name event handlers after the business action (`saveProfile()`), NEVER after the DOM trigger event (`handleClick()`).
  Why: Expresses intent directly in template bindings. [Lint: no]
- ALWAYS keep lifecycle methods concise by delegating work to helper methods, and ALWAYS implement lifecycle interfaces (`OnInit`, `OnDestroy`).
  Why: Guarantees correct method spelling and maintains readable initialization sequences. [Lint: yes (`@angular-eslint/use-lifecycle-interface`, `@angular-eslint/no-empty-lifecycle-method`)]
- NEVER declare lifecycle hooks as `async` (`async ngOnInit()`).
  Why: Angular does not await lifecycle promises; async hooks hide unhandled rejections and cause execution race conditions. [Lint: yes (`@angular-eslint/no-async-lifecycle-method`)]

## 5. Naming & Layout

- ALWAYS name files using lowercase hyphenated words matching the primary class identifier (`user-profile.component.ts` or `user-profile.ts` for `UserProfileComponent`).
  Why: Guarantees cross-platform filesystem compatibility and predictable module resolution. [Lint: no]
- ALWAYS colocate a component's TypeScript, template (`.html`), and style (`.css`/`.scss`) files under the same base name.
  Why: Keeps component units cohesive and straightforward to locate. [Lint: no]
- ALWAYS colocate unit test files with the code under test and name them with `.spec.ts`.
  Why: Ensures tests remain visible alongside source code and prevents isolated, forgotten test suites. [Lint: no]
- ALWAYS prefix component selectors with `app-` (kebab-case) and directive selectors with `app` (camelCase).
  Why: Prevents collisions with standard HTML tags and third-party components. [Lint: yes (`@angular-eslint/component-selector`, `@angular-eslint/directive-selector`)]
- ALWAYS suffix component classes with `Component` and directives with `Directive`.
  Why: Disambiguates Angular constructs across symbols. [Lint: yes (`@angular-eslint/component-class-suffix`, `@angular-eslint/directive-class-suffix`)]
- NEVER use generic filenames like `helpers.ts`, `utils.ts`, or `common.ts`; use feature- or domain-descriptive names.
  Why: Prevents indiscriminate dumping of unrelated logic. [Lint: no]