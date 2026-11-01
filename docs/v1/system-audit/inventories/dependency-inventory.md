# Dependency inventory — License Manager V1 system audit (Agent C)

Audit date: 2026-11-01. Branch `version-v1`, HEAD `d78c8b1d`. Read-only. No package was installed, upgraded, removed or pinned; no requirements, lock or virtualenv file was changed.

Companion report: [14-dependency-and-technology-audit.md](../14-dependency-and-technology-audit.md) (finding IDs `DEP-xxx`).

## Sources and how each column was filled

| Column | Source |
|---|---|
| Declared spec | `backend/requirements.txt`, `backend/requirements-test.txt`, `frontend/package.json` (exact text) |
| Installed | Backend: `.venv` (Python 3.14.6) via `python -I -B -m pip freeze`. Frontend: `npm ls --depth=0` in `frontend/node_modules`. `not installed` means absent from that environment. |
| Used-in | Backend: AST scan of `import`/`from` statements under `backend/` (production = outside `tests/` paths; test = paths containing `test`). Frontend: regex scan of `from`/`import`/`import()`/`require`/CSS `@import` across 389 source and config files (excluding `node_modules`, `dist`, report folders). Counts are importing files, not call sites. |
| Latest | PyPI JSON API and npm registry `/latest` endpoint, read 2026-11-01. |
| Advisories | OSV API (`api.osv.dev`) queried per installed PyPI version; fix versions taken from OSV `fixed` events. `npm audit --package-lock-only` for npm. Applicability to this app is noted only where a grep answered it. |
| Maintenance | Registry publish date of the latest release, PyPI `Development Status` classifier, npm `deprecated` field. End-of-life dates from endoflife.date (third-party aggregator). |

Status legend: `current` = installed equals latest; `patch/minor/major behind` = registry latest is newer; `ADVISORY` = OSV or npm audit reports an open advisory for the installed version; `UNUSED` = declared but no import found; `MISSING` = imported but not declared; `DEAD-SETTING` = configuration key that the framework ignores.

Priority scale (defined in the report, section 2): P0 critical security or data correctness; P1 high; P2 medium; P3 low or maintenance risk; P4 hygiene and major-version upgrades; P5 patch drift.

---

## 1. Backend runtime packages (`backend/requirements.txt`, 25 direct packages)

