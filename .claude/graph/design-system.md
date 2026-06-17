# 🎯 Design System Role

**Purpose:** own semantic tokens — color, typography, spacing, radius, hover.

## Source of truth
- `src/styles/tailwind.css` (Tailwind v4 `@theme` / CSS variables)
- `src/styles/designSystem.js`
- `src/theme/` directory
- shadcn config: `new-york`, `cssVariables: true`, base `slate`

## Mandate
- All color via semantic CSS variables (`--background`, `--foreground`,
  `--primary`, `--muted`, `--destructive`, etc.) — never raw hex in components.
- One spacing scale, one radius scale, one shadow scale — Tailwind tokens.
- Typography pairing defined once; components reference scale classes.
- Hover/focus system defined centrally; components consume it.
- Dark mode driven entirely by variable swaps, not duplicated component styles.

## Checklist
- [ ] No hard-coded colors/spacing in components
- [ ] New tokens added to the central files, documented in `decisions.md`
- [ ] Light + dark both resolve for every token used
- [ ] No duplicate / near-duplicate token definitions

## Exit criteria
Token set is the single source; components only reference it.
