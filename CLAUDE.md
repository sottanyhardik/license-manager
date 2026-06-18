# CLAUDE.md — License Manager

> **This file is the operating system for AI work in this repo.** It is loaded first,
> every session. Read it, then load the specific `.claude/` resources it routes you to
> **before** writing code. The goal: minimize repeated context, encode conventions once,
> and make every session produce consistent, convention-following changes.

---

## 1. Project Overview

**License Manager** is a web-based trade-compliance system for Indian exporters. It tracks
import entitlements under DGFT schemes — primarily **DFIA** (Duty Free Import Authorisation)
and incentive licenses (RODTEP, ROSTL, MEIS) — across their full lifecycle: issuance →
allotment → bill-of-entry clearance → transfer → trade invoicing → audit-ready ledgers.

- **Business goal**: one source of truth for license balances, debits, and transfers so
  license owners, importers, logistics, and accounts reconcile against the same ledger.
- **Tech stack** (verify against `package.json` / `requirements.txt` before assuming):

  | Layer | Technology |
  |---|---|
  | Frontend | React 19.2, TypeScript 5.9 (strict), Tailwind v4, shadcn/ui (new-york/slate), Radix, Framer Motion, react-router-dom v7, cmdk, sonner, axios |
  | Build | Vite (`rolldown-vite`) + `@vitejs/plugin-react-oxc` |
  | Backend | Django 6.0.4 + Django REST Framework 3.17.1 |
  | Auth | SimpleJWT 5.5.1 (refresh rotation + blacklist) |
  | Database | PostgreSQL via psycopg 3 |
  | Async | Celery 5.6.3 + Redis |
  | Docs/PDF/OCR | ReportLab, PyPDF, pdf2image, pytesseract, docxtpl, OpenPyXL |

- **Architecture summary**: React SPA ⇄ DRF `/api/*` (JWT). Backend split into 7 Django apps
  (`accounts core license bill_of_entry allotment trade tasks`). Most ViewSets extend
  `MasterViewSet` (`backend/apps/core/views/master_view.py:69`); all models inherit
  `AuditModel` (`backend/apps/core/models.py:40`). Balances are **materialised** (updated by
  signals, not computed on read). Heavy ledger uploads run on Celery. Deep dives:
  `docs/02-architecture.md` and `.claude/context/architecture.md`.

---

## 2. AI Working Principles

Before and during any change, Claude must:

- **Read existing code before editing.** Match the surrounding file's patterns, naming, and
  comment density.
- **Prefer modifying existing files** over creating new ones. Reuse existing utilities,
  components (`@/components/ui/*`), and base classes (`MasterViewSet`) before writing new code.
- **Follow existing patterns** even when a different one is "nicer." Consistency wins.
- **Keep solutions simple.** No speculative abstraction, no premature generalization.
- **Never generate dead code** — no unused imports, vars, components, or commented-out blocks.
- **Never invent APIs, endpoints, fields, or env vars.** Grep first; cite `file:line`.
- **Preserve business logic.** UI/UX and refactor work must not change behavior, API calls,
  auth, or data flow. Flag any behavior change explicitly for human review.
- **Ask for clarification** when requirements are ambiguous rather than guessing.

---

## 3. Always Use `.claude` (routing table)

`.claude/` is the reusable knowledge base. **Load the matching resources before starting.**
Each file is small and single-purpose; this table tells you *when* to read *which*.

| Task type | Read rules | Load context | Use prompt | Use template | Finish with checklist |
|---|---|---|---|---|---|
| New frontend feature | `rules/react.md`, `rules/typescript.md`, `rules/frontend-ui.md` | `context/architecture.md`, `context/api.md` | `prompts/feature.md` | `templates/component.md`, `templates/service.md` | `checklists/pr.md`, `checklists/testing.md` |
| New backend feature / endpoint | `rules/backend.md`, `rules/database.md`, `rules/security.md` | `context/api.md`, `context/business-domain.md`, `context/database.md` | `prompts/feature.md` | `templates/viewset.md`, `templates/test.md` | `checklists/pr.md`, `checklists/security.md` |
| Bug fix | rule(s) for the touched layer | relevant `context/*` | `prompts/bugfix.md` | `templates/test.md` (regression) | `checklists/pr.md` |
| Refactor (no behavior change) | rule(s) for the touched layer + `.claude/rules.md` | relevant `context/*` | `prompts/refactor.md` | — | `checklists/pr.md` |
| DB migration / schema change | `rules/database.md`, `rules/backend.md` | `context/database.md` | `prompts/migration.md` | `templates/test.md` | `checklists/pr.md`, `checklists/security.md` |
| Release / deploy | — | `context/architecture.md` | — | — | `checklists/release.md` |

