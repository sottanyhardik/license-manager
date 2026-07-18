# UI Modernization — License Manager

**Goal:** Transform this enterprise React app into a production-quality SaaS product
comparable to Linear, Stripe Dashboard, Vercel, GitHub, Notion, and OpenAI.

**Stack target:** shadcn/ui · Radix UI · TanStack Query · Tailwind v4 · cmdk ·
Lucide React · Framer Motion · Sonner · Recharts · React Hook Form · Zod

---

## How to use these docs

| File | Purpose |
|------|---------|
| `ROUTES.md` | Route ownership and progress tracker — **claim a route here** |
| `DESIGN_SYSTEM.md` | Tokens, typography, spacing, colour decisions |
| `COMPONENT_STATUS.md` | Shared component modernization status |
| `USER_FEEDBACK.md` | User-requested improvements and feedback |
| `DECISIONS.md` | Architectural decisions and rationale |
| `REGRESSIONS.md` | Known regressions (must be empty before release) |
| `BACKLOG.md` | Improvements deferred but not forgotten |
| `CHANGELOG.md` | Completed work with files changed |
| `SESSION_LOG.md` | Per-session summaries |

---

## Session startup checklist

```
1. Read ROUTES.md
2. Read REGRESSIONS.md  (fix anything blocking first)
3. Read USER_FEEDBACK.md (address P0 items first)
4. Claim ONE route (change TODO → IN_PROGRESS, add your session ID)
5. Work on that route only
6. Run lint + typecheck + build before committing
7. Update CHANGELOG.md, COMPONENT_STATUS.md, ROUTES.md
8. Ask user for review before freezing
```

---

## Route lifecycle

```
TODO → IN_PROGRESS → READY_FOR_REVIEW → (user approval) → FROZEN
                                              ↓
                                       USER_FEEDBACK → IN_PROGRESS
FROZEN → NEEDS_REVIEW → IN_PROGRESS (if regression or explicit request only)
```

---

## Rules

- **One route per session.** Never work on multiple routes simultaneously.
- **Locked routes are locked.** If `IN_PROGRESS`, skip it.
- **Preserve all business logic.** Never change APIs, permissions, validation, or workflows.
- **Append-only docs.** Never overwrite history in CHANGELOG, SESSION_LOG, DECISIONS.
- **Prefer deletion.** Remove custom UI code when a mature library covers it.
- **Maximum 3 iterations** per route before declaring READY_FOR_REVIEW.
- **Always build-verify.** `npm run typecheck && npm run build` must pass before updating route status.

---

## Preferred libraries (already installed where noted)

| Library | Status | Use for |
|---------|--------|---------|
| shadcn/ui | ✅ Installed | All UI primitives |
| @radix-ui/* | ✅ Installed | Accessible headless primitives |
| @tanstack/react-query v5 | ✅ Installed | Server state |
| cmdk v1 | ✅ Installed | Command palette (migrated) |
| framer-motion | ✅ Installed | Animations |
| sonner | ✅ Installed | Toast notifications |
| lucide-react | ✅ Installed | Icons |
| recharts | ✅ Installed | Charts (added Session 1) |
| react-datepicker | ✅ Installed | Date pickers |
| @tanstack/react-table | ❌ Not installed | Advanced tables (backlog) |
| react-hook-form | ❌ Not installed | Form state (backlog) |
| zod | ❌ Not installed | Schema validation (backlog) |
| react-hotkeys-hook | ❌ Not installed | Keyboard shortcuts (backlog) |

---

## Project context

- **Frontend:** React 19 · TypeScript 5.9 · Tailwind v4 · Vite (rolldown)
- **Domain:** Trade compliance — EPCG licenses, BOE, allotments, SION norms
- **Users:** Enterprise operators doing high-stakes, repetitive back-office tasks
- **Auth:** JWT via Django REST Framework backend on port 8000
- **Dev server:** Vite on port 5173
