# Rule — TypeScript (5.9, strict)

Scope: `frontend/src/**`. `tsconfig.json` runs in **strict** mode. Gate: `npm run typecheck`.

## Must

- **No `any`.** Use precise types, `unknown` + narrowing, or generics. If a third-party type
  is missing, declare a minimal local type — don't widen to `any`.
- **`import type { … }`** for type-only imports (keeps them out of the JS bundle).
- **Path aliases**: import via `@/…` (`@/components`, `@/components/ui`, `@/lib`,
  `@/lib/utils`, `@/hooks`). No deep relative `../../../` chains.
- **Shared domain types** live in `@/types`. Reuse them; don't redefine a shape inline that
  already exists there.
- Type all exported function signatures and component props explicitly.
- Prefer discriminated unions over boolean flags for multi-state.

## Avoid

- `as` casts except at trust boundaries (e.g. parsing external JSON) — and narrow right after.
- Non-null `!` assertions where a guard reads clearer.
- `enum` — prefer `as const` union objects (codebase convention).

## Migration note

The codebase finished its `.jsx → .tsx` migration, but a few `api/*.js` files remain
(`api/axios.js`, `api/tasks.js`, `api/users.js`). Don't add new `.js`; if you touch one
substantially, prefer migrating it to `.ts` — but keep behavior identical and flag the change.