| Package | Declared spec | Installed (.venv) | Purpose | Used-in | Status | Risk | Recommended target | Priority | Affected packages |
|---|---|---|---|---|---|---|---|---|---|
| Django | ==6.0.4 | 6.0.4 | Web framework and ORM | 259 prod / 182 test import sites | ADVISORY: 26 OSV ids fixed in 6.0.5 to 6.0.8. Latest 6.0.9 (6.0 cycle EOL 2027-04-30). Latest 6.1.2. | High | 6.0.9 (same minor) | P0 | master-data-service (same pin), django-filter, DRF, simplejwt, django-redis, drf-spectacular, whitenoise |
| djangorestframework | ==3.17.1 | 3.17.1 | REST API framework | 81 prod / 97 test | ADVISORY: 7 ids; 2 fixed in 3.17.2, 5 fixed in 3.18.2. Latest 3.18.3 (supports Django 5.2, 6.0, 6.1). | High | 3.18.3 | P1 | Django, simplejwt, drf-spectacular, master-data-service |
| djangorestframework-simplejwt | ==5.5.1 | 5.5.1 | JWT issue and verify; token_blacklist app | 3 prod / 40 test | current; no OSV record for 5.5.1 itself. Uses PyJWT (see section 4). | Low | 5.5.1 (re-test on DRF and Django bump) | P5 | PyJWT (undeclared), DRF, Django |
| django-filter | ==25.2 | 25.2 | Filtersets for list endpoints | 6 prod | current for pin; latest 26.2 (Django 6.0 classifier) | Low | 25.2 now; 26.2 later | P4 | Django, DRF |
| drf-spectacular | ==0.30.0 | 0.30.0 | OpenAPI schema generation | 3 prod / 1 test | current; Django 6.0 classifier | Low | 0.30.0 | P5 | DRF |
| django-cors-headers | ==4.9.0 | 4.9.0 | CORS middleware | 1 (settings) | current; Django 6.0 classifier | Low | 4.9.0 | none | Django |
| django-extensions | ==4.1 | 4.1 | Dev commands (runserver_plus, shell_plus) | INSTALLED_APPS only | current; ships in production INSTALLED_APPS | Low (dev tool in prod) | Move to dev requirements or gate on DEBUG | P3 | Django |
| django-tables2 | ==2.7.5 | 2.7.5 | Server-side table rendering | 2 prod (license tables) | latest 3.0.1 (major; Django 6.0 classifier); no OSV record for 2.7.5 | Low | 2.7.5 now; 3.0.1 after regression | P4 | Django |
| django-redis | ==6.0.0 | 6.0.0 | Django cache backend on Redis | settings CACHES; used by cache_utils, throttling, cached_views | latest 7.0.0 (Django <7, Django 5.2 and 6.0 classifiers) | Low | 7.0.0 after cache tests | P4 | redis-py, Django |
| whitenoise | ==6.12.0 | 6.12.0 | Static file serving middleware | settings MIDDLEWARE; settings line 247 | current; setting used for storage is DEAD-SETTING | Medium | 6.12.0 with STORAGES fix (DEP-013) | P2 | Django |
| celery | ==5.6.3 | 5.6.3 | Background task queue | 8 prod files | current (latest 5.6.3, published 2026-03-26) | Medium (broker compatibility) | 5.6.3 | P2 | kombu, redis, billiard, vine, amqp, click, python-dateutil |
| redis | ==7.4.0 | 7.4.0 | Redis client (Celery broker via kombu; django-redis) | 1 prod (rqworker only); indirect via django-redis and kombu | latest 8.1.0 (published 2026-07-30). kombu redis extra declares redis <6.5. | Medium | 7.4.0 pending broker smoke test; decide 8.x later | P2 | celery, kombu, django-redis |
| python-dotenv | ==1.2.2 | 1.2.2 | .env loading in settings | 1 prod | patch behind (latest 1.2.4) | Low | 1.2.4 | P5 | none |
| openpyxl | ==3.1.5 | 3.1.5 | XLSX read and write | 17 prod / 19 test | current; last release 2024-06-28 (stable, low churn) | Low | 3.1.5 | none | et_xmlfile |
| reportlab | ==4.4.10 | 4.4.10 | PDF generation | 21 prod / 3 test | latest 5.1.0 (major, published 2026-10-22) | Low | 4.4.10 now; 5.x after PDF regression | P4 | Pillow (>=9) |
| pypdf | >=6.0.0 | 6.15.0 (venv) | PDF parsing of uploaded BOE and licence PDFs | 9 prod / 8 test | ADVISORY: 40 ids fixed in 6.16.0 to 6.21.4. Latest 6.21.4 (2026-10-28). Spec is unpinned, so venv is below latest. | High | >=6.21.4 | P1 | Pillow (optional extra) |
| Pillow | ==12.2.0 | 12.2.0 | Image handling (logo and stamp images, pdf2image pages, reportlab) | 8 prod | ADVISORY: 85 ids; fix versions 12.3.0 (published 2026-07-01) and 13.0.0 (latest, 2026-10-16) | Medium | 12.3.0 minimum; 13.0.0 after evaluation | P2 | pytesseract, pdf2image, reportlab, pypdf (extra) |
| pytesseract | ==0.3.13 | 0.3.13 | OCR wrapper (needs tesseract binary) | 2 prod | current; no advisory | Medium (system binary not declared) | 0.3.13 | P3 | Pillow, tesseract (system) |
| pdf2image | ==1.17.0 | 1.17.0 | PDF to image (needs poppler binary) | 1 prod (dfia_pdf.py) | current (last release 2024-01-07) | Medium (system binary not declared) | 1.17.0 | P3 | Pillow, poppler (system) |
| pyzbar | ==0.1.9 | 0.1.9 | QR decode (needs zbar library) | 1 prod (dfia_pdf.py) | last release 2022-03-15; classifier Beta | Medium (maintenance) | Keep until a replacement is evaluated | P3 | Pillow, zbar (system) |
| requests | >=2.31.0 | 2.32.3 (venv) | HTTP client (DGFT pages, MDS, scrapers) | 7 prod / 2 test | ADVISORY: 4 ids; fixed 2.32.4 and 2.33.0. Latest 2.34.2. | Medium | >=2.34.2 | P2 | urllib3, idna, certifi, charset-normalizer |
| psycopg | ==3.3.3 | 3.3.3 | PostgreSQL driver (Django ENGINE postgresql imports it) | via Django | patch behind (latest 3.3.6) | Low | 3.3.6 | P5 | libpq (system) |
| docxtpl | ==0.20.2 | 0.20.2 | DOCX template rendering | 1 prod (allotment/scripts/aro.py) | current; PyPI classifier Beta; last release 2025-11-13 | Low | 0.20.2 | P5 | python-docx, jinja2, lxml |
| setuptools | <81 | 84.0.0 (venv, violates pin) | Build tooling; pin rationale is pkg_resources for docxcompose | not imported by repo code | ADVISORY (venv 84.0.0): GHSA-xmj3-9gf7-h52w, fixed 84.1.0 (build-time, Windows path). Pin violated in venv; requirements_python314.txt pins 82.0.1. Latest 84.2.1. | Low | Remove pin after clean-install test; then 84.2.x | P3 | none; docxcompose not installed |
| numpy | >=2.1,<3 | 2.5.2 | Numerics used only by apps/core/scripts/calculation.py | 1 prod (lazy import) | patch behind (latest 2.5.4); module cannot import without scipy | Low | 2.5.4 | P5 | scipy (missing, DEP-002) |

## 2. Backend test packages (`backend/requirements-test.txt`, includes runtime file; 7 test-only packages plus a second requests pin)