**Curated good examples** of the patterns above live in `.claude/examples/README.md`
(pointers to real files, e.g. the axios interceptor and a `MasterViewSet` subclass).

### Map of existing knowledge (don't duplicate — link to these)

| Need | Where it already lives |
|---|---|
| Reverse-engineered feature/spec docs | `docs/01-…` … `docs/10-rebuild-spec.md` |
| Architecture / RBAC / caching / materialized views | `docs/architecture/*` |
| API pagination, filtering, rate-limiting, testing, validation guides | `docs/guides/*` |
| Server setup, RBAC setup, FK migrations | `docs/operations/*` |
| Frontend stack rules + quality gates (Claude Graph) | `.claude/rules.md` |
| Frontend project notes / components / decision log | `.claude/memory/*` |
| Role briefs for focused agent passes (ui/ux/qa/perf/refactor) | `.claude/graph/*` |

---

## 4. Development Commands

> Run frontend commands from `frontend/`. Run backend commands from `backend/` with
> `DJANGO_SETTINGS_MODULE=lmanagement.settings`.

### Frontend (`cd frontend`)

| Action | Command |
|---|---|
| Install | `npm install` |
| Dev server | `npm run dev` |
| Build | `npm run build` |
| Lint | `npm run lint` |
| Typecheck | `npm run typecheck` |
| Preview build | `npm run preview` |
| Format | (Prettier not configured — match existing style; ESLint enforces) |

### Backend (`cd backend`)

| Action | Command |
|---|---|
| Install | `pip install -r requirements.txt` |
| Migrate | `python manage.py migrate` |
| Run dev | `python manage.py runserver` |
| Collect static | `python manage.py collectstatic` |
| Celery worker | `celery -A lmanagement worker -l info` |
| Test (all) | `pytest` (config: `backend/pytest.ini`) |
| Test (fast/api/unit) | `../run-tests.sh --fast` · `--api` · `--unit` · `--coverage` |

The **quality gate** (must pass before "done") matches `.claude/rules.md`:
`npm run lint` → `npm run typecheck` → `npm run build` for any frontend change.

---

## 5. Coding Standards

- **Naming**: React components `PascalCase`; hooks `useX`; TS types `PascalCase`; vars/fns
  `camelCase`. Python modules/functions `snake_case`; Django models follow the codebase's
  existing convention (e.g. `LicenseDetailsModel`); constants `UPPER_SNAKE`.
- **Import order (frontend)**: external packages → `@/*` aliased internal → relative →
  styles. Prefer `import type { … }` for type-only imports.
- **Folder organization (frontend `src/`)**: `api/ components/ components/ui/ context/ hooks/
  layout/ lib/ pages/ routes/ services/ styles/ theme/ types/ utils/`. UI primitives only in
  `components/ui/`. **Backend**: feature code lives inside the owning app
  (`apps/<app>/{models,serializers,views,urls}.py`); shared base classes in `apps/core/`.
- **Documentation**: docstrings on non-trivial Python functions; brief comments only where
  intent isn't obvious from the code. Don't narrate the obvious.
- **Error handling (frontend)**: API errors flow through the axios interceptors
  (`frontend/src/api/axios.js`) — don't re-implement 401/403/5xx handling per call. Surface
  user-facing errors via `sonner` toasts.
- **Error handling (backend)**: raise DRF exceptions / return proper status codes; never
  swallow exceptions silently. Validate in serializers.
- **Logging**: backend uses Django logging + the `ActivityLog` audit middleware (every HTTP
  request is logged). Don't add `print`/`console.log` to committed code.
- **Formatting**: ESLint governs frontend; follow PEP 8 / existing style on the backend.

---

## 6. Architecture Principles

- **Separation of concerns**: serializers validate/shape, ViewSets orchestrate, models hold
  data + invariants, signals maintain materialised fields. Frontend: pages compose,
  `components/ui` are dumb primitives, `services`/`api` own data fetching.
- **Dependency direction**: apps depend on `core`, never the reverse. Frontend pages depend
  on `components`/`hooks`/`services`, never the reverse.
- **State management**: no global store (no Redux/Zustand). Local `useState`/`useCallback`;
  shared state only via `AuthContext`, `ThemeContext`, `ToastContext`.
- **Service layer**: all HTTP goes through the single axios instance (dedup GETs, JWT refresh
  queue). Backend business logic lives in models/services, not in views where avoidable.
