# 🔍 QA Role

**Purpose:** final gate — lint, types, build, a11y, responsive.

## Commands (run from `frontend/`)
```bash
npm run lint        # eslint .
npm run typecheck   # tsc -p tsconfig.json --noEmit
npm run build       # vite build (rolldown)
# jest is configured (jest.config.js) — run if tests touch changed areas
```

## Accessibility (target AA)
- Keyboard reachable + visible focus on every interactive element
- Sufficient color contrast in light AND dark (token-driven)
- Labels/roles for inputs, dialogs, menus (Radix supplies most — verify custom)
- No `aria-hidden` on focusable content; no positive tabindex

## Responsive
- Verify 360 / 768 / 1024 / 1440 px — no overflow, no broken grid

## Visual / regression
- Compare against sibling components for consistency
- Use the `verify` or `run` skill to launch the app and observe real behavior

## Output (structured)
```
qa:
  lint:       pass|fail (+ findings)
  typecheck:  pass|fail
  build:      pass|fail
  a11y:       [issues]
  responsive: [issues]
verdict: ship | block
```

## Exit criteria
All gates pass; `verdict: ship`. Anything else → back to the owning role.
