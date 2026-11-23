# TypeScript Engineering Rules

Scope: Angular view only (`view/`). Formatting is Oxfmt; everything a linter or `tsc` catches is configured in `.oxlintrc.json`, `eslint.config.mjs`, `tsconfig.json`, and `.oxfmtrc.json` and is not repeated here. Angular-specific rules live in `angular-style-guide.md`.

Gate: `npm run format`, `npm run lint:fix`, `npm run typecheck`.

## 1. Imports and Modules

- Export only what other modules use (named exports are enforced by linter).
- Namespace import (`import * as x`) for many symbols from one large API; named import otherwise.
- Rename an import (`as`) only to avoid a collision or clarify an unclear name.

## 2. Errors & Logging

- ALWAYS assume a caught value is an `Error` unless the API is known to throw something else.
  Why: Defensive `typeof e === 'string'` branches are boilerplate for a case that does not exist.
- NEVER swallow an exception silently; an empty `catch` needs a comment saying why.
- Keep `try` blocks to the lines that can throw.
- Define an `Error` subclass when `Error` alone cannot carry the information.
- NEVER return `{error}` objects or error containers; throw.
- `console.warn` and `console.error` are allowed for now (other `console` methods are banned by linter); gradually replace them with an injected logger.

## 3. Language Features

- NEVER pass a named function directly as a callback to `map`/`filter`/`forEach` (`map(parseInt)`) when extra callback arguments could alter behavior; wrap it in an arrow function that forwards only the intended arguments.
- ALWAYS parse numbers with `Number()` and check `Number.isFinite()`; never unary `+`, `parseInt`, or `parseFloat` for base 10.
- Prefer `Map`/`Set` over plain objects used as dynamic dictionaries (`{[k: string]: T}`).
- Getters are pure: no side effects, and no pass-through accessors (make the field `readonly`).
- Parameter defaults have no side effects; past a few optionals take an options object.
- NEVER use `arguments`; use rest parameters.
- An arrow function stored in a class field is only for event handlers that must be bound and uninstalled.
- Spread only iterables into arrays and only objects into objects.

## 4. Types

- NEVER use `any`; use `unknown` and narrow with a type guard. If unavoidable, suppress the rule with a comment that says why.
- NEVER use `as` or `!` without a comment that says why it is safe, unless it is obvious. Prefer a runtime check. A double assertion goes through `unknown`.
- NEVER put `| null` or `| undefined` in a type alias definition; add nullability where the alias is used.
- Prefer `field?: T` over `field: T | undefined`.
- Pick the simplest type construct; no mapped or conditional types where an interface expresses it.
- Use a tuple for a two-value return and an object once there are three or more.

## 5. Classes

- ALWAYS use TypeScript's `private` keyword, never ECMAScript `#private` fields (except in external library code that requires hard runtime encapsulation).
  Why: Aligns with the Google TypeScript Style Guide and plays cleanly with TypeScript visibility modifiers (`private`/`protected`, `readonly`) and Angular `inject()` fields without down-leveling overhead. (For Angular DI, always use `private readonly service = inject(Service)` per `angular-style-guide.md`, never constructor parameter injection.)
- Members used by an Angular template are `protected`, never `private` or `public`.
- Initialize fields where they are declared; do not dynamically add or remove properties after construction.
- NEVER use a class only as a namespace for static members; export functions and constants.

## 6. Naming

- Names are descriptive; do not abbreviate by deleting letters (`cstmrId`). Single letters only in scopes of 10 lines or fewer.
- NEVER encode the type in the name (`nameString`, `optFoo`).
- Treat acronyms as words: `loadHttpUrl`.
- A leading `_` is allowed only on unused parameters.
- Backend JSON keys and HTTP headers keep their wire casing; map them in the data layer.
- Enums: prefer string literal unions; if an enum is needed, members are `UPPER_CASE`.

## 7. Comments and JSDoc

- NEVER put types in JSDoc.
- NEVER restate the name or type; `@param`/`@returns` only when they add information beyond types.
- Method descriptions start with a third-person verb ("Returns ...").
- Use a `/* paramName= */` comment at a call site only when a positional argument is unclear; prefer an options object.
- `@deprecated` must say how to migrate.
- JSDoc goes before decorators.
