# Phase 3 — Migration Plan

**Status:** Operational playbook. Drives Phase 4 execution.
**Prerequisite:** `PHASE_2_DESIGN.md` reviewed and approved.

This is a sequence of small, independently shippable phases. Each one is its own commit (or small PR) with explicit validation and rollback. No phase blocks production. Phases are grouped by risk so you can decide where to pause.

---

## 0. Conventions

Every phase below has the same shape:

- **What** — the changes in that phase
- **Why** — design rationale (deeper detail lives in Phase 2 doc)
- **Risk** — `LOW` / `MEDIUM` / `HIGH`
- **Effort** — rough estimate in implementer-hours
- **Depends on** — phases that must land first
- **Validation** — commands or checks that prove it worked
- **Rollback** — how to undo

**Universal preflight (every phase):**

```bash
# Backend
cd backend
python manage.py check                                # no system errors
python manage.py makemigrations --check --dry-run     # no unintended schema drift
pytest -q                                             # all tests pass
ruff check .                                          # lint clean (once ruff is wired)

# Frontend
cd frontend
npm run build                                         # production build succeeds
npm run lint                                          # lint clean
```

If any preflight check fails, the phase does not ship.

---

## Risk Tier 1 — LOW RISK (mechanical, no behaviour change)

### Phase 3.1 — URL namespacing  ⚠ RECLASSIFIED MEDIUM

- **What:** Add `app_name = "<app>"` to every `<app>/urls.py`. Add `namespace=` to every include in `lmanagement/urls.py`. Update all 78 `reverse()` callsites — including `license/models.py:166` (`get_absolute_url`), `bill_of_entry/models.py:131`, `core/models.py:139,241,283`, `allotment/models.py:317`, the entire `tests/test_api_*.py` and `tests/test_all_conditions.py` suite, and template `{% url %}` tags. Public paths unchanged.
- **Why:** Disambiguate `reverse()` calls; prepares for app moves; documented in `PHASE_2_DESIGN.md` §4.
- **Risk:** ~~LOW~~ **MEDIUM** — every `reverse()` call must update from `"license-list"` to `"license:license-list"`. Discovered during Phase 4 prep: 78 callsites including production `get_absolute_url()` methods.
- **Effort:** ~~1h~~ **4-6h** — most of the time is auditing callsites, not the urls.py edits.
- **Depends on:** none
- **Validation:**
  - `python manage.py check` clean
  - All tests pass (they will fail loudly if any reverse() is missed — good)
  - Manual: log in, hit one endpoint per app, all 200
  - Grep for unnamespaced reverse(): `grep -rn "reverse(['\"][a-z-]\+-list\|reverse(['\"]api-" backend --include='*.py'` should match nothing outside `migrations/`
- **Rollback:** revert the commit. The reverse() callsite updates are mechanical and atomic in one PR.
- **Note:** Originally tagged LOW. Re-tagged after callsite audit.

### Phase 3.2 — Split settings.py  (DEFERRED — see note)

**Note:** The current `lmanagement/settings.py` is already env-var driven for DEBUG, DATABASES, ALLOWED_HOSTS, CORS_*, SECURE_*, REDIS_URL, etc. A split into base/dev/prod files would mostly be cosmetic until there's a concrete divergence (e.g., a third-party app installed only in dev). Recommend deferring until the `apps/` move (Phase 3.7), at which point a `test.py` settings file becomes useful for the test suite (disable signals, fast password hashing).

Below is the original spec, kept for reference.

### Phase 3.2a — Original spec (deferred)

- **What:** Create `lmanagement/settings/{__init__.py, base.py, dev.py, prod.py, test.py}`. Move existing `settings.py` contents into `base.py`. `__init__.py` reads `DJANGO_ENV` (default `dev`) and re-exports from the matching module.
- **Why:** Lets prod lock down `DEBUG`, `ALLOWED_HOSTS`, `SECURE_*` cookies independently. Test settings can disable signals safely.
- **Risk:** LOW
- **Effort:** 2h
- **Depends on:** none
- **Validation:**
  - `DJANGO_ENV=dev python manage.py check` → clean
  - `DJANGO_ENV=prod python manage.py check --deploy` → fewer warnings than before
  - Test suite uses `DJANGO_ENV=test`; passes