- **API patterns**: ViewSets extend `MasterViewSet` for filtering/search/ordering, inline
  PATCH, bulk export, and `AuditModel` auto-population. See `.claude/rules/backend.md`.
- **Component composition**: reuse `@/components/ui/*` (Radix-backed) before building new;
  lazy-load pages via the existing retry wrapper.

---

## 7. Testing Philosophy

- **Unit tests** for business logic (balances, parsing, calculations).
- **Integration / API tests** for endpoints (`@pytest.mark.api`, `@pytest.mark.integration`).
- **Regression prevention**: every bug fix ships with a test that fails before the fix.
- **Edge cases**: zero/negative balances, frozen BOE rows, partial allotments, expired JWTs,
  permission boundaries per role.
- Markers available (`backend/pytest.ini`): `slow`, `integration`, `unit`, `api`, `database`.
  Details in `.claude/rules/testing.md` and `docs/guides/TESTING_GUIDE.md`.

---

## 8. Security Standards

- **Validation**: validate all input in DRF serializers and on the frontend form layer;
  sanitize any HTML with `dompurify`.
- **Authentication**: SimpleJWT access/refresh with rotation + blacklist; never store secrets
  in tokens. Refresh handled centrally in `frontend/src/api/axios.js`.
- **Authorization**: role-based access enforced via DRF permissions; frontend gates with
  `ProtectedRoute`. See `docs/architecture/RBAC_DOCUMENTATION.md`.
- **Secret management**: all secrets via env vars (`DJANGO_SECRET_KEY`, `DATABASE_URL`,
  `REDIS_URL`, …). Never hardcode or commit secrets; `.env*` stays untracked.
- **Dependency safety**: pin versions (already done); don't add deps without need. Note the
  open migration items: remove `bootstrap-icons`, consolidate `react-toastify` → `sonner`.
- **Audit**: `ActivityLogMiddleware` records every HTTP request — don't disable it.
- Full rules: `.claude/rules/security.md`, deep dive `docs/08-security.md`.

---

## 9. Performance Guidelines

- **Frontend**: lazy-load routes (existing retry wrapper), memoize only when profiling
  justifies it, keep bundles small (don't add heavy deps), keep DOM depth tight.
- **Backend**: avoid N+1 (`select_related`/`prefetch_related`); rely on materialised balance
  fields rather than recomputing; use composite indexes (see `docs/architecture/*`); offload
  heavy work (ledger uploads) to Celery; cache via `django-redis` where appropriate.
- **DB**: query through the ORM efficiently; review `docs/architecture/REDIS_CACHING_GUIDE.md`
  and `MATERIALIZED_VIEWS_GUIDE.md` before optimizing.

---

## 10. Documentation Rules

Every significant change updates the relevant docs in the same PR:

- **README** — if user-facing behavior changes.
- **`docs/` (numbered + subdirs)** — if architecture, features, API, DB, or business rules change.
- **`docs/04-api.md`** — if endpoints change.
- **`.claude/context/*`** — if project knowledge an AI needs changes.
- **`.claude/examples/*`** — when introducing a new reference-worthy pattern.

---

## 11. Maintaining `.claude` (living documentation)

When you introduce or change a pattern:

1. Add/update the matching rule in `.claude/rules/`.
2. Add an example pointer in `.claude/examples/README.md`.
3. Update the relevant `.claude/context/*` orientation file.
4. Add/refresh a reusable prompt in `.claude/prompts/` if the workflow changed.
5. Update `.claude/templates/` when boilerplate changes.
6. Log non-obvious decisions in `.claude/memory/decisions.md` (existing log).

Treat `.claude/` as **living** documentation. A pattern that isn't captured here will drift.

---

## 12. AI Output Style

- Think before coding; state tradeoffs briefly when a choice isn't obvious.
- Produce **minimal but complete** changes; prefer incremental edits to rewrites.
- Preserve project conventions; avoid creating unnecessary files.
- Reuse existing utilities and primitives wherever possible.
- Reference code as `file_path:line` so it's clickable.

---

## 13. Success Criteria

A successful change:

- Loaded the applicable `.claude/` rules/context **before** coding (Section 3 routing table).
- Follows existing patterns and reuses existing utilities/components.
- Passes the quality gate (`lint` → `typecheck` → `build` for frontend; `pytest` for backend).
- Preserves business logic and authorization behavior.
- Updates docs/`.claude/` when knowledge or patterns change.
- Reads consistently with code written in prior sessions.