| Package | Declared spec | Installed (.venv) | Purpose | Used-in | Status | Risk | Recommended target | Priority | Affected packages |
|---|---|---|---|---|---|---|---|---|---|
| pytest | ==8.3.4 | 8.3.4 | Test runner | 158 test files; pytest.ini; CI | ADVISORY: CVE-2025-71176 (GHSA-6w46-j5rx-g56g), fixed 9.0.3. Latest 9.2.0. | Medium (test environment) | >=9.0.3 (9.2.0 after suite run) | P3 | pytest-django, pytest-cov, pytest-xdist |
| pytest-django | ==4.9.0 | 4.9.0 | Django test integration | pytest.ini DJANGO_SETTINGS_MODULE | latest 4.14.0 | Low | 4.14.0 with pytest bump | P4 | pytest |
| pytest-cov | ==6.0.0 | 6.0.0 | Coverage plugin | pytest.ini addopts (--cov) | latest 7.1.0 | Low | 7.1.0 with coverage bump | P4 | pytest, coverage |
| pytest-xdist | ==3.6.1 | 3.6.1 | Parallel test execution | No config, no CI use found (`-n` absent) | UNUSED (in repo config and CI) | Low | Remove, or document CLI use | P4 | pytest |
| requests | ==2.32.3 | 2.32.3 | Test HTTP client | 2 test files | ADVISORY (see requests above). Test pin is lower than prod spec. | Medium | >=2.34.2 | P2 | none |
| faker | ==33.1.0 | not imported | Fake data | UNUSED: 1 file mentions the word only (tests/test_boe_script_helpers.py); no import | UNUSED. Latest 40.44.0. | Low | Remove | P4 | none |
| flake8 | ==7.1.1 | 7.1.1 | Lint | UNUSED: no config file; not run in CI | UNUSED. Latest 7.5.0. | Low | Remove, or adopt in CI | P4 | pycodestyle, pyflakes, mccabe |
| coverage[toml] | ==7.6.10 | 7.6.10 | Coverage measurement | via pytest-cov | latest 7.17.0 | Low | 7.17.0 with pytest-cov | P5 | pytest-cov |

## 3. Backend packages imported by code but not declared (MISSING)

| Package (import name) | Declared spec | Installed (.venv) | Purpose | Used-in | Status | Risk | Recommended target | Priority | Affected packages |
|---|---|---|---|---|---|---|---|---|---|
| scipy (`scipy`) | none | not installed | optimize.minimize and linprog in calculation.py | apps/core/scripts/calculation.py:3 and :58 (top-level); called lazily from apps/license/models/core.py:683 inside try/except Exception that sets the function to None; backend/scripts/veg_oil_allocator.py (standalone) | MISSING and silently absent in venv. Latest 1.18.1. | High (provisional: silent calculation fallback) | Owner decision on intended behaviour (DEP-002); then declare scipy or remove the path | P0 | numpy, LicenseDetailsModel.get_glass_formers, balance and debit outputs (to be confirmed by Agent B) |
| beautifulsoup4 (`bs4`) | none | not installed | HTML parsing for DGFT pages | apps/core/management/commands/update_dgft_descriptions.py:105; apps/core/scripts/company_names.py:79 (inside try); backend/scripts/dgft_shipping_bill.py:35 | MISSING. Latest 4.15.0. | Medium | Declare beautifulsoup4==4.15.0 if commands are kept | P2 | update_dgft_descriptions command, company name scraping |
| brotli (`brotli`) | none | not installed | Brotli response decoding | apps/core/management/commands/fetch_exchange_rates.py:61 (inside encoding branch) | MISSING. Latest 1.2.1 (Beta classifier). | Low | Declare, or drop br from accepted encodings | P3 | fetch_exchange_rates command |
| psycopg2 (`psycopg2`) | none (psycopg 3 declared) | not installed | Legacy source DB copy during auth migration | apps/accounts/management/commands/migrate_auth.py:67-68 (inside function) | MISSING. Latest psycopg2-binary 2.9.13. | Low | Retire the one-off command, or port to psycopg 3 | P3 | migrate_auth command |
| rq (`rq`) | none | not installed | Redis Queue worker | apps/core/management/commands/rqworker.py:68-94 (inside try) | MISSING and DEAD: no RQ settings; Celery is the operational queue. Latest 3.0.0. | Low | Remove the command (BE-INV-04 confirmed) | P3 | rqworker command |
| django-rq (`django_rq`) | none | not installed | Django integration for RQ | apps/core/management/commands/rqworker.py:66 (inside try) | MISSING and DEAD. Latest 4.2.0. | Low | Same as rq | P3 | rqworker command |
| python-dateutil (`dateutil`) | none (transitive via celery) | 2.9.0.post0 | relativedelta date arithmetic | apps/license/item_report.py:4; apps/license/views/dashboard.py:8; apps/license/models/core.py:2161 | Transitive but imported directly. Current. | Low | Declare python-dateutil==2.9.0.post0 | P3 | celery |
| python-docx (`docx`) | none (transitive via docxtpl) | 1.2.0 | DOCX document creation | apps/license/views/license.py:1028 (inside function) | Transitive but imported directly. Current. | Low | Declare python-docx==1.2.0 | P3 | docxtpl |
| mds-client (`mds_client`) | commented out in requirements.txt | not installed | Master-Data Service client (optional, MDS_ENABLED) | 7 prod files; apps/core/admin.py:17 is guarded with try | Optional local package (ADR-001). Local path only. | Low | Declare as optional extra when MDS is enabled | P4 | MDS integration |

Local modules imported but not present (not PyPI packages, listed for completeness): `ebrc`, `shipping_bill` (lmanagement/tasks.py:20-47, orphan module BE-INV-07); `item_fetch_bisc`, `item_fetch_conf` (apps/core/management/commands/fetch_detail_bisc.py:12-15, fetch_detail_conf.py:8). No file with those names exists in the repository (find returned nothing). See DEP-026.

## 4. Backend transitive packages of note (installed, not declared directly)