- **Rollback:** revert. The old `settings.py` is still in git history.
- **Deploy note:** `auto-deploy.sh` and supervisord configs must export `DJANGO_ENV=prod`. Include in the same PR.

### Phase 3.3 — Strip `print()` and `console.log`

- **What:** Replace 176 backend `print()` statements with `logging.info()` / `logging.warning()`. Strip 50 frontend `console.log` (or move to `console.debug` then strip via Vite plugin in prod).
- **Why:** Production log noise; debug output leaks; tiny perf wins.
- **Risk:** LOW
- **Effort:** 3h (semi-automated with `ruff`/`eslint --fix`)
- **Depends on:** none
- **Validation:**
  - `grep -rn "print(" backend --include='*.py' | grep -v migrations | wc -l` ≈ 0
  - `grep -rn "console.log" frontend/src | wc -l` = 0
  - App still works
- **Rollback:** revert. No behaviour relies on prints.

### Phase 3.4 — Frontend: extract `routes.jsx`, dedupe role constants

- **What:**
  - Create `frontend/src/app/routes.jsx`. Move the 340-LOC route table out of `App.jsx`. `App.jsx` becomes the providers + `<RouterProvider>` shell.
  - Move `utils/roleConstants.js` → `shared/auth/roleConstants.js` (intermediate path; final structure comes later).
  - Delete the inline role-name strings from `App.jsx`; import from `roleConstants.js`.
- **Why:** Modularity; eliminates duplicated role strings.
- **Risk:** LOW
- **Effort:** 2h
- **Depends on:** none
- **Validation:**
  - `npm run build` clean
  - Login, every protected route loads / 403s correctly
  - Grep: no remaining inline role string literals in `App.jsx`
- **Rollback:** revert

### Phase 3.5 — Backend: scripts consolidation, mgmt commands cleanup

- **What:**
  - Audit `core/management/commands/rqworker.py` — if RQ unused (Celery is the queue), delete.
  - Move `backend/data_script/fetch_ownership.py` → `backend/apps/license/services/dgft_ownership.py`. Update single import in `update_license_ownership.py`. (Done as `license/services/dgft_ownership.py` even before the apps/ move; that path becomes `apps/license/services/dgft_ownership.py` in Phase 3.7.)
  - Delete `backend/data_script/__init__.py` and the now-empty `data_script/` dir.
- **Why:** Eliminates a top-level Python package that shouldn't exist.
- **Risk:** LOW
- **Effort:** 1h
- **Depends on:** none
- **Validation:**
  - `python -m backend.license.management.commands.update_license_ownership --help` runs
  - Smoke test the command on dev DB
- **Rollback:** revert

### Phase 3.6 — Backend: consolidate 6 PDF generators in `license/views/ledger.py`

- **What:** Extract the shared table/page/style logic into `backend/shared/pdf/builders.py`. Each of the 6 PDF endpoints becomes a thin wrapper that calls the builder with its specific columns and headers.
- **Why:** `ledger.py` is 2,918 LOC, half of which is repeated PDF scaffolding. This is the clearest internal duplication in the codebase.
- **Risk:** LOW (visual diff possible — keep golden PDFs to compare bytes before/after)
- **Effort:** 6h
- **Depends on:** none
- **Validation:**
  - For each of the 6 endpoints: generate a PDF before refactor (save bytes), generate after, compare. Allow for whitespace-only differences if cleanup changed any spacing.
  - `npm run build` and manual click-test each export.
- **Rollback:** revert. Golden PDFs let us spot regressions instantly.

---

## Risk Tier 2 — MEDIUM RISK (structural, requires careful validation)

