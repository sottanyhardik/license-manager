# Phase 11 Documents Audit Report

## backend/templates/profile.html

- File Path(s): `backend/templates/profile.html`
- Module: Documents / Legacy Django template
- Total LOC: 901
- Lines Reviewed: 901 plus repository-wide dependency references
- Functions Reviewed: 0
- Classes Reviewed: 0
- Validation Improvements: Removed a legacy static HTML profile page with no live validation, form, upload, export, or authenticated runtime path.
- Package Replacements: None; deletion was preferred because React is the active frontend and no Django runtime dependency remained.
- Performance Improvements: Removed a 901-line legacy template and its static asset/script load surface from active source inventory.
- Security Improvements: Removed stale unauthenticated legacy profile markup, external font loading, local asset/script references, static demo links, and inactive form controls from active source inventory.
- Dead Code Removed: Deleted verified-dead `backend/templates/profile.html`.
- Duplicate Logic Removed: Removed duplicate legacy profile/dashboard UI surface superseded by the React application.
- Tests Added: None; no live caller remained. Existing URL-routing regression coverage was run.
- Verification Results:
  - Repository-wide dependency scan found no live `render()`, `render_to_response()`, `TemplateResponse`, generic/class-based view, `include`, `extends`, custom/inclusion tag, email/PDF/report/export, management command, test, URL route, middleware, signal, dynamic import, cached template path, third-party package, or runtime loader reference to `backend/templates/profile.html`.
  - Remaining `profile.html` references are stale static `href` links inside other legacy `backend/templates/*.html` files.
  - React entry HTML remains preserved: the Django catch-all serves `index.html`, and template `DIRS` resolve `frontend/dist` before `backend/templates`.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py -q` -> 14 passed.
  - `.venv/bin/python -m py_compile backend/lmanagement/urls.py backend/lmanagement/settings.py backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/lmanagement backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `.venv/bin/ruff check backend/lmanagement/urls.py backend/lmanagement/settings.py backend/tests/test_url_routing.py` -> blocked by pre-existing unused imports in `backend/tests/test_url_routing.py` (`pytest`, `django.test.TestCase`).
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check -- backend/templates/profile.html` -> clean before source commit.
- Source Commit SHA: `08269148be7f2eea870d8c61158372764e388572`
- Source Commit Timestamp: `2026-07-17T10:54:25+05:30`
- Source Commit Summary: `cleanup(documents): remove dead profile template`
- Blocked Items:
  - Scoped Ruff is blocked by pre-existing unused imports in `backend/tests/test_url_routing.py`.
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Other legacy `backend/templates/*.html` files still contain stale static links to `profile.html`; audit them only when selected by the Phase 11 queue or marked `REQUIRES_RECHECK`.
- Status: DELETED

## docs/media-security-cutover.md

- File Path(s): `docs/media-security-cutover.md`
- Module: Documents / Media security runbook
- Total LOC: 105
- Lines Reviewed: 105 plus deployment script, nginx snippet, authenticated media view, query-token auth, frontend media helpers, and referenced tests
- Functions Reviewed: 0 in the document; referenced `ProtectedMediaView.get`, `JWTAuthenticationFromQueryParam.authenticate`, `toProtectedMediaPath`, `openAuthedFile`, and `openDocument`
- Classes Reviewed: 0 in the document; referenced `ProtectedMediaView` and `JWTAuthenticationFromQueryParam`
- Validation Improvements: Updated stale instructions to reflect current authenticated blob helper usage and the restricted `GET`/`HEAD` download/export query-token fallback.
- Package Replacements: Replaced obsolete `grep` guidance with project-standard `rg`; no dependency added.
- Performance Improvements: Preserved the X-Accel-Redirect operational path and clarified that nginx should serve bytes only from the internal protected-media location after cutover.
- Security Improvements: Removed stale claims that frontend direct media/token flows still exist, documented the remaining public nginx `/media/` operational risk, and clarified final query-token fallback removal criteria.
- Dead Code Removed: None; dependency analysis proved the runbook is live through deployment and frontend helper references.
- Duplicate Logic Removed: None; this is an operational document, not an implementation module.
- Tests Added: None; documentation-only source update. Existing media/auth routing regressions were run.
- Verification Results:
  - Dependency scan found live references from `scripts/deployment/auto-deploy.sh` and `frontend/src/utils/documentDownload.ts`; retained and updated rather than deleted.
  - Frontend direct token/media scan returned only authenticated helper implementation, comments, tests, and `AuthedImage`-style authenticated media consumers.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py backend/tests/test_authentication_query_param.py -q` -> 17 passed.
  - `.venv/bin/ruff check backend/apps/core/views/media.py backend/apps/core/authentication.py backend/tests/test_authentication_query_param.py backend/tests/test_url_routing.py` -> blocked by pre-existing unused imports in `backend/tests/test_url_routing.py` (`pytest`, `django.test.TestCase`).
  - `.venv/bin/python -m py_compile backend/apps/core/views/media.py backend/apps/core/authentication.py backend/lmanagement/urls.py backend/lmanagement/settings.py backend/tests/test_authentication_query_param.py backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/core/views/media.py backend/apps/core/authentication.py backend/lmanagement backend/tests/test_authentication_query_param.py backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check -- docs/media-security-cutover.md` -> clean before source commit.
- Source Commit SHA: `96f0da8f0903b8a18c7ddc1460146572b8994689`
- Source Commit Timestamp: `2026-07-17T10:58:35+05:30`
- Source Commit Summary: `docs(documents): update media security cutover`
- Blocked Items:
  - Scoped Ruff is blocked by pre-existing unused imports in `backend/tests/test_url_routing.py`.
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Public nginx `/media/` remains an operational cutover risk until Step 3 is applied on deployed servers.
  - Restricted query-token JWT fallback remains configured until production logs prove it can be removed.
- Status: COMPLETED

## frontend/src/hooks/useFileUpload.js

- File Path(s): `frontend/src/hooks/useFileUpload.js`, `frontend/src/test/useFileUpload.test.ts`
- Module: Documents / Upload hook
- Total LOC: 919
- Lines Reviewed: 515 hook lines plus 404 focused regression-test lines and live `LedgerUpload.tsx` import paths
- Functions Reviewed: 12 hook/helper/callback functions plus 18 focused test cases
- Classes Reviewed: 0
- Validation Improvements: Added malformed file-object rejection, invalid/non-finite size rejection, invalid max-file-size fallback, case-insensitive MIME matching, safe empty event file-list handling, unsafe endpoint rejection, bounded progress percentages, malformed success response normalization, trimmed error extraction, and non-finite file-size formatting.
- Package Replacements: Reused existing React hooks, Axios API client, and Vitest/testing-library coverage; no new dependency introduced.
- Performance Improvements: Prevented NaN/Infinity progress state and exception-prone response access during upload progress/render cycles.
- Security Improvements: Rejected absolute/protocol-relative upload endpoints and backslash/control-character endpoint paths before multipart POST.
- Dead Code Removed: None; dependency analysis confirmed the hook is live through `frontend/src/pages/LedgerUpload.tsx` and exported by `frontend/src/hooks/index.js`.
- Duplicate Logic Removed: Consolidated repeated response/error/progress handling into local helpers inside the hook.
- Tests Added: Extended `frontend/src/test/useFileUpload.test.ts` with malformed file, MIME case, unsafe endpoint, malformed response/progress, and size-formatting regressions.
- Verification Results:
  - Dependency scan found live imports in `frontend/src/pages/LedgerUpload.tsx` and `frontend/src/hooks/index.js`.
  - `npm test -- useFileUpload.test.ts` -> 18 passed.
  - `npm run typecheck` -> passed.
  - `npm run lint -- --quiet src/hooks/useFileUpload.js src/test/useFileUpload.test.ts` -> clean.
  - `npm run build` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `py_compile`/`compileall` not applicable to JavaScript/TypeScript source; frontend typecheck/build executed instead.
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check -- frontend/src/hooks/useFileUpload.js frontend/src/test/useFileUpload.test.ts` -> clean before source commit.
- Source Commit SHA: `70602d69d878a865aa7b71bd064f194cd927ad5b`
- Source Commit Timestamp: `2026-07-17T11:02:48+05:30`
- Source Commit Summary: `fix(documents): harden file upload hook`
- Blocked Items:
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - `frontend/src/pages/LedgerUpload.tsx` remains its own audited page/component surface and should stay frozen unless dependency changes mark it `REQUIRES_RECHECK`.
- Status: COMPLETED


## frontend/src/pages/Profile.tsx

- File Path(s): `frontend/src/pages/Profile.tsx`, `frontend/src/context/AuthContext.tsx`, `frontend/src/types/index.ts`, `frontend/src/pages/Profile.test.tsx`, `frontend/src/test/useAuth.test.tsx`, `frontend/src/pages/admin/UserForm.test.tsx`, `frontend/src/pages/admin/UserList.test.tsx`
- Module: Documents / React profile page
- Total LOC: 1280 across the audited source/test dependency unit
- Lines Reviewed: 289 profile page lines plus the AuthContext user-update contract, auth types, and affected regression fixtures
- Functions Reviewed: 11 profile helper/component/callback functions plus AuthContext `updateUser` and 22 focused test cases
- Classes Reviewed: 0
- Validation Improvements: Trimmed profile PATCH fields, normalized blank email to `null`, added model-aligned first/last name input limits, synchronized form state after async user hydration, normalized duplicate/malformed role strings, and extracted DRF field/non-field/native error messages safely.
- Package Replacements: Reused React built-ins, existing AuthContext, Axios API client, Vitest, and Testing Library; no new dependency introduced.
- Performance Improvements: Memoized normalized role rendering and avoided unnecessary auth token localStorage rewrites after profile PATCH.
- Security Improvements: Removed `loginSuccess` misuse that could persist `null` access/refresh tokens from localStorage; profile updates now call `updateUser` and only refresh the serialized user snapshot.
- Dead Code Removed: None; dependency analysis confirmed the React profile page is live through `/profile` in `frontend/src/routes/AppRoutes.tsx`.
- Duplicate Logic Removed: Added shared local helpers for profile payload normalization, error extraction, and role normalization inside the page module.
- Tests Added: Added `frontend/src/pages/Profile.test.tsx` and extended `frontend/src/test/useAuth.test.tsx`; updated typed admin auth fixtures for the new context contract.
- Verification Results:
  - Dependency scan found live `/profile` route in `frontend/src/routes/AppRoutes.tsx` behind `ProtectedRoute` and `AdminLayout`; backend dependency is `/auth/me/` served by `backend/apps/accounts/views/auth.py::MeView` with `UserSerializer`.
  - `npm test -- Profile.test.tsx useAuth.test.tsx UserForm.test.tsx UserList.test.tsx` -> 22 passed.
  - `npm test` -> 38 files passed, 161 tests passed.
  - `npm run typecheck` -> passed.
  - `npm run lint -- --quiet src/pages/Profile.tsx src/pages/Profile.test.tsx src/context/AuthContext.tsx src/types/index.ts src/pages/admin/UserForm.test.tsx src/pages/admin/UserList.test.tsx src/test/useAuth.test.tsx` -> clean.
  - `npm run lint -- --quiet` -> clean.
  - `npm run build` -> passed.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py -q` -> 14 passed.
  - `.venv/bin/python -m py_compile backend/manage.py backend/lmanagement/settings.py backend/lmanagement/urls.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/lmanagement backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `.venv/bin/ruff check backend/lmanagement/urls.py backend/lmanagement/settings.py backend/tests/test_url_routing.py` -> blocked by pre-existing unused imports in `backend/tests/test_url_routing.py` (`pytest`, `django.test.TestCase`).
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check` and `git diff --cached --check` for the source unit -> clean before source commit.
- Source Commit SHA: `f0bb9e719b23ad4dc17ae53f187366e135bfdb64`
- Source Commit Timestamp: `2026-07-17T11:08:56+05:30`
- Source Commit Summary: `fix(documents): harden profile page updates`
- Blocked Items:
  - Scoped backend Ruff remains blocked by pre-existing unused imports in `backend/tests/test_url_routing.py`.
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Broader AuthContext session-loading behavior remains outside this Documents unit and should stay frozen unless dependency changes mark it `REQUIRES_RECHECK`.
- Status: COMPLETED


## nginx-protected-media.conf

- File Path(s): `nginx-protected-media.conf`
- Module: Documents / nginx protected media snippet
- Total LOC: 23
- Lines Reviewed: 23 plus `docs/media-security-cutover.md`, active nginx media blocks, `scripts/deployment/auto-deploy.sh`, and `backend/apps/core/views/media.py`
- Functions Reviewed: 0
- Classes Reviewed: 0
- Validation Improvements: Clarified that the `alias` must match `MEDIA_ROOT` with a trailing slash so X-Accel-Redirect path joins remain correct.
- Package Replacements: None; nginx built-in `internal`, `alias`, and `add_header` directives retained.
- Performance Improvements: Preserved nginx byte-serving through the internal X-Accel-Redirect location, avoiding file bytes through gunicorn.
- Security Improvements: Added `Cache-Control: private, no-store` to the reusable internal media snippet for authenticated customs/PII documents.
- Dead Code Removed: None; dependency analysis confirmed the snippet is live operational documentation for secure media cutover.
- Duplicate Logic Removed: None in this unit; active concrete nginx configs already contain related internal blocks and remain queued separately if marked `REQUIRES_RECHECK`.
- Tests Added: None; config-template change only.
- Verification Results:
  - Dependency scan found live references from `docs/media-security-cutover.md`, `scripts/deployment/auto-deploy.sh`, and `backend/apps/core/views/media.py` documentation.
  - Duplicate/config scan found concrete `/protected-media/` blocks in `nginx-license-manager.conf`, `nginx-labdhi.conf`, and `nginx-license-tractor.conf`; broader config parity remains separate queued work.
  - `nginx -v` -> command not found; local nginx syntax validation unavailable.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py -q` -> 14 passed.
  - `.venv/bin/python -m py_compile backend/apps/core/views/media.py backend/lmanagement/settings.py backend/lmanagement/urls.py backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/core/views/media.py backend/lmanagement backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `.venv/bin/ruff check backend/apps/core/views/media.py backend/lmanagement/settings.py backend/lmanagement/urls.py backend/tests/test_url_routing.py` -> blocked by pre-existing unused imports in `backend/tests/test_url_routing.py` (`pytest`, `django.test.TestCase`).
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check` and `git diff --cached --check` for `nginx-protected-media.conf` -> clean before source commit.
- Source Commit SHA: `95bc45513b56f735540d92aefc6508c08cba34ae`
- Source Commit Timestamp: `2026-07-17T11:14:12+05:30`
- Source Commit Summary: `fix(documents): harden protected media nginx snippet`
- Blocked Items:
  - `nginx` binary is unavailable locally, so full nginx syntax validation could not be run.
  - Scoped backend Ruff remains blocked by pre-existing unused imports in `backend/tests/test_url_routing.py`.
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Active concrete nginx configs should be audited separately when their queued `REQUIRES_RECHECK` items are selected, especially for cache-header parity.
- Status: COMPLETED


## scripts/diagnostics/sync-media.sh

- File Path(s): `scripts/diagnostics/sync-media.sh`
- Module: Documents / media sync diagnostics script
- Total LOC: 371
- Lines Reviewed: 371 plus `scripts/database/db-tools.sh`, `docs/guides/SCRIPTS_README.md`, `scripts/README.md`, deployment media paths, and Django `MEDIA_ROOT`
- Functions Reviewed: 12 shell functions / command branches
- Classes Reviewed: 0
- Validation Improvements: Added strict mode, explicit config validation, absolute path enforcement, unsupported remote-path character rejection, unknown-option rejection, `sync --dry-run` handling, and `sync --delete` rejection.
- Package Replacements: Reused shell built-ins plus existing `ssh`/`rsync`; no new dependency introduced.
- Performance Improvements: Preserved rsync incremental transfer behavior while making failure handling explicit under `set -e`.
- Security Improvements: Corrected stale root-level `media` paths to `backend/media`, quoted SSH/rsync invocations, made SSH/rsync binaries environment-overridable, and blocked unsafe/destructive option paths before network execution.
- Dead Code Removed: None; docs prove this diagnostics script remains live.
- Duplicate Logic Removed: Aligned path contract with `scripts/database/db-tools.sh` rather than maintaining a conflicting media location.
- Tests Added: None; shell-script behavior verified through syntax and non-network command-path checks.
- Verification Results:
  - Dependency scan found live references from `docs/guides/SCRIPTS_README.md` and `scripts/README.md`.
  - Duplicate/path scan found `scripts/database/db-tools.sh` already uses `backend/media`, which this script now matches.
  - `bash -n scripts/diagnostics/sync-media.sh` -> passed.
  - `bash scripts/diagnostics/sync-media.sh` -> usage printed, exit 0.
  - `bash scripts/diagnostics/sync-media.sh download --bad-option` -> rejected before SSH/rsync.
  - `bash scripts/diagnostics/sync-media.sh sync --delete` -> rejected before SSH/rsync.
  - `REMOTE_MEDIA_PATH=relative bash scripts/diagnostics/sync-media.sh status` -> rejected before SSH/rsync.
  - `shfmt -d scripts/diagnostics/sync-media.sh` -> command not found; shell formatter unavailable locally.
  - `shellcheck scripts/diagnostics/sync-media.sh` -> command not found; shell linter unavailable locally.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py -q` -> 14 passed.
  - `.venv/bin/python -m py_compile backend/manage.py backend/lmanagement/settings.py backend/lmanagement/urls.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/lmanagement backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `.venv/bin/ruff check backend/lmanagement/urls.py backend/lmanagement/settings.py backend/tests/test_url_routing.py` -> blocked by pre-existing unused imports in `backend/tests/test_url_routing.py` (`pytest`, `django.test.TestCase`).
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check` and `git diff --cached --check` for `scripts/diagnostics/sync-media.sh` -> clean before source commit.
- Source Commit SHA: `9bddcf84789ce0825b165f34b1db940a44a2532c`
- Source Commit Timestamp: `2026-07-17T11:18:04+05:30`
- Source Commit Summary: `fix(documents): harden media sync diagnostics`
- Blocked Items:
  - `shfmt` and `shellcheck` are unavailable locally.
  - Scoped backend Ruff remains blocked by pre-existing unused imports in `backend/tests/test_url_routing.py`.
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Actual SSH/rsync transfer paths were not executed because they require remote server credentials/network access.
- Status: COMPLETED


## nginx-http-only-tractor.conf

- File Path(s): `nginx-http-only-tractor.conf`
- Module: Documents / tractor HTTP-only nginx bootstrap config
- Total LOC: 30
- Lines Reviewed: 30 plus `scripts/deployment/auto-deploy.sh`, `docs/media-security-cutover.md`, `nginx-license-tractor.conf`, and related nginx config parity
- Functions Reviewed: 0
- Classes Reviewed: 0
- Validation Improvements: Retained the live cert-bootstrap server block and aligned proxy timeout handling with the production nginx config family.
- Package Replacements: None; nginx built-in proxy/header directives remain the correct implementation.
- Performance Improvements: Added explicit client/proxy timeout directives to avoid premature upload/download interruption during bootstrap traffic.
- Security Improvements: Added `proxy_redirect off`, `X-Frame-Options`, `X-Content-Type-Options`, and `Referrer-Policy` headers to the HTTP-only bootstrap config.
- Dead Code Removed: None; dependency analysis confirmed the file is live through `scripts/deployment/auto-deploy.sh` for `165.232.185.220`.
- Duplicate Logic Removed: None; this file is a distinct HTTP-only certbot bootstrap config and should not be merged with TLS nginx configs.
- Tests Added: None; nginx config hardening only.
- Verification Results:
  - Dependency scan found live references in `scripts/deployment/auto-deploy.sh`, deployment documentation, and tractor nginx config references.
  - `nginx -v` -> command not found; local nginx syntax validation unavailable.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py -q` -> 14 passed.
  - `.venv/bin/python -m py_compile backend/manage.py backend/lmanagement/settings.py backend/lmanagement/urls.py backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/lmanagement backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `.venv/bin/ruff check backend/lmanagement/urls.py backend/lmanagement/settings.py backend/tests/test_url_routing.py` -> blocked by pre-existing unused imports in `backend/tests/test_url_routing.py` (`pytest`, `django.test.TestCase`).
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check` and `git diff --cached --check` for `nginx-http-only-tractor.conf` -> clean before source commit.
- Source Commit SHA: `45a2223bc7f7ad1ac954e2c87de62c775cd106ac`
- Source Commit Timestamp: `2026-07-17T11:21:21+05:30`
- Source Commit Summary: `fix(documents): harden tractor http nginx bootstrap`
- Blocked Items:
  - `nginx` binary is unavailable locally, so full nginx syntax validation could not be run.
  - Scoped backend Ruff remains blocked by pre-existing unused imports in `backend/tests/test_url_routing.py`.
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Other active nginx configs remain separate queued Phase 11 `REQUIRES_RECHECK` items and should be audited only when selected.
- Status: COMPLETED


## Legacy Allotment Django Templates

- File Path(s): `backend/apps/allotment/templates/allotment/add.html`, `backend/apps/allotment/templates/allotment/card.html`, `backend/apps/allotment/templates/allotment/delete.html`, `backend/apps/allotment/templates/allotment/generate.html`, `backend/apps/allotment/templates/allotment/item.html`, `backend/apps/allotment/templates/allotment/list.html`, `backend/apps/allotment/templates/allotment/quantity_input.html`, `backend/apps/allotment/templates/allotment/table.html`, `backend/apps/allotment/templates/allotment/value_input.html`, `backend/apps/allotment/templates/allotment/verify.html`, `backend/apps/allotment/templatetags/__init__.py`, `backend/apps/allotment/templatetags/app_tags.py`
- Module: Documents / legacy allotment Django template and tag stack
- Total LOC: 844
- Lines Reviewed: 844 plus `backend/apps/allotment/views.py`, `backend/apps/allotment/urls.py`, `backend/lmanagement/urls.py`, `backend/apps/core/templates/core/list.html`, route tests, and repository-wide template-loader/reference scans
- Functions Reviewed: 8 template tag functions
- Classes Reviewed: 0
- Validation Improvements: Removed orphaned templates containing stale form, URL tag, inline AJAX, and CSRF surfaces that no active Django route renders.
- Package Replacements: None; removed dead Django template/tag code instead of replacing it.
- Performance Improvements: Removed orphaned template tag database lookups and unused template rendering logic from the active codebase.
- Security Improvements: Removed stale legacy URL actions and inline AJAX paths from an otherwise unreachable template surface.
- Dead Code Removed: Deleted 10 legacy allotment templates and the private `app_tags` template tag package.
- Duplicate Logic Removed: Removed duplicate legacy allotment rendering and totaling helpers superseded by active DRF/React allotment flows.
- Tests Added: None; behavior preserved by deletion of verified-dead code.
- Verification Results:
  - Dependency scan found no live `render()`, `render_to_response`, `TemplateResponse`, `template_name`, include/extends, custom tag, URLConf, middleware, signal, management command, test, email/PDF/report/export, dynamic loader, cached path, or third-party runtime path for the deleted allotment templates or `app_tags`.
  - Remaining pre-deletion hits were self-contained stale template URL/include tags plus one orphaned `backend/apps/core/templates/core/list.html` legacy link; no live render path exists for that core template either.
  - `.venv/bin/python -m pytest backend/tests/test_api_allotment.py backend/tests/test_url_routing.py -q` -> 25 passed.
  - `.venv/bin/python -m py_compile backend/apps/allotment/views.py backend/apps/allotment/views_actions.py backend/apps/allotment/views_export.py backend/apps/allotment/urls.py backend/tests/test_api_allotment.py backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/apps/allotment backend/tests/test_api_allotment.py backend/tests/test_url_routing.py` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - `.venv/bin/ruff check backend/apps/allotment backend/tests/test_api_allotment.py backend/tests/test_url_routing.py --select F401,F821,F811,E741,F841` -> blocked by pre-existing unused imports in unchanged allotment modules and `backend/tests/test_url_routing.py`.
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check` and `git diff --cached --check` for source deletions -> clean before source commit.
- Source Commit SHA: `99ed3080ed82f0923fe5538108dca80353cdd5a9`
- Source Commit Timestamp: `2026-07-17T16:04:27+05:30`
- Source Commit Summary: `cleanup(documents): remove dead allotment templates`
- Blocked Items:
  - Scoped backend Ruff remains blocked by pre-existing unused imports in unchanged allotment modules and `backend/tests/test_url_routing.py`.
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - `backend/apps/core/templates/core/list.html` still contains a stale `allotment-add` URL tag, but dependency analysis found no live render path; leave it for its own queued Phase 11 legacy-template audit item.
- Status: COMPLETED


## Production 404 Template

- File Path(s): `backend/templates/404.html`, `backend/tests/test_url_routing.py`
- Module: Documents / Django production error template
- Total LOC: 438 (`404.html`: 86; focused route test module: 352)
- Lines Reviewed: 100 original template lines, 86 replacement template lines, route URLConf, Django template settings, and 352 test lines
- Functions Reviewed: 1 added regression test method
- Classes Reviewed: 1 existing `URLRoutingRegressionTests` class touched for coverage
- Validation Improvements: Added a regression proving `404.html` renders through Django's template loader without runtime context.
- Package Replacements: Removed stale DAdmin/static asset dependency from the template; no new package introduced.
- Performance Improvements: Removed external font fetch, stale CSS bundles, stale JavaScript bundles, and obsolete search form from production 404 responses.
- Security Improvements: Added `noindex,nofollow`, removed external Google Font loading, removed JavaScript execution, and replaced the stale dashboard-relative link with `/`.
- Dead Code Removed: Removed DAdmin wrapper, broken asset references, and unused search form from the active 404 template.
- Duplicate Logic Removed: None; retained Django's conventional `404.html` contract.
- Tests Added: `URLRoutingRegressionTests.test_html_404_template_renders_without_external_assets`
- Verification Results:
  - Dependency scan retained `backend/templates/404.html` because `backend/templates` is in `TEMPLATES["DIRS"]` and Django can load `404.html` by convention for production 404 handling.
  - Remaining `404.html` references are stale links from other queued legacy DAdmin templates, not render dependencies.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py -q` -> 15 passed.
  - `.venv/bin/ruff check backend/tests/test_url_routing.py --select F401,F821,F811,E741,F841` -> clean.
  - `.venv/bin/python -m py_compile backend/tests/test_url_routing.py backend/lmanagement/urls.py backend/lmanagement/settings.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/tests/test_url_routing.py backend/lmanagement` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check` and `git diff --cached --check` for source files -> clean before source commit.
- Source Commit SHA: `d7e55f2ef8b03c4fe95cab4f751641f16fd36892`
- Source Commit Timestamp: `2026-07-17T16:08:27+05:30`
- Source Commit Summary: `fix(documents): harden production 404 template`
- Blocked Items:
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Queued legacy DAdmin templates still link to `404.html`; audit them only when selected by the Phase 11 queue.
- Status: COMPLETED


## Production 500 Template

- File Path(s): `backend/templates/500.html`, `backend/tests/test_url_routing.py`
- Module: Documents / Django production error template
- Total LOC: 452 (`500.html`: 86; focused route test module: 366)
- Lines Reviewed: 90 original template lines, 86 replacement template lines, route URLConf, Django template settings, and 366 test lines
- Functions Reviewed: 1 added regression test method
- Classes Reviewed: 1 existing `URLRoutingRegressionTests` class touched for coverage
- Validation Improvements: Added a regression proving `500.html` renders through Django's template loader without runtime context.
- Package Replacements: Removed stale DAdmin/static asset dependency from the template; no new package introduced.
- Performance Improvements: Removed external font fetch, stale CSS bundles, stale JavaScript bundles, and obsolete dashboard wrapper from production 500 responses.
- Security Improvements: Added `noindex,nofollow`, removed external Google Font loading, removed JavaScript execution, and replaced the stale dashboard-relative link with `/`.
- Dead Code Removed: Removed DAdmin wrapper, broken asset references, and unused script/style dependencies from the active 500 template.
- Duplicate Logic Removed: None; retained Django's conventional `500.html` contract.
- Tests Added: `URLRoutingRegressionTests.test_html_500_template_renders_without_external_assets`
- Verification Results:
  - Dependency scan retained `backend/templates/500.html` because `backend/templates` is in `TEMPLATES["DIRS"]` and Django can load `500.html` by convention for production 500 handling.
  - Remaining `500.html` references are stale links from other queued legacy DAdmin templates, not render dependencies.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py -q` -> 16 passed.
  - `.venv/bin/ruff check backend/tests/test_url_routing.py --select F401,F821,F811,E741,F841` -> clean.
  - `.venv/bin/python -m py_compile backend/tests/test_url_routing.py backend/lmanagement/urls.py backend/lmanagement/settings.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/tests/test_url_routing.py backend/lmanagement` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check` and `git diff --cached --check` for source files -> clean before source commit.
- Source Commit SHA: `6ed96a35cfed4a23c98530b8e232c90d22511876`
- Source Commit Timestamp: `2026-07-17T16:11:22+05:30`
- Source Commit Summary: `fix(documents): harden production 500 template`
- Blocked Items:
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Queued legacy DAdmin templates still link to `500.html`; audit them only when selected by the Phase 11 queue.
- Status: COMPLETED


## Legacy Base/DFIA Template Stack

- File Path(s): `backend/templates/base/main.html`, `backend/templates/blank.html`, `backend/templates/dfia/box.html`, `backend/templates/dfia/list.html`
- Module: Documents / legacy DAdmin Django template stack
- Total LOC: 956
- Lines Reviewed: 956 plus exact template inheritance, Django render/template loader, URLConf, command, test, frontend runtime, and queued legacy-template reference scans
- Functions Reviewed: 3 legacy JavaScript helper functions in `dfia/list.html`
- Classes Reviewed: 0
- Validation Improvements: Removed orphaned templates containing stale URL tags, inline AJAX helpers, and context-dependent filter/pagination paths that no active Django route renders.
- Package Replacements: None; removed verified-dead Django templates instead of replacing them.
- Performance Improvements: Removed an unused base template that loaded multiple stale CSS/JS bundles and external fonts.
- Security Improvements: Removed stale inline AJAX/CSRF JavaScript, broken legacy route links, and external Google Font loading from an unreachable template surface.
- Dead Code Removed: Deleted the legacy DAdmin base template, blank child page, and orphaned DFIA list/box templates.
- Duplicate Logic Removed: Removed duplicate legacy DFIA list/card rendering superseded by active DRF/React license flows.
- Tests Added: None; behavior preserved by deletion of verified-dead templates.
- Verification Results:
  - Dependency scan found no live `render()`, `TemplateResponse`, `template_name`, `get_template()`, `select_template()`, include, URLConf, management command, test, frontend runtime, or third-party runtime path for the deleted templates.
  - Remaining `blank.html` references are stale links inside other queued legacy DAdmin templates and are not live render dependencies.
  - `.venv/bin/python -m pytest backend/tests/test_url_routing.py -q` -> 16 passed.
  - `.venv/bin/ruff check backend/tests/test_url_routing.py --select F401,F821,F811,E741,F841` -> clean.
  - `.venv/bin/python -m py_compile backend/tests/test_url_routing.py backend/lmanagement/urls.py backend/lmanagement/settings.py` -> passed.
  - `.venv/bin/python -m compileall -q backend/tests/test_url_routing.py backend/lmanagement` -> passed.
  - `.venv/bin/python backend/manage.py check` -> no issues.
  - `.venv/bin/python backend/manage.py makemigrations --check --dry-run` -> no changes detected; sandboxed PostgreSQL connection warning only.
  - Security tooling unavailable locally: `.venv/bin` contains no `bandit`, `semgrep`, `pip-audit`, or `safety` executable.
  - `git diff --check` and `git diff --cached --check` for source deletions -> clean before source commit.
- Source Commit SHA: `9d56821b2e08bcf5f9c35ccb54a705c208c6a84d`
- Source Commit Timestamp: `2026-07-17T16:15:04+05:30`
- Source Commit Summary: `cleanup(documents): remove dead base template stack`
- Blocked Items:
  - Security tooling is unavailable locally.
- Remaining Technical Debt:
  - Other queued legacy DAdmin templates still contain static `blank.html` hrefs; audit them only when selected by the Phase 11 queue.
- Status: COMPLETED