| Package | Declared spec | Installed (.venv) | Purpose | Used-in | Status | Risk | Recommended target | Priority | Affected packages |
|---|---|---|---|---|---|---|---|---|---|
| PyJWT | none (`requirements_python314.txt` pins 2.10.1) | 2.13.0 | JWT encode and decode used by simplejwt | via simplejwt (every token issue and verify) | ADVISORY: 27 ids likely affect 2.13.0; fixed in 2.14.0 and 2.15.0. Latest 2.15.1. App uses default HS256 (ALGORITHM not set), so the JWKS and PEM advisories are probably not reachable. | High | Declare PyJWT>=2.15.1 | P1 | djangorestframework-simplejwt |
| sqlparse | none (Django requires >=0.5.0) | 0.5.5 | SQL formatting used inside Django backend operations | Django base/operations.py and introspection modules | ADVISORY: 10 ids; fixed in 0.6.0 (latest, 2026-08-13). Exposure from app code not evidenced. | Low to Medium | >=0.6.0 after Django test run | P3 | Django |
| kombu | none (via celery) | 5.6.2 | Messaging layer; Redis transport | via celery | current. kombu[redis] extra declares redis <6.5. | Medium (broker compatibility) | Follow celery; verify with redis-py pin | P2 | celery, redis |
| asgiref | none (Django requires >=3.9.1) | 3.12.1 | ASGI helpers | via Django | venv 3.12.1; requirements_python314.txt pins 3.10.0 (stale) | Low | Let Django resolve; do not pin | P5 | Django |
| lxml | none (docxtpl requires) | 6.1.1 | XML processing | via docxtpl and python-docx | venv 6.1.1; requirements_python314 pins 6.0.2; latest 6.1.3 | Low | Let resolve | P5 | docxtpl |
| cryptography | none | 50.0.2 | Crypto primitives | Source not identified in repo (likely a dev-only dependency) | current (latest 50.0.2) | Low | Confirm origin | P5 | none identified |

## 5. Backend packages installed in .venv but not declared and not imported by backend code (drift)

| Package | Installed | Purpose | Used-in | Status | Recommended target | Priority |
|---|---|---|---|---|---|---|
| pandas | 3.0.6 | DataFrame work | 0 imports in repo (excluding .venv, htmlcov, node_modules) | UNUSED and undeclared | Do not declare; remove from venv if not needed | P4 |
| pdfplumber | 0.11.10 | PDF text extraction | 0 imports | UNUSED and undeclared | Same | P4 |
| xlrd | 2.0.2 | Legacy XLS read | 0 imports | UNUSED and undeclared | Same | P4 |
| webdriver-manager | 4.1.2 | Browser driver download | 0 imports | UNUSED and undeclared | Same | P4 |
| pytest-html | 4.2.0 | HTML test report | 0 imports (CLI plugin only) | Undeclared | Same | P4 |
| PyPDF2 | 3.0.1 | Deprecated PDF library | parity_extract_pdf_excel.py (root-level script, 2 files) | Root script only; deprecated upstream name | Remove with script or port to pypdf | P4 |
| selenium | 4.47.0 | Browser automation | tests/e2e only (19 files); declared in tests/e2e/requirements.txt (>=4.20) | Not in backend requirements | Keep in e2e requirements, pinned | P4 |
| ipykernel, ipython, jupyter stack | 7.3.0, 9.16.1, various | Notebooks (accounting_validation.ipynb, verify_ledger notebook) | Notebook files | Dev tooling; ipykernel reports missing debugpy (pip check) | Dev-only; declare or remove | P4 |
| django-stubs, djangorestframework-stubs, django-stubs-ext | 6.1.0, 3.18.0, 6.1.0 | Type stubs | No mypy configuration file found under backend/ | UNUSED (no type checker config found; UNVERIFIED) | Remove or add mypy gate | P4 |
| types-PyYAML | 6.0.12.20260815 | Type stubs | none | UNUSED | Remove | P4 |

## 6. Other Python requirement and manifest files

| File | Packages declared | Status | Priority | Notes |
|---|---|---|---|---|
| backend/requirements_python314.txt | 58 pinned lines (frozen snapshot) | STALE and contradicts requirements.txt: setuptools==82.0.1 (requirements.txt says <81); pypdf==6.10.2 (spec >=6.0.0); PyJWT==2.10.1; contains docopt==0.6.2 and tqdm==4.67.1 that no code imports. Not referenced by CI. | P4 | DEP-032 |
| master-data-service/requirements.txt | Django==6.0.4, djangorestframework==3.17.1, psycopg==3.3.3 | Inherits DEP-001 and DEP-004 advisories | P0 (via Django) | Same pins as backend |
| master-data-service/requirements-prod.txt | gunicorn==23.0.0 (latest 26.2.0), whitenoise==6.12.0 | gunicorn patch and minor behind | P5 | Includes requirements.txt |
| master-data-service/requirements-test.txt | pytest==8.3.4, pytest-django==4.9.0 | Inherits DEP-021 | P3 | |
| tests/e2e/requirements.txt | pytest>=8.0, requests>=2.31, selenium>=4.20 | UNPINNED. Installed selenium 4.47.0; latest 4.52.0 | P4 | DEP-037 |
| mds-client/pyproject.toml | Django>=6.0, requests>=2.31; optional celery>=5.3; test: responses>=0.24, pytest>=8.0, pytest-django>=4.8 | Django spec unpinned (CI installs latest 6.x). responses not checked. | P4 | DEP-037 |

