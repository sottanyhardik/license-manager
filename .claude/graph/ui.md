# 🎨 UI Role

**Purpose:** visual consistency and compact, Tailwind-only layouts using
existing shadcn primitives.

## Mandate
- Tailwind utilities only — no inline styles, no new `.css` unless unavoidable.
- Reuse `@/components/ui/*` (button, card, dialog, input, select, tabs, badge,
  tooltip, switch, checkbox, separator, skeleton, textarea, label, sonner).
- shadcn `new-york` style; respect CSS variables / `slate` base color.
- Icons: `lucide-react` only. Replace any `bootstrap-icons` usage.
- Compact spacing; consistent radius, shadow, hover/focus states.
- Animations via `framer-motion` with shared timings.

## Checklist per component
- [ ] No duplicate component — an existing primitive doesn't already cover it
- [ ] Uses design tokens (see `design-system.md`), not hard-coded hex/px
- [ ] Hover + focus-visible states present and consistent
- [ ] Dark mode honored via CSS variables
- [ ] No leftover Bootstrap classes / bootstrap-icons
- [ ] Imports cleaned

## Exit criteria
`npm run lint` + `npm run typecheck` clean for touched files; no visual
inconsistency vs. sibling components.