### Phase 3.7 — Backend: app moves into `apps/`

- **What:**
  - Create `backend/apps/` directory.
  - Move each app: `git mv <app>/ apps/<app>/`. Order: tasks → accounts → core → trade → bill_of_entry → allotment → license. (Smallest first to validate the pattern.)
  - In each `apps/<app>/apps.py`, set:
    ```python
    class FooConfig(AppConfig):
        name = "apps.foo"
        label = "foo"   # MUST equal the previous app_label
    ```
  - Update `INSTALLED_APPS` to use the new dotted path.
  - Update every Python import: `from license.models` → `from apps.license.models`. Use a single `sed` pass, then verify with `python -c "import apps.license"` for each app.
  - Update `lmanagement/urls.py` includes.
- **Why:** §1 of Phase 2 doc. Standardizes package layout, sets up feature-folder thinking.
- **Risk:** MEDIUM — many imports change; one missed reference breaks startup.
- **Effort:** 1 day (the largest mechanical change in the project)
- **Depends on:** 3.1, 3.2 (URL namespace + settings split make the import surgery less risky)
- **Validation:**
  - `python manage.py check` clean for each app moved individually
  - `python manage.py makemigrations --check --dry-run` → no migrations (PROOF that app_label preserved)
  - `python manage.py migrate --plan` shows no pending migrations
  - Full pytest suite passes
  - Manual: hit one endpoint per app
  - On staging: full deploy, smoke test
- **Rollback:** Each app move is its own commit. Revert in reverse order. If a partial state needs to ship, the old import paths can stay as compat re-exports for one release:
  ```python
  # license/__init__.py  (temporary compat shim)
  from apps.license import *  # noqa
  ```
- **Critical pitfalls:**
  - `AUTH_USER_MODEL = "accounts.User"` — references app_label, not module path. Don't change.
  - String FK targets like `"core.CompanyModel"` — same. Don't change.
  - Migration `dependencies` lists — reference app_label. Don't change.
  - Celery task imports — must update.
  - Templates: `{% load app_tags %}` resolves via app_label; unchanged.

### Phase 3.8 — Backend: signal sender strings → direct imports

- **What:** In `apps/license/signals.py:332-379`, replace string sender refs with direct imports:
  ```python
  # before
  @receiver(post_save, sender="allotment.AllotmentItems")

  # after
  from apps.allotment.models import AllotmentItems
  @receiver(post_save, sender=AllotmentItems)
  ```
- **Why:** Eliminates the silent-failure rename risk identified in Phase 1 risk register #4.
- **Risk:** MEDIUM — must verify signals actually fire after change.
- **Effort:** 1h
- **Depends on:** 3.7 (apps/ move complete)
- **Validation:**
  - New test: `tests/license/test_signals.py`. For each signal, save an instance of the sender model in `pytest.mark.django_db`, assert the receiver ran (via `mock.patch` or a side-effect check on the license).
  - Run the test before and after the change. Before should pass too (existing behaviour); after should still pass with direct imports.
- **Rollback:** revert; string senders still work.

### Phase 3.9 — Backend: kill N+1s in license serializers

- **What:**
  - `apps/license/serializers/license.py` (formerly `serializers.py:157-187`): drop the `SerializerMethodField` for `items_detail`. Move to view-level `prefetch_related("items_detail__sion_norm_class")`.
  - Replace `.filter().exists()` boolean fields (`get_has_tl`, `get_has_copy`) with `Case/When` annotations on the queryset.
  - Replace `instance.license_documents.exists()` + `.all()[:1]` with single prefetched lookup.
- **Why:** Risk register #8, #9. Eliminates dozens of queries per list response.
- **Risk:** MEDIUM — serializer changes can subtly change payload shape.
- **Effort:** 4h
- **Depends on:** 3.7
- **Validation:**
  - `pytest tests/license/` covers list and detail responses
  - Manual: hit `/api/licenses/` and `/api/licenses/<id>/`, payload shape unchanged from main branch
  - Compare query counts: run with `django_assert_num_queries` in a test