---

## 7. Frontend runtime dependencies (`frontend/package.json` dependencies, 36)

Installed versions from `npm ls --depth=0` (all 57 top-level packages present; no invalid or missing entries reported).

| Package | Declared spec | Installed | Purpose | Used-in | Status | Risk | Recommended target | Priority | Affected packages |
|---|---|---|---|---|---|---|---|---|---|
| @radix-ui/react-checkbox | ^1.3.4 | 1.3.4 | Checkbox primitive | 1 (src/components/ui/checkbox.tsx) | patch/minor behind (latest 1.4.1) | Low | 1.4.1 | P5 | shadcn ui layer |
| @radix-ui/react-dialog | ^1.1.16 | 1.1.16 | Dialog primitive | 1 (ui/dialog.tsx) | behind (latest 1.3.1) | Low | 1.3.1 with UI test | P4 | ConfirmDialog and modals |
| @radix-ui/react-dropdown-menu | ^2.1.17 | 2.1.17 | Dropdown primitive | 1 (ui/dropdown-menu.tsx) | behind (latest 2.2.1) | Low | 2.2.1 | P5 | |
| @radix-ui/react-label | ^2.1.9 | 2.1.9 | Label primitive | 1 (ui/label.tsx) | behind (latest 2.1.17) | Low | 2.1.17 | P5 | |
| @radix-ui/react-popover | ^1.1.16 | 1.1.16 | Popover primitive | 0 | UNUSED | Low | Remove | P3 | DEP-028 |
| @radix-ui/react-scroll-area | ^1.2.11 | 1.2.11 | Scroll area | 0 | UNUSED | Low | Remove | P3 | DEP-028 |
| @radix-ui/react-select | ^2.3.0 | 2.3.0 | Select primitive | 1 (ui/select.tsx) | behind (latest 2.4.1) | Low | 2.4.1 | P5 | |
| @radix-ui/react-separator | ^1.1.9 | 1.1.9 | Separator | 1 (ui/separator.tsx) | behind (latest 1.2.0) | Low | 1.2.0 | P5 | |
| @radix-ui/react-slot | ^1.2.5 | 1.2.5 | Slot composition | 2 (badge.tsx, button.tsx) | behind (latest 1.5.0) | Low | 1.5.0 | P5 | |
| @radix-ui/react-switch | ^1.3.0 | 1.3.0 | Switch | 1 (ui/switch.tsx) | behind (latest 1.4.1) | Low | 1.4.1 | P5 | |
| @radix-ui/react-tabs | ^1.1.14 | 1.1.14 | Tabs | 1 (ui/tabs.tsx) | behind (latest 1.2.1) | Low | 1.2.1 | P5 | |
| @radix-ui/react-tooltip | ^1.2.9 | 1.2.9 | Tooltip | 1 (ui/tooltip.tsx) | behind (latest 1.4.1) | Low | 1.4.1 | P5 | |
| @tailwindcss/vite | ^4.3.1 | 4.3.1 | Tailwind v4 Vite plugin | 1 (vite.config.js) | behind (latest 4.3.3) | Low | 4.3.3 | P5 | tailwindcss, vite |
| @tanstack/react-query | ^5.101.2 | 5.101.2 | Server-state caching | 44 files | behind (latest 5.105.0) | Low | 5.105.0 | P5 | React 18 or 19 peer |
| @tanstack/react-query-devtools | ^5.101.2 | 5.101.2 | Dev-only devtools | 1 (src/main.tsx, lazy and gated on import.meta.env.DEV) | behind (latest 5.105.0) | Low (not in production bundle) | 5.105.0 | P5 | @tanstack/react-query (exact match required) |
| axios | ^1.13.2 | 1.18.1 | HTTP client for all API calls | 1 (src/api/axios.js) | ADVISORY (high): GHSA-vh66-26gq-q6x8 and GHSA-9fr6-4gfg-395g, affected <1.20.0. Latest 1.21.0. | High | >=1.20.0 (1.21.0 latest) | P1 | follow-redirects (transitive, Node adapter) |
| class-variance-authority | ^0.7.1 | 0.7.1 | Variant classes | 3 (ui/alert.tsx, ui/badge.tsx, ...) | current | None | 0.7.1 | none | shadcn ui |
| clsx | ^2.1.1 | 2.1.1 | Class merge helper | 1 (src/lib/utils.ts) | current | None | 2.1.1 | none | |
| cmdk | ^1.1.1 | 1.1.1 | Command palette | 1 (CommandPalette.tsx) | current (latest 1.1.1) | None | 1.1.1 | none | React 18 or 19 peer |
| dompurify | ^3.3.3 | 3.4.14 | HTML sanitiser | 0 | ADVISORY (critical, npm audit): GHSA-p98j-92pf-mc4p and GHSA-6688-9rhm-gjv2, affected <=3.4.15 or <=3.4.16. UNUSED. Latest 3.4.17. | Critical advisory, no runtime exposure in src | Remove if unused; otherwise 3.4.17 | P1 | jspdf 4.2.1 (also declared and unused; jspdf depends on dompurify) |
| exceljs | ^4.4.0 | 4.4.0 | Excel generation | 0 imports (only the vite.config.js alias 'exceljs' pointing to dist) | UNUSED; last publish 2023-10-19; npm audit moderate chain (archiver, glob, readdir-glob, zip-stream, fflate) with no fix in registry | Medium (advisory chain) | Remove | P2 | DEP-016 |
| framer-motion | ^12.40.0 | 12.40.0 | Animation | 4 (ErrorScreen.tsx, motion/PageTransition.tsx, ...) | major behind (latest 14.9.0) | Low | Evaluate 14.x; keep 12.x meanwhile | P4 | React 18 or 19 peer |
| jspdf | ^4.2.1 | 4.2.1 | Client-side PDF | 0 | UNUSED | Low | Remove | P3 | DEP-028 |
| jspdf-autotable | ^5.0.2 | 5.0.7 | PDF tables | 0 | UNUSED; latest 5.0.9 | Low | Remove | P3 | DEP-028 |
| jwt-decode | ^4.0.0 | 4.0.0 | Decode JWT payload | 0 | UNUSED | Low | Remove | P3 | DEP-028 |
| lucide-react | ^1.18.0 | 1.18.0 | Icons | 109 files | behind (latest 1.66.0) | Low | 1.66.0 | P5 | React peer ^16.5 to ^19 |
| react | ^19.2.0 | 19.2.0 | UI runtime | 140 files | behind (latest 19.3.1) | Low | 19.3.1 | P4 | react-dom, testing-library, all peers |
| react-datepicker | ^8.9.0 | 8.9.0 | Date picker | 3 (TradeForm.tsx, MasterForm.tsx) | major behind (latest 9.1.0; peer react up to 19) | Low | 9.1.0 after form tests | P4 | React peer |
| react-dom | ^19.2.0 | 19.2.0 | DOM renderer | 2 (main.tsx, ConfirmDialog.tsx) | behind (latest 19.3.1) | Low | 19.3.1 with react | P4 | react |
| react-router-dom | ^7.9.6 | 7.18.2 | Routing | 57 files | patch behind (latest 7.18.5); engines node >=20 | Low | 7.18.5 | P5 | react, react-dom |
| react-select | ^5.10.2 | 5.10.2 | Select control | 16 files | current | None | 5.10.2 | none | React 16 to 19 peer |
| recharts | ^3.9.2 | 3.9.2 | Charts | 0 source imports; used only in Dashboard.test.tsx (vi.mock) and vite.config.js optimizeDeps comment | UNUSED in production source. Latest 3.10.1. vite.config.js comment says Dashboard trend panel imports Recharts; no such import found. | Low | Remove if confirmed; otherwise 3.10.1 | P3 | DEP-028 |
| sonner | ^2.0.7 | 2.0.7 | Toast notifications | 61 files | patch behind (latest 2.0.8) | Low | 2.0.8 | P5 | React 18 or 19 peer |
| tailwind-merge | ^3.6.0 | 3.6.0 | Class merge | 1 (src/lib/utils.ts) | behind (latest 3.7.0) | Low | 3.7.0 | P5 | |
| tailwindcss | ^4.3.1 | 4.3.1 | Tailwind v4 engine | 1 (src/styles/tailwind.css) | behind (latest 4.3.3) | Low | 4.3.3 | P5 | @tailwindcss/vite |
| tw-animate-css | ^1.4.0 | 1.4.0 | Animation utilities | 1 (src/styles/tailwind.css) | current | None | 1.4.0 | none | tailwindcss |

