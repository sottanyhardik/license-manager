# Rule — Frontend UI (Tailwind v4 + shadcn/ui)

Scope: `frontend/src/**`. Mirrors and extends `.claude/rules.md`. Gates: `npm run lint`,
`npm run typecheck`, `npm run build`.

## Stack (verify before assuming)

- Tailwind **v4** (`@tailwindcss/vite`), CSS entry `src/styles/tailwind.css`.
- shadcn/ui — style `new-york`, base color `slate`, CSS variables on.
- Radix primitives, `framer-motion` for animation, `cmdk` for the Cmd+K palette.

## Must

- **Reuse `@/components/ui/*`** (button, card, dialog, input, select, …) before building new.
- **Icons: `lucide-react` only.** `bootstrap-icons` is a migration leftover — never add
  usages; remove them when you touch a file.
- **Toasts: `sonner`.** `react-toastify` is legacy — don't add new calls; migrate toward sonner.
- **Tailwind utilities first.** No new `.css` files without a real reason (only 4 exist — keep
  it that way). Compose classes with `cn()` from `@/lib/utils`.
- **Accessibility AA**: labels on inputs, focus-visible states, keyboard operability, adequate
  contrast in both light and dark themes.
- **Responsive** layouts required; keep DOM depth and spacing tight (compact mode).
- Consistent hover/focus states; shared animation timings via Framer Motion.

## Avoid

- Inline hex colors / magic px — use design tokens (`styles/tailwind.css`, `theme/`).
- Bespoke modal/dropdown/tooltip when a Radix-backed `ui/*` primitive exists.
- Behavior changes during a UI refactor (see "Preserve business logic" in CLAUDE.md §2).

Template: `.claude/templates/component.md`. Example: `.claude/examples/README.md`.
