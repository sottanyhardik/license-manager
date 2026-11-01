# 14. Dependency and technology audit — License Manager V1

Audit date: 2026-11-01. Branch `version-v1`, HEAD `d78c8b1d`. Agent C (dependency and technology). Read-only: nothing was installed, upgraded, removed or pinned, and no requirements file, lock file, virtualenv or `node_modules` was changed.

Companion inventory: [inventories/dependency-inventory.md](inventories/dependency-inventory.md) (every declared package with installed version, purpose, usage count, status, risk, target and priority).

Finding IDs use the prefix `DEP-`. Evidence is cited with file paths and line numbers where a grep or read produced it.

---

## 1. Summary in plain English

The application is built on a current stack: Django 6.0, Django REST Framework 3.17, React 19, Vite (through a Rolldown fork), Tailwind v4, TypeScript 5.9, TanStack Query 5 and Playwright. Most declared packages are at or near their latest release.

The main problems are these:

1. **Security patches are behind on the core framework and several parsers.** Django is pinned to 6.0.4 while 6.0.9 is available. OSV lists 26 advisories against 6.0.4, fixed between 6.0.5 and 6.0.8. The same pin is in `master-data-service`. DRF 3.17.1 has 7 advisories, pypdf in the dev environment has 40, Pillow 12.2.0 has 85, and PyJWT (an undeclared transitive dependency) has 27.
2. **A calculation dependency is missing and the code hides the gap.** `scipy` is imported by `apps/core/scripts/calculation.py` but is not declared in `requirements.txt` and is not installed in `.venv`. The only caller wraps the import in `try/except Exception` and falls back to `None` (`apps/license/models/core.py:683-686`). Whether the fallback changes any stored or displayed balance is not verified here and must be checked with the financial audit (Agent B).
3. **The frontend has a critical-rated advisory in a declared but unused package.** `dompurify` is declared, reported as critical by npm audit, and is not imported by any source file. `vitest` 3.2.6 is in the critical advisory range for the test runner that CI runs.
4. **Several declared packages are not used.** Eight runtime packages in `frontend/package.json` have no source import, including `exceljs` (stale since 2023 and carrying a moderate advisory chain), `jspdf` and `recharts`. Three backend test packages (`faker`, `flake8`, `pytest-xdist`) have no use in the repository.
5. **Some imports are not declared at all.** Six PyPI packages are imported but absent from every requirements file: `scipy`, `beautifulsoup4`, `brotli`, `psycopg2`, `rq` and `django-rq`. Two more are imported directly but come only transitively (`python-dateutil`, `python-docx`).
6. **Two settings or pins are stale.** `STATICFILES_STORAGE` is a removed Django setting, so it is silently ignored (WhiteNoise compressed storage is not active). The `setuptools<81` pin is justified by a `docxcompose` dependency that the installed `docxtpl` does not need, and the `.venv` already violates the pin (84.0.0).
7. **The toolchain has end-of-life or blocked upgrades.** ESLint 9 is out of support and `eslint-plugin-react` blocks ESLint 10. Vite is an npm alias to a Rolldown fork, and its declared plugin peer (`vite ^6.3.0`) does not match. TypeScript 7 is blocked by `typescript-eslint`, which supports TypeScript below 6.1. PostgreSQL 14, the minimum that Django 6.0 accepts, reaches end of life on 2026-11-12, eleven days after this audit.
8. **Reproducibility is weak on the backend.** There is no lock file or hash set. The venv differs from `requirements.txt` in several places, and `backend/requirements_python314.txt` is a stale, contradictory snapshot that CI does not read.

Nothing in this audit proves that an advisory is exploitable in this deployment. Applicability was judged from code search only. Section 9 lists the limits.

---

## 2. Priority scale

The repository roadmap uses only P0, P1 and P2 (`docs/v1/08-implementation/implementation-roadmap.md`). P3 to P5 are defined here and should be ratified by the lead.

| Priority | Meaning used in this report |
|---|---|
| P0 | Critical security or data correctness. Act before the next release. |
| P1 | High security or availability exposure on a live or CI path. Next release cycle. |
| P2 | Medium exposure, broken or unverified runtime path, or a blocked upgrade. Within the current milestone. |
| P3 | Low exposure or maintenance risk: dead code, undeclared imports, system-level gaps. Scheduled. |
| P4 | Hygiene and major-version upgrades without known exposure. |
| P5 | Patch drift. Take opportunistically. |

---

## 3. Findings register

Priority, area, finding and recommended action. Evidence for each is in the inventory section named in the last column.