- **Rollback:** revert. The materialized view layer hides any temporary slowdown.

### Phase 3.10 — Backend: service layer for `trade`

- **What:** Follow the template in `PHASE_2_DESIGN.md` §6. Extract `trade/views.py` business logic into `apps/trade/services/`. Pilot for the pattern.
- **Why:** Smallest app — proves the pattern with low blast radius before applying elsewhere.
- **Risk:** MEDIUM
- **Effort:** 4h
- **Depends on:** 3.7
- **Validation:**
  - All existing trade tests pass
  - New service-level unit tests (one per service function)
  - Hit every trade endpoint manually; payloads identical
- **Rollback:** revert

### Phase 3.11 — Backend: service layer for `tasks`, `bill_of_entry`, `allotment`

- **What:** Same as 3.10 for the remaining mid-sized apps. One PR per app.
- **Risk:** MEDIUM (per app)
- **Effort:** 4h each
- **Depends on:** 3.10 (pattern validated)
- **Validation:** same as 3.10, per app

### Phase 3.12 — Backend: service layer for `license` (the big one)

- **What:** Extract license-app business logic into `apps/license/services/`. Existing `services/` already has `balance_calculator`, `condition_pool`, etc. — extend with `license_crud.py`, `transfer.py`, `purchase.py`, `incentive.py`. Move logic out of the 2,931-LOC views file.
- **Why:** The largest viewset file in the project. Reduces blast radius for every future change.
- **Risk:** MEDIUM-HIGH (lots of surface area; this is the most-touched file in production)
- **Effort:** 1-2 days
- **Depends on:** 3.10, 3.11 (pattern proven)
- **Validation:**
  - All license tests pass (`test_balance_calculator.py`, `test_signals.py`, integration tests)
  - Hit every endpoint in license manually
  - Staging deploy and smoke test before prod
- **Rollback:** revert; this PR should be split into logical sub-PRs (license CRUD, transfers, purchases, reports) so rollback can be partial

### Phase 3.13 — Frontend: TanStack Query setup + first feature migration

- **What:**
  - `npm install @tanstack/react-query @tanstack/react-query-devtools`
  - Add `shared/api/queryClient.js`, wrap app in `<QueryClientProvider>`.
  - Migrate ONE feature (`tasks` — simplest) to TanStack Query. Delete the old fetch hooks just for that feature.
- **Why:** Proves the data-fetching redesign on a small surface before applying to license, etc.
- **Risk:** MEDIUM
- **Effort:** 4h
- **Depends on:** 3.4
- **Validation:**
  - Tasks list/detail/CRUD all work
  - Network tab shows cached responses (no refetch on revisit)
  - All other features untouched
- **Rollback:** revert; QueryClientProvider is additive and can stay even if features don't use it yet

### Phase 3.14 — Frontend: migrate remaining features to TanStack Query

- **What:** One feature per PR — allotment, bill_of_entry, trade, masters, reports, license, admin.
- **Risk:** MEDIUM (per feature)
- **Effort:** 4-6h per feature
- **Depends on:** 3.13
- **Validation:** per-feature smoke test; old fetch hooks deleted after last consumer migrates

### Phase 3.15 — Backend: long-running endpoints to Celery

- **What:** For each of 5 sync PDF/Excel endpoints (see Phase 1 §5), add an `*-async/` variant:
  - Trade bill-of-supply, trade purchase-invoice
  - 4 report endpoints (inventory-balance, expiring, active, item-pivot, item-report)
  - Allotment generate-pdf
  - License merged-documents
- Pattern:
  ```
  POST /api/licenses/<id>/export-pdf-async/
       → {task_id: "..."}
  GET  /api/jobs/<task_id>/
       → {status: "pending|done|failed", result_url?: "..."}
  ```