## 8. Frontend development dependencies (`frontend/package.json` devDependencies, 21)

| Package | Declared spec | Installed | Purpose | Used-in | Status | Risk | Recommended target | Priority | Affected packages |
|---|---|---|---|---|---|---|---|---|---|
| @axe-core/playwright | ^4.13.0 | 4.13.0 | Accessibility checks in E2E | 2 (e2e/accessibilityHelpers.ts, e2e/shell-and-filter.accessibility.spec.ts) | behind (latest 4.14.0) | Low | 4.14.0 | P5 | @playwright/test |
| @eslint/js | ^9.39.1 | 9.39.1 | ESLint recommended config | 1 (eslint.config.js) | major behind (latest 10.0.1); tied to ESLint major | Medium (with ESLint EOL) | Move with ESLint 10 | P2 | eslint |
| @playwright/test | ^1.62.1 | 1.62.1 | E2E runner | 16 files (e2e/*.spec.ts) | behind (latest 1.64.1); not run in CI (documented) | Low | 1.64.1 with browser refresh | P4 | playwright (transitive) |
| @testing-library/jest-dom | ^6.9.1 | 6.9.1 | DOM matchers | 1 (src/test/setup.ts) | major behind (latest 7.0.1) | Low | 7.0.1 after test run | P4 | vitest |
| @testing-library/react | ^16.3.2 | 16.3.2 | Component tests | 51 files | patch behind (latest 16.3.3) | Low | 16.3.3 | P5 | React 18 or 19 peer; @testing-library/dom ^10 |
| @testing-library/user-event | ^14.6.1 | 14.6.1 | User event simulation | 8 files | behind (latest 14.6.8) | Low | 14.6.8 | P5 | |
| @types/react | ^19.2.2 | 19.2.5 | React types | tsc (implicit) | behind (latest 19.3.0) | None | 19.3.0 with react | P5 | typescript |
| @types/react-dom | ^19.2.2 | 19.2.3 | React DOM types | tsc (implicit) | behind (latest 19.3.0) | None | 19.3.0 | P5 | typescript |
| @vitejs/plugin-react-oxc | ^0.1.1 | 0.1.1 | React Fast Refresh and JSX via oxc | 1 (vite.config.js) | Pre-1.0; peerDependency vite ^6.3.0 while installed Vite is rolldown-vite 7.2.2 (npm ls does not flag it); latest 0.4.3 (published 2025-11-12) | Medium | 0.4.x with a Vite version it declares | P2 | vite (DEP-014) |
| baseline-browser-mapping | ^2.10.32 | 2.10.43 | Browser data for Browserslist | 0 imports (tooling data) | ADVISORY (moderate): GHSA-w5vr-8v7q-w6rv, affected <2.11.0. Latest 2.11.34. | Low | 2.11.34 | P4 | browserslist |
| esbuild | ^0.25.0 | 0.25.12 | JS minifier; required peer of rolldown-vite | vite.config.js (minify: 'esbuild'); rolldown-vite peer ^0.25.0 | behind (latest 0.28.2) but outside the peer range | Low | Keep 0.25.x while rolldown-vite 7.x is used | P5 | rolldown-vite |
| eslint | ^9.39.1 | 9.39.1 | Linting | 1 (eslint.config.js) | OUT OF SUPPORT: npm deprecation notice on installed version; endoflife.date EOL 2026-08-06. Moderate advisory (npm audit). Latest 10.14.0. | Medium | 10.14.0 after plugin compatibility | P2 | DEP-015 |
| eslint-plugin-react | ^7.37.5 | 7.37.5 | React lint rules | 1 (eslint.config.js) | Moderate advisory (npm audit, range >=7.23.0, no fix listed). Peer eslint ^3 to ^9.7, so it blocks ESLint 10. Latest 7.37.5. | Medium | Replace or fork, or keep ESLint 9 | P2 | DEP-015 |
| eslint-plugin-react-hooks | ^7.0.1 | 7.0.1 | Hooks rules | 1 (eslint.config.js) | behind (latest 7.1.1); latest peer includes eslint ^10 | Low | 7.1.1 | P2 | DEP-015 |
| eslint-plugin-react-refresh | ^0.4.24 | 0.4.24 | Fast refresh lint | 1 (eslint.config.js) | Moderate advisory (npm audit, no fix listed); latest 0.5.7 with peer eslint ^9 or ^10 | Low | 0.5.7 | P2 | DEP-015 |
| globals | ^16.5.0 | 16.5.0 | Global variable sets for ESLint | 1 (eslint.config.js) | behind (latest 17.13.0) | Low | 17.13.0 with ESLint change | P5 | eslint |
| jsdom | ^26.1.0 | 26.1.0 | DOM for Vitest (environment set by string) | vitest.config.ts environment 'jsdom' | major behind (latest 30.1.3) | Low | 30.1.3 after test run | P4 | vitest |
| typescript | ^5.9.3 | 5.9.3 | Type checking (tsc in typecheck script and CI) | tsc (implicit) | major behind (latest 7.0.2); typescript-eslint peer is <6.1.0 so TS 7 is blocked | Low | Stay on 5.9.x (DEP-035) | P4 | typescript-eslint |
| typescript-eslint | ^8.61.0 | 8.61.0 | TS lint integration | 1 (eslint.config.js) | behind (latest 8.72.1); moderate advisory via minimatch chain (npm audit) | Low | 8.72.1 | P5 | eslint, typescript |
| vite (npm alias to rolldown-vite@7.2.2, via overrides) | declared through overrides: "npm:rolldown-vite@7.2.2" | 7.2.2 (rolldown-vite) | Dev server and build | vite.config.js; vitest; @tailwindcss/vite | Non-standard fork under the name vite; official vite latest 8.3.5 | Medium | Official Vite 8 (or document the fork decision) | P2 | DEP-014 |
| vitest | ^3.2.6 | 3.2.6 | Unit test runner (CI) | 78 test files | CRITICAL advisories (npm audit): GHSA-82fw-gwwq-j7x9 (path traversal and arbitrary file read via @vitest/mocker, affected <4.1.11) and GHSA-qxg6-89mg-rqv8 (code injection via manual mock, affected <4.1.12). Transitive tinypool critical. Latest 5.0.5 (major). | High (test and CI tooling, not shipped) | >=4.1.12 minimum; 5.0.5 per npm suggestion | P1 | DEP-007 |

## 9. Frontend transitive packages with open advisories (npm audit, not declared directly)

| Package | Installed | Severity | Advisory (summary) | Path | Priority |
|---|---|---|---|---|---|
| tinypool | 1.1.1 (affected range <=2.1.1) | Critical | Prototype pollution gadget leading to RCE in worker options (GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr) | via vitest 3.2.6 | P1 (with vitest) |
| zod | 4.1.12 | High | Memory exhaustion on oversized constrained collections (GHSA-mrhx-c7xc-m3w5, <4.6.6) | via eslint-plugin-react-hooks 7.0.1 (zod-validation-error) | P2 |
| follow-redirects | 1.16.0 | High | Credential header exposure (GHSA-q3jh-wrc6-jgq8, GHSA-8r9p-f939-6h3c, 1.16.0 to 1.16.1) | via axios (Node adapter) | P1 (with axios) |
| js-yaml | 4.3.1 | High | CPU use with empty merge sources (GHSA-2883-xcg3-v3hh, <4.3.2) | via eslint 9.39.1 | P2 |
| source-map-js | 1.2.1 | High | Event-loop DoS via source-map (GHSA-68fv-2mgg-jv7q, <1.2.2) | via tailwindcss/vite, postcss | P2 |
| brace-expansion | 1.1.18 and 5.x | High | Quadratic expansion CPU DoS (GHSA-q2hr-2g5m-vwhr) | via minimatch 3 and 5 (eslint and glob chains) | P2 |
| browserslist | 4.28.6 | High | Unbounded memory growth and crash via browserslist-stats (GHSA-c83g-rgw3-j3cx, GHSA-73wf-gq98-2v4g) | via @babel/core chain | P2 |
| minimatch | <11.0.1 | Moderate | ReDoS-style DoS (GHSA-g3hv-75wg-m249) | via typescript-eslint | P3 |
| fflate | 0.8.2 | Moderate | Infinite loop on malformed ZIP64 (GHSA-px8p-9vwx-vf98, affected 0.8.0 to 0.8.2) | via jspdf 4.2.1 (unused declared package) | P2 (remove with jspdf) |
| archiver, archiver-utils, glob, readdir-glob, zip-stream | various | Moderate | Affected by npm audit with no fix in the compatible range | via exceljs 4.4.0 | P2 (removed with exceljs) |
| @humanfs/node | 0.16.7 (affected <0.16.8) | Moderate | Recursive copy follows symlinked files (GHSA-p498-v437-472g) | via eslint 9.39.1 | P3 |
| rimraf | 2.7.1 | Moderate | Affected range in npm audit | via exceljs, unzipper, fstream | P2 (removed with exceljs) |
| @vitest/mocker | 3.2.6 | Moderate | Same family as vitest critical advisories | via vitest | P1 (with vitest) |

## 10. Frontend declared but not imported in source (summary)

| Package | Declared in | Imported by source | Action | Priority |
|---|---|---|---|---|
| @radix-ui/react-popover | dependencies | No | Remove | P3 |
| @radix-ui/react-scroll-area | dependencies | No | Remove | P3 |
| dompurify | dependencies | No | Remove or upgrade (critical advisory) | P1 |
| exceljs | dependencies | No (alias only in vite.config.js) | Remove (advisory chain) | P2 |
| jspdf | dependencies | No | Remove | P3 |
| jspdf-autotable | dependencies | No | Remove | P3 |
| jwt-decode | dependencies | No | Remove | P3 |
| recharts | dependencies | No (test mock and optimizeDeps only) | Remove after confirming Dashboard | P3 |
| baseline-browser-mapping | devDependencies | No (tooling data) | Keep, but update (moderate advisory) | P4 |

## 11. Frontend imported but not declared

| Import | Where | Status | Action | Priority |
|---|---|---|---|---|
| axe-playwright | frontend/playwright/accessibility.spec.ts | Undeclared, not installed. The file is outside Playwright testDir ./e2e, so the config never runs it (orphan spec). | Delete or port to @axe-core/playwright | P3 |
| playwright | frontend/route-authenticated-test.mjs, route-browser-test.js (root-level scripts) | Undeclared direct import; resolves through @playwright/test (playwright 1.62.1 present in node_modules) | Declare or move scripts | P3 |
| node built-ins (fs, path, url, node:fs, node:url) | root scripts, e2e specs, vite and vitest configs | Built-in, not a dependency | None | none |

## 12. Frontend tooling files without a matching dependency

| File | Issue | Priority |
|---|---|---|
| frontend/jest.config.js | Jest config (jsdom, babel-jest, jest-watch-typeahead). Jest is not installed and Vitest is the test runner. | P4 |
| backend/tailwind.config.js and backend/postcss.config.js | Tailwind-style v3 config and autoprefixer plugin; autoprefixer is declared nowhere; no backend package.json. Backend templates contain Tailwind-era theme files. | P4 |
| frontend/package.json "overrides" uuid ^11.1.1 | No open advisory for uuid 11.1.1 in npm audit; latest 14.0.3. Harmless. | P5 |
| frontend/package.json "engines" | Not declared; Node 24 is set only in CI (no .nvmrc). | P5 (DEP-019) |
| backend/theme (HTML assets) | Static theme HTML and CSS; Tailwind use was not inspected. Not referenced by any backend package. | P4 (DEP-032) |

---

## 13. Node and tooling metadata

| Item | Value | Source |
|---|---|---|
| Node (local) | v24.19.0 | `node --version` |
| npm (local) | 11.17.0 | `npm --version` |
| Node (CI) | 24 | .github/workflows/ci.yml (setup-node) |
| Python (venv) | 3.14.6 at /opt/homebrew (virtualenv created with python@3.14) | .venv/pyvenv.cfg |
| Python (CI) | "3.14" | .github/workflows/ci.yml |
| .python-version, .nvmrc, .tool-versions, pyproject for backend | none found | file search |
| Dockerfile or docker-compose | none found in repository | file search |
| Working-tree change | frontend/package.json adds "test:e2e:isolated": "bash ../scripts/test/run_data_bearing_browser_e2e.sh" (uncommitted). Target script exists and is executable. No new dependency. | git diff |
| Lock files | frontend/package-lock.json present (resolves uuid 11.1.1). Backend: no lock file or hashes. | file search |