| ID | Priority | Area | Finding | Recommendation | Inventory |
|---|---|---|---|---|---|
| DEP-001 | P0 | Backend | Django 6.0.4 (pinned in `requirements.txt` and `master-data-service/requirements.txt`) has 26 OSV advisories, fixed in 6.0.5 to 6.0.8. Latest 6.0.9 (6.0 cycle EOL 2027-04-30). Some advisories concern cache and cookie disclosure. The app uses the Django cache API (`apps/core/cache_utils.py`, `cached_views.py`, `throttling.py`); no per-view cache decorator or cache middleware was found, so applicability is UNVERIFIED per advisory. | Pin `Django==6.0.9` in both files. Run the backend suites (section 7). | sec 1 |
| DEP-002 | P0 (provisional) | Backend | `scipy` is imported but not declared or installed. `apps/core/scripts/calculation.py:3,58` import it at module top; the only runtime caller is `apps/license/models/core.py:683`, inside `try/except Exception`, which sets `optimize_milk_distribution = None` on failure. The method `get_glass_formers` feeds BOE and allotment debit scoping (`lmanagement/settings.py:573`). In the dev venv the optimisation branch is therefore skipped silently. | Owner and financial owner decide whether the optimisation is required. If yes, declare `scipy` and add a test that fails when it is absent. If no, remove the path with characterization evidence. Escalate to Agent B. | sec 3 |
| DEP-003 | P1 | Backend | `pypdf` is 6.15.0 in `.venv` against the spec `>=6.0.0`. OSV lists 40 advisories fixed in 6.16.0 to 6.21.4 (DoS, infinite loops at EOF, large memory use, unvalidated JPEG loading). The library parses uploaded BOE and licence PDFs (`apps/bill_of_entry/parsers/boe_pdf.py`, `apps/license/parsers/dfia_pdf.py`, `apps/core/utils/transfer_letter.py`, and 6 more). | Set `pypdf>=6.21.4` (latest 6.21.4, published 2026-10-28). Rebuild the venv. | sec 1 |
| DEP-004 | P1 | Backend | `djangorestframework` 3.17.1: 7 OSV advisories. Two are fixed in 3.17.2 and five in 3.18.2. Applicable to this app: JSON parser codec selection, DATA_UPLOAD_MAX_MEMORY_SIZE bypass when parsing, and Accept-header CPU cost. Not applicable: TokenProxy (`rest_framework.authtoken` is not in INSTALLED_APPS) and AdminRenderer (only `JSONRenderer` is configured, `settings.py:291-293`). | Pin `djangorestframework==3.18.3` (supports Django 5.2, 6.0, 6.1). | sec 1 |
| DEP-005 | P1 | Backend | `PyJWT` is not declared in any requirements file, yet every simplejwt token passes through it. The venv has 2.13.0 with 27 advisories fixed in 2.14.0 and 2.15.0 (including unauthenticated RecursionError DoS in `jwt.decode`). `SIMPLE_JWT` does not set `ALGORITHM` or `SIGNING_KEY` (defaults: HS256, `SECRET_KEY`), so the JWKS and PEM-detection advisories are probably unreachable. | Declare `PyJWT>=2.15.1` explicitly. Security owner to confirm the algorithm choice. | sec 4 |
| DEP-006 | P1 | Frontend | `axios` 1.18.1 is the HTTP client for every API call (`frontend/src/api/axios.js`). npm audit reports two high advisories (GHSA-vh66-26gq-q6x8 and GHSA-9fr6-4gfg-395g, prototype pollution gadgets in the fetch adapter and default instance) affected below 1.20.0. | Set `axios` to `^1.21.0` (latest) and run the frontend test and build gate. | sec 7 |
| DEP-007 | P1 | Frontend tooling | `vitest` 3.2.6 (direct devDependency) is in the critical advisory range: GHSA-82fw-gwwq-j7x9 (path traversal and arbitrary file read through `@vitest/mocker`, affected below 4.1.11) and GHSA-qxg6-89mg-rqv8 (code injection through manual mocks, below 4.1.12). The transitive `tinypool` 1.1.1 is critical (prototype pollution to RCE, affected up to 2.1.1). Not shipped to users, but it runs in CI, which executes test code from pull requests. | Upgrade `vitest` to at least 4.1.12 (latest 5.0.5 is a major release; npm's suggested fix). Re-run `npm test`. | sec 8 |
| DEP-008 | P1 | Frontend | `dompurify` 3.4.14 is a declared runtime dependency with two critical npm audit advisories (GHSA-p98j-92pf-mc4p, GHSA-6688-9rhm-gjv2, affected up to 3.4.16). No source file imports it, so runtime exposure is nil today. It also enters the tree through the unused `jspdf`. | Remove `dompurify` together with `jspdf` (DEP-028). If it must stay, use 3.4.17. | sec 7 |
| DEP-009 | P2 | Backend | `Pillow==12.2.0` (exact pin) has 85 OSV advisories. Fixed in 12.3.0 (published 2026-07-01) and 13.0.0 (latest, 2026-10-16, a major release). Exposure: local logo and stamp images (`apps/core/utils/pdf_helpers.py:302,376`), pdf2image rasterised pages (`dfia_pdf.py`), and reportlab output. | Set `Pillow==12.3.0` as the minimum. Evaluate 13.0.0 with the PDF golden-output tests. | sec 1 |
| DEP-010 | P2 | Backend and test | `requests` is `>=2.31.0` in production and `==2.32.3` in `requirements-test.txt`. Four OSV advisories, including a `.netrc` credential leak (CVE-2024-47081, fixed 2.32.4) and insecure temp-file reuse (fixed 2.33.0). Latest 2.34.2. | Set `requests>=2.34.2` in both files. | sec 1, sec 2 |
| DEP-011 | P2 | Backend | `beautifulsoup4` (`bs4`) is imported by `apps/core/management/commands/update_dgft_descriptions.py:105` (unguarded inside the function), `apps/core/scripts/company_names.py:79` (inside try) and `backend/scripts/dgft_shipping_bill.py:35`. It is not declared or installed. The management command fails with ImportError when run. | Declare `beautifulsoup4==4.15.0` if the commands stay in use; otherwise retire them (see DEP-024 for the same question). | sec 3 |
| DEP-012 | P2 | Backend runtime | Celery 5.6.3 uses kombu 5.6.2 for Redis. The kombu `redis` extra declares `redis>=4.5.2,<6.5`. The project pins `redis==7.4.0` directly, outside that range. django-redis 6.0.0 has no upper bound, so it is compatible. No CI job starts a worker or sends a task through the broker. Runtime compatibility is UNVERIFIED. | Add a worker smoke test in CI against the redis:7 service, then decide between pinning redis below 6.5 and accepting 7.4 with evidence. Redis 8.1.0 is the latest (2026-07-30). | sec 4 |
| DEP-013 | P2 | Backend configuration | `lmanagement/settings.py:247` sets `STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"`. Django 5.1 removed this setting. It is absent from Django 6.0's `global_settings.py` (verified in `.venv`), and no `STORAGES` key exists. Static files therefore use the default storage: no manifest hashing and no WhiteNoise compression. | Replace with `STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}, "default": {...}}`. Test `collectstatic` and the manifest. Infrastructure audit (Agent E) to confirm how static files are served in production. | sec 5 |
| DEP-014 | P2 | Frontend build | `package.json` declares `"vite": "npm:rolldown-vite@7.2.2"` and an override that forces every Vite resolution to this fork. `@vitejs/plugin-react-oxc` 0.1.1 declares `peerDependencies: { vite: "^6.3.0" }`, which the installed 7.2.2 does not satisfy. `npm ls` does not report this as invalid. Official `vite` is 8.3.5 (latest). Plugin latest is 0.4.3 (2025-11-12). | Decide: either move to official Vite 8 with a current React plugin and rerun build, or record the fork as a deliberate decision with its peer exceptions. | sec 8 |
| DEP-015 | P2 | Frontend lint | ESLint 9.39.1 is out of support. npm marks the installed version deprecated ("no longer supported"), and endoflife.date lists 9.x EOL 2026-08-06 (latest 9.39.5 on 9; 10.14.0 on 10). ESLint 10 is blocked by `eslint-plugin-react` 7.37.5 (peer `eslint ^3 to ^9.7`, npm audit moderate advisory with no fix listed). `eslint-plugin-react-refresh` 0.4.24 also has a moderate advisory with no fix listed; 0.5.7 supports ESLint 9 and 10. `eslint-plugin-react-hooks` 7.1.1 and `typescript-eslint` 8.61 already accept ESLint 10. | Plan an ESLint 10 migration: replace or fork `eslint-plugin-react` (or drop its rules that are not needed), upgrade `@eslint/js` to 10.0.1 and the hook and refresh plugins. Run `npm run lint`. | sec 8 |
| DEP-016 | P2 | Frontend | `exceljs` 4.4.0 is a declared runtime dependency with no source import. The only mention is the `vite.config.js` alias `'exceljs': 'exceljs/dist/exceljs.min.js'`. Its last publish was 2023-10-19. Its dependency chain (archiver, glob, readdir-glob, zip-stream, rimraf 2.7.1 through unzipper and fstream) carries moderate npm audit advisories with no fix in the compatible range. | Remove the dependency and the alias. Confirm no `.xlsx` generation is done in the browser (backend exports only, per `apps/license/views`). | sec 7 |
| DEP-017 | P2 | Frontend dev and build chain | Transitive high advisories in the build and lint chain: `zod` 4.1.12 (memory exhaustion, below 4.6.6) via `eslint-plugin-react-hooks`; `js-yaml` 4.3.1 via `eslint`; `source-map-js` 1.2.1 via tailwindcss and postcss; `brace-expansion` (1.1.18 and 5.x) via minimatch; `browserslist` 4.28.6 via `@babel/core`. Not in the shipped bundle (not traced further, UNVERIFIED). `follow-redirects` 1.16.0 via `axios` Node adapter (see DEP-006). | Refresh the lock file after DEP-006, DEP-007 and DEP-015 so the transitive versions move. Rerun `npm audit`. Do not run `npm audit fix --force` (it proposes major downgrades for several chains). | sec 9 |
| DEP-018 | P2 | Backend reproducibility | No lock file or hash set for the backend. Transitive packages (kombu, billiard, vine, amqp, asgiref, sqlparse, PyJWT, lxml, python-docx, jinja2 and others) are not pinned. `.venv` differs from the declared pins: `setuptools 84.0.0` against `<81`; `PyJWT 2.13.0` (undeclared); `asgiref 3.12.1` against `3.10.0` in `requirements_python314.txt`; `lxml 6.1.1` against `6.0.2`. `pip check` reports only `ipykernel` missing `debugpy`. | Generate a hashed lock (pip-tools or uv) from `requirements.txt`, and have CI run `pip check` and a pip-audit-equivalent gate. | sec 1, sec 4, sec 5 |
| DEP-019 | P2 | Runtime contract | No `.python-version`, `pyproject.toml`, `.nvmrc`, `engines` field or Dockerfile. CI pins Python 3.14 and Node 24, PostgreSQL 16 and Redis 7 (`ci.yml`). Django 6.0 accepts PostgreSQL 14 and newer (`django/db/backends/postgresql/features.py:10`). PostgreSQL 14 reaches end of life on 2026-11-12 (endoflife.date). Production versions of Python, Node, PostgreSQL, Redis and system binaries are not recorded in the repository. | Record the supported matrix in one file (for example `docs/v1/07-quality-and-operations/operational-configuration-contracts.md`): Python 3.14, Node 24, PostgreSQL 16 or later, Redis 7. Add `.python-version` and `.nvmrc`. | sec 13 |
| DEP-020 | P3 | Backend transitive | `sqlparse` 0.5.5 (pulled by Django, not declared) has 10 OSV advisories, all fixed in 0.6.0 (latest, 2026-08-13). Django imports it in `django/db/backends/base/operations.py` and two introspection modules. Exposure from app code is not evidenced. | After the Django bump, declare `sqlparse>=0.6.0` and rerun the backend suite. | sec 4 |
| DEP-021 | P3 | Backend test | `pytest==8.3.4` (test pin) is affected by CVE-2025-71176 (GHSA-6w46-j5rx-g56g, insecure tmpdir handling), fixed in 9.0.3. Latest 9.2.0. Test-environment exposure only. | Move to `pytest>=9.0.3` with pytest-django 4.14.0 and pytest-cov 7.x, then rerun the suites. | sec 2 |
| DEP-022 | P3 | Backend build | `setuptools<81` in `requirements.txt` has this stated rationale: "docxcompose (used by docxtpl) still imports pkg_resources". In the venv, `docxtpl 0.20.2` requires only `jinja2`, `lxml` and `python-docx`. `docxcompose` is an optional `subdoc` extra, not installed, and no repository code imports `docxtpl.subdoc` or `pkg_resources`. The same stale rationale is repeated in the comment at `lmanagement/settings.py:9`. The pin also contradicts `requirements_python314.txt` (82.0.1). The venv's 84.0.0 is affected by GHSA-xmj3-9gf7-h52w (fixed 84.1.0; build-time, Windows path escape). | Remove the pin after a clean-install test. Then keep setuptools at the latest 84.x. Remove the `settings.py` warning filter for `pkg_resources` (lines 10-14) when the pin goes. | sec 1 |
| DEP-023 | P3 | Backend | `psycopg2` is imported inside `migrate_auth.py:67-68` (the one-off legacy auth migration). It is not declared or installed, and the project otherwise uses psycopg 3. | Retire the command after the migration is confirmed complete, or port it to psycopg 3. Owner decision (section 10). | sec 3 |
| DEP-024 | P3 | Backend | `rq` and `django_rq` are imported by `apps/core/management/commands/rqworker.py:66-94` inside a try. Neither is declared or installed. No RQ setting exists (`RQ_QUEUES` absent). Celery is the operational queue. The command is dead code. This confirms BE-INV-04. | Remove the command, or declare the packages and configure RQ. Owner decision (section 10). | sec 3 |
| DEP-025 | P3 | Backend | `brotli` is imported inside an encoding branch (`apps/core/management/commands/fetch_exchange_rates.py:60-61`). It is not declared or installed. Behaviour on ImportError depends on the surrounding try, which was not fully read (UNVERIFIED). | Declare `brotli` if the `br` encoding is needed, otherwise drop `br` from the accepted encodings. | sec 3 |
| DEP-026 | P3 | Backend | Imports of modules that do not exist anywhere in the repository: `ebrc`, `shipping_bill` (`lmanagement/tasks.py:20-47`, an orphan file, BE-INV-07) and `item_fetch_bisc`, `item_fetch_conf` (`apps/core/management/commands/fetch_detail_bisc.py:12-15`, `fetch_detail_conf.py:8`). These commands cannot run. | Delete the orphan file and the two commands, or restore the missing modules from history with owner approval. | sec 3 |
| DEP-027 | P3 | Backend | Direct imports of packages that arrive only transitively: `python-dateutil` (`apps/license/item_report.py:4`, `views/dashboard.py:8`, `models/core.py:2161`, via celery) and `python-docx` (`apps/license/views/license.py:1028`, via docxtpl). | Declare both with the pinned versions the venv has: `python-dateutil==2.9.0.post0` and `python-docx==1.2.0`. | sec 3 |
| DEP-028 | P3 | Frontend | Declared runtime packages with no source import: `jspdf` 4.2.1, `jspdf-autotable` 5.0.7, `jwt-decode` 4.0.0, `recharts` 3.9.2 (only `vi.mock` in `Dashboard.test.tsx` and a stale `optimizeDeps` entry in `vite.config.js`; the comment that the Dashboard trend panel imports Recharts is no longer true), `@radix-ui/react-popover` 1.1.16, `@radix-ui/react-scroll-area` 1.2.11. `jspdf` also brings `dompurify` and `fflate` (advisories). | Remove the six packages after confirming the Dashboard does not render Recharts. Re-run the frontend gate. | sec 7 |
| DEP-029 | P3 | Backend | `django-extensions` 4.1 is a development tool but sits in `requirements.txt` and is listed unconditionally in `INSTALLED_APPS` (`settings.py:133`). It adds `runserver_plus`, `shell_plus` and `graph_models` to production. | Move to a dev requirements file, or add it to `INSTALLED_APPS` only when `DEBUG` is true. | sec 1 |
| DEP-030 | P3 | Backend system | Native libraries are needed but not declared or documented in the repository: tesseract (`pytesseract`), poppler (`pdf2image`), zbar (`pyzbar`), libpq (`psycopg`, CI installs `libpq-dev`). `pyzbar` 0.1.9 was last released on 2022-03-15 and carries a Beta classifier. | Document the system packages in the deployment runbook. Track `pyzbar` maintenance and evaluate a replacement. | sec 1 |
| DEP-031 | P3 | Frontend test | `frontend/playwright/accessibility.spec.ts` imports `axe-playwright`, which is undeclared and not installed. The file sits outside the Playwright `testDir` (`./e2e`) and never runs. Root-level `route-browser-test.js` and `route-authenticated-test.mjs` import `playwright` directly; it resolves only through `@playwright/test`. | Delete the orphan spec or port it to `@axe-core/playwright`. Declare `playwright` or move the scripts into `e2e/`. | sec 11 |
| DEP-032 | P4 | Stale files | `backend/requirements_python314.txt` is a 58-line frozen snapshot that disagrees with `requirements.txt` (setuptools 82.0.1, pypdf 6.10.2, PyJWT 2.10.1) and lists `docopt` and `tqdm`, which no code imports. CI does not read it. `backend/tailwind.config.js` and `backend/postcss.config.js` (Tailwind v3 style, autoprefixer declared nowhere). `frontend/jest.config.js` (Jest is not installed; Vitest is used). `apps/license/__init__.py:1` sets `default_app_config`, which Django 6.0 ignores (verified in `django/apps/config.py`). | Delete the snapshot and the orphan configs after confirming nothing references them. Remove the `default_app_config` line. | sec 6, sec 12 |
| DEP-033 | P4 | Backend test | Declared test packages with no use: `faker` 33.1.0 (one test file mentions the word; no import), `flake8` 7.1.1 (no configuration file, not run in CI), `pytest-xdist` 3.6.1 (no `-n` in `pytest.ini` or CI). `django-stubs`, `djangorestframework-stubs` and `types-PyYAML` are installed in `.venv` without any mypy configuration in `backend/`. | Remove the unused entries, or add the gate they were meant for. | sec 2, sec 5 |
| DEP-034 | P4 | Backend | Major versions available but not urgent: `django-redis` 7.0.0 (Django `<7` and `>=5.2`; redis `>=4` with no upper bound), `django-tables2` 3.0.1, `reportlab` 5.1.0, `django-filter` 26.2, `redis` 8.1.0, `gunicorn` 26.2.0 (MDS), `numpy` 2.5.4 (patch). Each needs a regression run for its own area. | Schedule with the next minor window: django-redis after cache tests; reportlab after golden PDF comparison. | sec 1, sec 6 |
| DEP-035 | P4 | Frontend | TypeScript 5.9.3 (latest 7.0.2, 2026-07-08). `typescript-eslint` 8.61 declares `typescript >=4.8.4 <6.1.0`, so TypeScript 7 is blocked by the lint toolchain. | Stay on 5.9.x. Track `typescript-eslint` support for TypeScript 7. | sec 8 |
| DEP-036 | P4 | Frontend | Behind on minor or major versions with no advisory: `react` and `react-dom` 19.2.0 (latest 19.3.1); `@types/react` 19.2.5 (19.3.0); `react-datepicker` 8.9.0 (9.1.0 is a major release); `framer-motion` 12.40.0 (14.9.0 is a major release); `jsdom` 26.1.0 (30.1.3); `@testing-library/jest-dom` 6.9.1 (7.0.1); `@playwright/test` 1.62.1 (1.64.1, which also needs browser refresh); `@tanstack/react-query` 5.101.2 (5.105.0). | Batch the minors. Take majors one at a time with their test suites. | sec 7, sec 8 |
| DEP-037 | P4 | Test requirements | `tests/e2e/requirements.txt` is unpinned (`pytest>=8.0`, `requests>=2.31`, `selenium>=4.20`). `mds-client/pyproject.toml` requires `Django>=6.0` unpinned, so its CI installs whatever 6.x is current. Installed selenium is 4.47.0 (latest 4.52.0). | Pin the e2e requirements. Pin the Django major and minor in mds-client CI. | sec 6 |
| DEP-038 | P5 | Patch drift | Patch releases behind: `psycopg` 3.3.3 (3.3.6), `python-dotenv` 1.2.2 (1.2.4), `numpy` 2.5.2 (2.5.4), `coverage` 7.6.10 (7.17.0), `pytest-cov` 6.0.0 (7.1.0), `@tailwindcss/vite` and `tailwindcss` 4.3.1 (4.3.3), `@tanstack/react-query` and devtools, `react-router-dom` 7.18.2 (7.18.5), `sonner`, `lucide-react`, `tailwind-merge`, `@testing-library/react`, `@testing-library/user-event`, `@radix-ui/*`, `typescript-eslint`, `baseline-browser-mapping` (2.10.43; moderate advisory below 2.11.0, latest 2.11.34). | Take with the next dependency refresh. Do not combine with a major change. | sec 1, sec 2, sec 7, sec 8 |

Items checked and found clean: no use of removed Django APIs (`django.utils.timezone.utc`, `force_text`, `ugettext`, `USE_L10N`, `index_together`, `url()` routes, `is_ajax`); no use of `datetime.utcnow`; no `np.float`-style aliases; no Pillow `ANTIALIAS`; no openpyxl `get_sheet_by_name`; no legacy pypdf names (`PdfFileReader`, `extractText`); no legacy Celery `celery.task` import; the frontend Devtools import is gated on `import.meta.env.DEV` (`src/main.tsx:21`), so it stays out of production.

---

## 4. Compatibility matrix

Status values: **Supported** (project claims it and CI exercises it), **Works by metadata** (declared compatible, not exercised by CI), **Conflict** (declared constraints disagree), **Untested** (no evidence), **Not claimed** (project documentation does not claim it).

| Layer | Versions in repo | Constraint or evidence | Claimed by project docs or CI | Status |
|---|---|---|---|---|
| Python | 3.14.6 (`.venv`); CI "3.14" | Django 6.0 needs >=3.12; numpy 2.5 needs >=3.12; Pillow 13 needs >=3.11 | CI runs 3.14 only | Supported (3.14). 3.12 and 3.13 are Not claimed. |
| Django | 6.0.4 pinned; 6.0.9 latest in 6.0 | 26 advisories on 6.0.4 (DEP-001) | CI runs Django 6.0.4 | Supported but vulnerable (DEP-001) |
| Django and PostgreSQL | CI postgres:16; deployment docs say CI uses PG 16 | Django 6.0 minimum PG 14 (`features.py:10`). PG 14 EOL 2026-11-12; PG 16 EOL 2028-11-09 | Only PG 16 is Supported. PG 14, 15, 17 and 18 are Untested. | Supported on 16; PG 14 is Untested and EOL soon (DEP-019) |
| Django and DRF | DRF 3.17.1 | DRF 3.17.1 declares Django 6.0 classifier; DRF 3.18.3 declares 5.2, 6.0, 6.1 | CI | Supported; upgrade to 3.18.3 (DEP-004) |
| Django and simplejwt | simplejwt 5.5.1 | No Django 6.0 classifier on PyPI; CI exercises auth tests | CI | Supported by test, Works by metadata only |
| Django and django-redis | django-redis 6.0.0 | `Django>=4.2`, `redis>=4.0.2`, no upper bounds | Cache used in code | Works by metadata; cache tests in CI UNVERIFIED |
| Django and django-tables2 | 2.7.5 | No Django 6.0 classifier; 3.0.1 has one | CI | Supported by test |
| Django and WhiteNoise | whitenoise 6.12.0 | Django 6.0 classifier present. The storage setting is ignored (DEP-013). | Static serving not claimed in CI | Conflict between intent and configuration (DEP-013) |
| Django and psycopg | psycopg 3.3.3 | Django requires `psycopg>=3.1.12`; Django checks `>=3.1.12` at import | CI | Supported |
| Celery and Redis (broker) | celery 5.6.3; kombu 5.6.2; redis 7.4.0; django-redis | kombu `redis` extra: `redis>=4.5.2,<6.5`. Project pins 7.4.0 outside it. | No CI job runs a worker | Conflict by metadata; Untested runtime (DEP-012) |
| Redis server | CI redis:7 | Redis 7.4 EOL 2029-12-01 (endoflife.date) | Redis 7 claimed by CI | Supported. Redis 8 is Not claimed. |
| Celery and Python 3.14 | celery 5.6.3 | No `pip check` conflict for celery in venv (the only reported issue is ipykernel missing debugpy) | CI runs worker-free tests | Works by metadata |
| Node | 24.19.0 local; CI 24 | vitest `^18 or ^20 or >=22`; react-router-dom `>=20`; plugin-react-oxc `>=20`; typescript-eslint `^18.18 or ^20.9 or >=21.1`; @playwright `>=20` | CI runs Node 24 | Supported. Node 24 active LTS to 2028-04-30 (endoflife.date). |
| React | react 19.2.0, react-dom 19.2.0 | TanStack Query, Radix, react-select 5, cmdk 1, sonner 2, framer-motion 12, react-datepicker 8 all declare React 19 | CI runs the app | Supported |
| React and react-datepicker 9 | 9.1.0 (not installed) | Peer range for 9.x not verified | Not claimed | Untested if upgraded |
| TypeScript | 5.9.3 | typescript-eslint 8.61 peer `>=4.8.4 <6.1.0` | CI typecheck | Supported. TypeScript 7 is Conflict (DEP-035). |
| Vite | rolldown-vite 7.2.2 under the name `vite` | `@vitejs/plugin-react-oxc` 0.1.1 peer `vite ^6.3.0`: Conflict, not reported by npm ls. `@tailwindcss/vite` 4.3.1 peer `^5.2 or ^6 or ^7 or ^8`: satisfied. `esbuild` required peer `^0.25.0`: satisfied. | CI runs `vite build` | Build works in CI; declared peer Conflict (DEP-014) |
| Tailwind | tailwindcss 4.3.1 with @tailwindcss/vite 4.3.1 | v4 is CSS-first, no frontend `tailwind.config`. Backend holds a v3-style config (DEP-032). | CI builds | Supported |
| TanStack Query | 5.101.2; devtools 5.101.2 | Devtools peer `@tanstack/react-query ^5.101.2`, exact match | CI | Supported |
| Vitest | 3.2.6 | Resolves against rolldown-vite 7.2.2; no peer error reported; critical advisories (DEP-007) | CI runs `npm test` | Supported but vulnerable |
| Playwright | @playwright/test 1.62.1; @axe-core/playwright 4.13 | axe peer `playwright-core >=1.0`: satisfied | Deployment docs: Playwright and axe are not run in CI | Not claimed in CI; local only |
| ESLint | eslint 9.39.1 with plugins | eslint-plugin-react peer up to `^9.7`. ESLint 9 out of support (DEP-015). | CI runs `npm run lint` | Supported but out of support |
| Backend and Frontend cross-check | Django and React are independent | None | — | Not applicable |
| MDS and main backend | MDS pins Django 6.0.4, DRF 3.17.1, psycopg 3.3.3 | Same versions as main backend | MDS CI runs its own suite | Supported; inherits DEP-001 and DEP-004 |
| mds-client | Django `>=6.0` (unpinned) | CI installs whatever 6.x is current | mds-client CI | Untested for each 6.x release (DEP-037) |
| numpy and scipy | numpy 2.5.2 installed; scipy absent | calculation.py needs both | Not claimed | Conflict: the module cannot load without scipy (DEP-002) |
| Pillow and reportlab, pytesseract, pdf2image | Pillow 12.2.0; reportlab 4.4.10 requires `pillow>=9.0.0` | Satisfied | Not claimed | Supported |
| setuptools | `<81` pin; venv 84.0.0 | Pin violated in venv | Not claimed | Conflict (DEP-022) |
| Python 3.14 and docxtpl and python-docx | docxtpl 0.20.2, python-docx 1.2.0 | `subdoc` extra not used | — | Supported |

---

## 5. Missing, unused and undeclared dependencies

### 5.1 Imported by code but not declared (MISSING)

| Package | Import sites | Installed | Declared | Finding |
|---|---|---|---|---|
| scipy | `apps/core/scripts/calculation.py:3,58` (lazy use from `apps/license/models/core.py:683`); `backend/scripts/veg_oil_allocator.py:1` | No | No | DEP-002 (P0 provisional) |
| beautifulsoup4 (`bs4`) | 3 files (DEP-011) | No | No | DEP-011 (P2) |
| brotli | `fetch_exchange_rates.py:61` | No | No | DEP-025 (P3) |
| psycopg2 | `migrate_auth.py:67-68` | No | No | DEP-023 (P3) |
| rq | `rqworker.py:68-94` | No | No | DEP-024 (P3) |
| django-rq | `rqworker.py:66` | No | No | DEP-024 (P3) |
| python-dateutil | 3 production files | Yes (transitive) | No | DEP-027 (P3) |
| python-docx | `views/license.py:1028` | Yes (transitive) | No | DEP-027 (P3) |
| mds-client | 7 production files (admin guarded by try) | No (optional local package) | Commented out | Documented as optional; DEP-037 |
| ebrc, shipping_bill, item_fetch_bisc, item_fetch_conf | Local modules, absent from the repository | — | — | DEP-026 (P3) |
| axe-playwright (frontend) | `frontend/playwright/accessibility.spec.ts` (orphan) | No | No | DEP-031 (P3) |
| playwright (frontend) | Root-level scripts | Yes (transitive) | No | DEP-031 (P3) |

### 5.2 Declared but unused

| Package | Where declared | Evidence | Finding |
|---|---|---|---|
| faker | backend/requirements-test.txt | No import; one test file mentions the word | DEP-033 |
| flake8 | backend/requirements-test.txt | No config file; not run in `ci.yml` | DEP-033 |
| pytest-xdist | backend/requirements-test.txt | No `-n` in `pytest.ini` or CI | DEP-033 |
| dompurify | frontend dependencies | No import | DEP-008 (P1 for advisory) |
| exceljs | frontend dependencies | Alias only in vite.config.js | DEP-016 (P2) |
| jspdf | frontend dependencies | No import | DEP-028 (P3) |
| jspdf-autotable | frontend dependencies | No import | DEP-028 (P3) |
| jwt-decode | frontend dependencies | No import | DEP-028 (P3) |
| recharts | frontend dependencies | Test mock only | DEP-028 (P3) |
| @radix-ui/react-popover | frontend dependencies | No import | DEP-028 (P3) |
| @radix-ui/react-scroll-area | frontend dependencies | No import | DEP-028 (P3) |
| baseline-browser-mapping | frontend devDependencies | Tooling data; not imported | Intentional. Update (DEP-038). |
| django-extensions | backend requirements | Used only as an INSTALLED_APPS entry | Keep in dev only (DEP-029) |

### 5.3 Installed in .venv but neither declared nor imported

pandas 3.0.6, pdfplumber 0.11.10, xlrd 2.0.2, webdriver-manager 4.1.2, pytest-html 4.2.0 (no imports); PyPDF2 3.0.1 (root-level `parity_extract_pdf_excel.py` only; deprecated upstream name); type stubs for django-stubs, djangorestframework-stubs and types-PyYAML. Drift only. Clean the venv or declare them (DEP-033, DEP-018).

---

## 6. Deprecations

### 6.1 Framework and language

| Item | Location | Status | Finding |
|---|---|---|---|
| `STATICFILES_STORAGE` | `lmanagement/settings.py:247` | Removed in Django 5.1; silently ignored in Django 6.0 (absent from `global_settings.py`) | DEP-013 |
| `default_app_config` | `apps/license/__init__.py:1` | Ignored by Django 6.0 | DEP-032 |
| `pkg_resources` warning filter | `lmanagement/settings.py:10-14` | Harmless, but the API is gone in setuptools 84 | DEP-022 |
| Django upstream support | Django 6.0 | Non-LTS. EOL 2027-04-30. Django 6.1 EOL 2027-12-31. Django 5.2 LTS EOL 2028-04-30 (endoflife.date). | Owner question Q-DEP-1 (section 10) |
| PostgreSQL 14 | Django 6.0 minimum | EOL 2026-11-12 | DEP-019 |
| Python 3.14 | CI and venv | Supported to 2030-10-31 | none |
| Node 24 | CI and local | Active LTS to 2028-04-30 | none |
| Node 25 | (not used) | EOL 2026-06-01 | none |
| PyPDF2 | `parity_extract_pdf_excel.py` (root) | Upstream name is superseded by pypdf | DEP-033 |

### 6.2 Frontend

| Item | Status | Finding |
|---|---|---|
| eslint 9.39.1 | npm deprecation notice: "This version is no longer supported"; EOL 2026-08-06 | DEP-015 |
| eslint-plugin-react 7.37.5 | Not deprecated, but no ESLint 10 peer | DEP-015 |
| jest.config.js | Refers to Jest, which is not used | DEP-032 |
| vite as an npm alias to rolldown-vite | Non-standard fork under the public name | DEP-014 |
| Other installed packages | The npm `deprecated` field was checked for all 57 top-level packages; no other flags | none |

### 6.3 Backend packages

No PyPI deprecation flag was found for any installed package. `pyzbar` (last release 2022) and `docxtpl` (Beta classifier) are the maintenance-risk entries; both are noted in the inventory.

---

## 7. Backend upgrade and gap detail for the critical path

This section gives the exact pins, verified against registry metadata on 2026-11-01.

| Package | Current pin | Minimum safe target | Recommended target | Latest (publish date) | Notes |
|---|---|---|---|---|---|
| Django | 6.0.4 | 6.0.9 | 6.0.9 | 6.1.2 (2026-10-06) | Same minor. Fixes span 6.0.5 to 6.0.8 plus 6.0.9. |
| djangorestframework | 3.17.1 | 3.18.2 | 3.18.3 | 3.18.3 (2026-10-06) | Declares Django 5.2, 6.0 and 6.1. |
| pypdf | `>=6.0.0` (venv 6.15.0) | 6.21.4 | `>=6.21.4` | 6.21.4 (2026-10-28) | Parses untrusted PDFs. |
| PyJWT | not declared (venv 2.13.0) | 2.15.0 | `>=2.15.1` | 2.15.1 (2026-09-28) | Add explicit pin. |
| Pillow | 12.2.0 | 12.3.0 | 12.3.0, then evaluate 13.0.0 | 13.0.0 (2026-10-16) | 13.0.0 is a major release. |
| requests | `>=2.31.0` / `==2.32.3` (tests) | 2.33.0 | `>=2.34.2` | 2.34.2 (2026-05-14) | Align test pin. |
| sqlparse | not declared (venv 0.5.5) | 0.6.0 | `>=0.6.0` | 0.6.0 (2026-08-13) | Django allows 0.5.0 and above. |
| pytest | 8.3.4 | 9.0.3 | 9.2.0 | 9.2.0 | Test only. |
| setuptools | `<81` (venv 84.0.0) | 84.1.0 | Remove pin; keep latest 84.x | 84.2.1 (2026-10-20) | DEP-022. |
| scipy | not declared | Owner decision | Declare pinned version if required | 1.18.1 | DEP-002. |
| beautifulsoup4 | not declared | 4.15.0 if kept | 4.15.0 | 4.15.0 | DEP-011. |

Redis, Celery and PostgreSQL are covered in sections 4 and 3 (DEP-012 and DEP-019).

---

## 8. Frontend toolchain detail

| Package | Installed | Problem | Recommended target |
|---|---|---|---|
| axios | 1.18.1 | High advisories below 1.20.0 | 1.21.0 (latest) |
| vitest | 3.2.6 | Critical advisories below 4.1.11 and 4.1.12 | 5.0.5 (npm's suggested fix, major) or 4.1.12 minimum |
| dompurify | 3.4.14 | Critical, unused | Remove (3.4.17 if kept) |
| vite (alias to rolldown-vite) | 7.2.2 | Non-standard, peer mismatch with plugin | Official Vite 8 with the current React plugin |
| @vitejs/plugin-react-oxc | 0.1.1 | Peer `vite ^6.3.0` | 0.4.3 with a matching Vite |
| eslint | 9.39.1 | Out of support | 10.14.0 after plugin replacement |
| eslint-plugin-react | 7.37.5 | Blocks ESLint 10 | Replace or drop the rules in use |
| eslint-plugin-react-hooks | 7.0.1 | Behind | 7.1.1 |
| eslint-plugin-react-refresh | 0.4.24 | Moderate advisory, no fix listed | 0.5.7 |
| typescript | 5.9.3 | TypeScript 7 blocked by typescript-eslint | Stay on 5.9.x |
| esbuild | 0.25.12 | Required peer of rolldown-vite 7 | Keep until Vite 8 |
| baseline-browser-mapping | 2.10.43 | Moderate advisory below 2.11.0 | 2.11.34 |
| exceljs | 4.4.0 | Unused, stale (2023), advisory chain | Remove |

Transitive advisories and their paths are in the inventory section 9.

---

## 9. Limits

- **Environment scope.** Only the developer environment was read: `.venv` (Python 3.14.6 on macOS), `frontend/node_modules`, CI workflow files and repository files. The production server's Python, Node, PostgreSQL, Redis and system package versions are not in the repository and are UNVERIFIED. The `.venv` is not evidence of what is deployed.
- **Advisory data.** OSV records were queried per installed PyPI version. "Likely affecting" was decided by comparing the installed version with OSV `fixed` events; OSV ranges were not otherwise re-derived. npm audit was run with `--package-lock-only` (read-only) and its bulk advisory data at the time of the run. `pip-audit` is not installed and was not installed, as the rules forbid. Advisory severity labels come from npm audit for npm packages and are not provided by OSV for PyPI packages.
- **Applicability.** Judged by grep and by reading specific lines. No exploit was attempted and no runtime request was sent. Several advisories (Django cache disclosures, pypdf DoS, PyJWT DoS) need a runtime check before a release decision.
- **End-of-life dates** come from endoflife.date, a third-party aggregator. Vendor support pages were not fetched.
- **Registry snapshot.** Latest versions and publish dates were read on 2026-11-01 and will change.
- **Network.** All lookups succeeded: PyPI JSON API, npm registry (`/latest` and version documents), OSV API, npm audit bulk endpoint and endoflife.date. One first pass timed out for some npm full documents and was re-run successfully with the lighter `/latest` endpoint. No lookup failed in the final data.
- **No execution.** No test, build, lint, migration check or install was run during this audit. Upgrade recommendations are not validated against the suites.
- **Priority scale.** P3 to P5 are defined in this report (section 2). Only P0 to P2 appear in the repository roadmap.
- **Overlap with other agents.** DEP-002 needs Agent B (financial semantics). DEP-013, DEP-019 and DEP-012 need Agent E (infrastructure). DEP-005 and DEP-004 need the security audit to confirm JWT algorithm and browsable-API exposure in production.
- **Lock files.** `frontend/package-lock.json` was read through `npm ls` and `npm audit`, not parsed. No backend lock exists.

---

## 10. Candidate questions for the product owner

Most findings above are technical and do not need an owner. These three need a decision.

| ID | Category | Impact | Question |
|---|---|---|---|
| Q-DEP-1 | Support policy | Upgrade cadence and risk | Django 6.0 is a non-LTS release with upstream EOL 2027-04-30. Should the platform stay on the 6.x line (6.1 EOL 2027-12-31) or move to the 5.2 LTS line (EOL 2028-04-30)? |
| Q-DEP-2 | Financial correctness (P0 provisional) | Whether a dependency is required, and whether debits change | Is the scipy-based milk and glass-former distribution optimisation (`apps/core/scripts/calculation.py`, called from `LicenseDetailsModel.get_glass_formers`) an approved calculation that must run in production? If yes, scipy must be declared. If no, removing the path changes outputs and needs owner sign-off. |
| Q-DEP-3 | Operational scope | Removes three missing packages | May the dead RQ worker command (`rqworker`) and the one-off legacy auth migration (`migrate_auth`, which needs psycopg2) be removed rather than declared as dependencies? |

---

## 11. Method

1. Read `backend/requirements.txt`, `requirements-test.txt`, `requirements_python314.txt`, the MDS and mds-client manifests, `tests/e2e/requirements.txt`, `frontend/package.json`, `.github/workflows/ci.yml`, and the settings sections that define installed apps, DRF, JWT, Celery, cache and storage.
2. Listed `.venv` with `python -I -B -m pip freeze` (124 distributions) and ran `pip check`. Checked module presence with `importlib.util.find_spec`, without importing application code.
3. Listed `frontend/node_modules` with `npm ls --depth=0 --json` (57 top-level packages, no invalid entries) and traced transitive advisory paths with `npm ls <pkg> --all`.
4. AST-scanned the backend (excluding virtualenv, htmlcov, migrations, artifacts and report folders) for top-level imports. Regex-scanned the frontend (389 files) for module specifiers.
5. Grepped for removed or deprecated framework APIs (section 3, last paragraph).
6. Queried PyPI, the npm registry, OSV and endoflife.date for latest versions, publish dates, classifiers, peer dependencies, deprecation flags and advisories. Read-only GET requests and OSV POST queries.
7. Ran `npm audit --package-lock-only --json` (read-only).
8. Checked engines and peer compatibility from registry metadata for installed versions.

No installation, upgrade, removal, pin or edit of any dependency file was performed. Temporary analysis scripts were kept in `/tmp/depaudit` and are not part of the deliverable.