- Existing sync endpoints kept for back-compat; frontend can migrate incrementally.
- **Why:** Worker thread time. UX (no 30s spinners).
- **Risk:** MEDIUM
- **Effort:** 2 days (Celery task + signed URL + job-status endpoint + frontend hook)
- **Depends on:** 3.7
- **Validation:**
  - Submit async PDF; poll status; download PDF; verify identical bytes to sync version
  - Worker pool not saturated under concurrent load
- **Rollback:** revert; old sync endpoints still work

---

## Risk Tier 3 — HIGH RISK (data-integrity; staged rollout required)

### Phase 3.16 — Signal recompute → Celery (dual-write phase)

- **What:** Add `recompute_license_flags` Celery task. In `apps/license/signals.py`, the cross-app signal receivers now do BOTH the existing sync work AND `recompute_license_flags.delay(license_id)`. Compare results in logs.
- **Why:** Validate the async path produces identical balance values before switching off the sync path.
- **Risk:** HIGH (potential for divergence; log carefully)
- **Effort:** 1 day implementation + 1 week observation
- **Depends on:** 3.7, 3.8, 3.12
- **Validation:**
  - For each signal fire, log `{license_id, source, sync_balance_after, async_balance_after}` (via Celery task hook).
  - Daily query: `SELECT count(*) FROM signal_dual_write_log WHERE sync != async`. Should be 0 every day for 7 days.
  - If any divergence: stop, investigate, do not advance.
- **Rollback:** revert the `delay()` calls; sync path was untouched

### Phase 3.17 — Signal recompute → Celery (switch flag)

- **What:** Settings flag `ASYNC_LICENSE_FLAG_RECALC = True`. Receivers now only enqueue, no sync recompute.
- **Why:** Worker thread time savings on hot writes (BOE imports, trade saves, allotment writes).
- **Risk:** HIGH
- **Effort:** 1h to flip flag + 1 day monitoring
- **Depends on:** 3.16 with 7 clean days
- **Validation:**
  - Worker thread time drops on writes (measure via APM or `time.time()` logs)
  - Dashboard balance numbers continue to match the source-of-truth recompute
  - No spike in 500s
- **Rollback:** flag off; immediately back to sync path

### Phase 3.18 — Signal recompute → Celery (remove sync code)

- **What:** Delete the old sync recompute code paths from `signals.py`. Keep only the Celery dispatcher.
- **Risk:** MEDIUM (just code removal at this point; flag-off rollback no longer possible)
- **Effort:** 1h
- **Depends on:** 3.17 with 1 week clean
- **Validation:** same as 3.17
- **Rollback:** revert the deletion commit; sync code returns

---

## Risk Tier 4 — Infrastructure & DX (parallelizable with above)

### Phase 3.19 — Add CI

- **What:** GitHub Actions (or chosen CI). Three jobs:
  1. Backend: `pytest`, `manage.py makemigrations --check --dry-run`, `ruff check`
  2. Frontend: `npm run build`, `npm run lint`, `vitest run` (once tests exist)
  3. Security: `pip-audit`, `npm audit --production`
- Block merge if any job fails.
- **Risk:** LOW (additive)
- **Effort:** 1 day
- **Depends on:** none — can run in parallel with any phase
- **Validation:** push a known-failing commit, confirm CI blocks it

### Phase 3.20 — Add `/api/health/` endpoint + deploy check

- **What:** Add `GET /api/health/` returning `{status, db, redis, celery}` — IsAdminUser or no auth (low-data). Wire `auto-deploy.sh` to curl it after each server's supervisor restart; fail the deploy if non-200.
- **Risk:** LOW
- **Effort:** 2h
- **Depends on:** none
- **Validation:** intentionally break Redis on a staging server, deploy → script aborts

### Phase 3.21 — Vitest scaffold + first 5 frontend tests

- **What:** Install Vitest, wire `npm run test`. Write tests for the 5 most-critical hooks: `useAuth`, `useFileUpload`, the new license query hook, `useDebounce`, `useConfirmDialog`.
- **Risk:** LOW
- **Effort:** 1 day
- **Depends on:** 3.13 (query hooks exist to test)

### Phase 3.22 — Documentation consolidation

- **What:**
  - Move all 26 remaining root markdown files into `docs/` with subfolders (`docs/architecture/`, `docs/guides/`, `docs/operations/`).
  - Create `docs/README.md` index.
  - Consolidate overlapping pairs: `RBAC_DOCUMENTATION.md` + `RBAC_SETUP_INSTRUCTIONS.md` → one; `RATE_LIMITING_GUIDE.md` + `_IMPLEMENTATION.md` → one; etc.
- **Risk:** LOW
- **Effort:** 2h
- **Depends on:** none
- **Validation:** `ls *.md` at root only shows `README.md` and `LICENSE` (if any)

### Phase 3.23 — Move `DFIA_COPY/` to object storage

- **What:** Decide on storage (S3/Spaces/GCS). Upload existing 210 PDFs. Update any code that reads from local disk to read via signed URL. Add to `.gitignore`. Remove from git history (separate operation — `git filter-branch` or `git lfs migrate`).
- **Risk:** MEDIUM (history rewrite affects all clones)
- **Effort:** 1 day
- **Depends on:** infra decision

---

## Phase Sequencing & Dependency Graph

```
3.1 namespacing ──┐
3.2 settings split ──┼── 3.7 apps/ move ── 3.8 signal imports ─┐
3.3 print cleanup ──┘                                          ├── 3.10 trade service ── 3.11 mid services ── 3.12 license service ──┐
3.4 routes extract ───────── 3.13 query setup ── 3.14 query migrations                                                                ├── 3.16 dual-write ── 3.17 flag on ── 3.18 sync removed
3.5 data_script move ──────────────────────────────────────┐                                                                          │
3.6 pdf consolidation ─────────────────────────────────────┴── 3.9 N+1 fixes ─────────────────────────────────────────────────────────┘── 3.15 long-running async

3.19 CI ───── parallel to anything
3.20 health endpoint ─── 3.7+
3.21 vitest ─── 3.13+
3.22 docs ── parallel
3.23 DFIA_COPY ── parallel (separate ops decision)
```

---

## Suggested Schedule (calendar-time)

Treating this as a single implementer's calendar, with realistic context-switching:

| Week | Phases shipped | Cumulative state |
|---|---|---|
| 1 | 3.1, 3.2, 3.3, 3.4, 3.5 | All Tier-1 lows done; codebase materially cleaner; zero behaviour change |
| 2 | 3.6, 3.19, 3.20 | PDF consolidation, CI live, deploy has health gate |
| 3 | 3.7 (apps/ move) | The big mechanical change; everything still works |
| 4 | 3.8, 3.9, 3.10 | Direct signal imports, N+1 fixed, trade service pattern shipped |
| 5 | 3.11 (×3) | All mid-app services done |
| 6 | 3.12 | License service refactor |
| 7 | 3.13, 3.14 (start) | TanStack Query rolling out feature by feature |
| 8 | 3.14 (finish), 3.15 | Async PDF endpoints live |
| 9 | 3.16 | Dual-write phase begins (1 week observation) |
| 10 | 3.17, 3.18 | Async signals live; sync path removed |
| 11 | 3.21, 3.22, 3.23 | Tests + docs + storage cleanup |

**11 weeks total** for a single implementer working solo. Parallelizable with 2 implementers to ~6 weeks.

---

## What to do BEFORE Phase 3.1

The Phase 0 cleanup (already done in this session) and Stage A hotfixes (already done) are prerequisites. Verify in `git status` that:

- Hardcoded password is removed from `auto-deploy.sh`
- `ThrottleHealthView.permission_classes = [IsAdminUser]`
- `app_tags.py` imports from `allotment.models`, not `license.models`
- Stale docs / dead refactor artifacts removed
- `check_user_roles.py` is a proper management command

If any of these is missing, fix before proceeding to 3.1.
