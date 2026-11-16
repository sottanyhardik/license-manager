# OD-06 remediation manifest (repository side)

Status: written **before** any file was changed (OD-06 amended package, owner approval 2026-11-16, condition 2).
Branch: `feature/version5`. Scope is repository-side changes plus local tests only. Nothing here is committed or
pushed, and no remote system, production database or real data is touched.

This document contains **no secret values**. Files were inspected with key-name-only or masked commands
(for example `grep -o '^[A-Za-z_]*='`, or a Python scanner that prints only `len=` and a class such as
`KNOWN-EXPOSED` / `placeholder`). "Known-exposed DB password" means the single 11-character Postgres
application password from the OD-06 assessment, section 2. It is equal to the database and role name, so it
is effectively public.

Related: `docs/security/OD-06-exposure-assessment.md` (findings), `OD-06-rotation-runbook.md` (ops),
`OD-06-history-remediation-assessment.md` (history options, not executed).

## 1. Tracked files that contain live or exposed credentials (HEAD)

| # | File | Contents (key names / classification only) | Planned change | Why functionality is preserved |
|---|---|---|---|---|
| 1 | `backend/setup/Backup & Restore Script` | `pg_dump`/`dropdb`/`createdb`/`pg_restore` recipe. 4 literal `PGPASSWORD=` prefixes, all the known-exposed DB password. | Remove the 4 inline literals. Add a guard line `: "${PGPASSWORD:?...}"` so the recipe stops with a clear message when `PGPASSWORD` is unset. libpq reads `PGPASSWORD` from the environment. The file stays tracked. | Same commands and flags; the password now comes from the operator's environment. |
| 2 | `backend/setup/PostgreSQL Commands` | DROP/CREATE role and DB recipe. `CREATE USER ... WITH PASSWORD '<literal>'` (known-exposed). | Use the psql variable `:'db_password'`, with a `\if :{?db_password}` guard that prints an error and `\quit`s when it is unset. Add a usage comment: `psql -v db_password="$DB_PASS" -f ...`. | Same SQL; the password is supplied at run time. |
| 3 | `backend/setup/reset_lmanagement.sql` | Same pattern, 1 literal (known-exposed). Tracked even though `*.sql` ignores it. | Same psql-variable change. Add a `.gitignore` exception so the required script is explicitly un-ignored. | Same SQL. |
| 4 | `scripts/database/db-tools.sh` | `REMOTE_DB_PASS` and `LOCAL_DB_PASS` assigned the known-exposed literal (lines 27 and 30). Other `PGPASSWORD=` uses reference those variables. | Read `REMOTE_DB_PASS` from the env, and `LOCAL_DB_PASS` from the env with `DB_PASS` as fallback. Add a `require_db_pass` helper, called right before each use, which exits 2 with a clear message when the variable is unset. | Every subcommand behaves the same once the variable is exported. `--help`/usage still works without any password. **Not executed** (it talks to servers). |
| 5 | `scripts/diagnostics/server-health.sh` | Line 141: remote `psql` call with an inline `PGPASSWORD=<known-exposed>`. Other secrets already come from `HEALTH_*` env (`HEALTH_SUDO_PASSWORD`). | Use `HEALTH_DB_PASS` from the env, following the existing `HEALTH_*` convention. When it is unset, the table-count probe is reported as skipped (warn) instead of failing. | The other probes are unchanged. **Not executed** (remote). |
| 6 | `audit_evidence/pass1/BL-EXP/01/query_result` | Line 1 is a captured command transcript with an inline `PGPASSWORD=<known-exposed>`. | Redact that token to `PGPASSWORD=<redacted>`. The query output stays byte-identical. | Evidence content (results) is unchanged; only the credential in the transcript header is redacted. |
| 7 | `docs/modules/PHASE_4E_B_TEST_ENVIRONMENT_AUDIT.md` | Lines 46 and 161 document `DB_PASS` with the known-exposed literal for the local test DB. | Replace it with `<local test DB password>` / `"$DB_PASS"`. | Docs only. |
| 8 | `master-data-service/.env.production.example` | Template. `MDS_DB_PASS` placeholder equals `MDS_DB_USER` (a weak value that people may copy as-is). Other keys are already `REPLACE_*`/generated placeholders. | Change the placeholder to `CHANGE_ME_STRONG_DB_PASSWORD`. | Template only; no code reads it. |

## 2. Sensitive config to untrack and replace with a template

| File | Keys (classification) | Planned change | Why functionality is preserved |
|---|---|---|---|
| `backend/.env_dgft` (474 B, single commit `79a08ac2` 2026-08-31; already ignored by `backend/.gitignore:26` but still tracked) | `DGFT_SESSION_ID`, `DGFT_CSRF_TOKEN`, `DGFT_AWSALB`: **secret** (browser session, CSRF and load-balancer cookies). `DGFT_APP_ID`: **identifier**, required by the ownership lookup (not a credential by itself, but it is sent with the session). `DGFT_IEC_NUMBER`, `DGFT_SCRIP_NUMBER`, `DGFT_SCRIP_ISSUE_DATE`: **identifiers** (business-confidential, not rotatable, not read by any code other than `settings.py`). `DGFT_OWNERSHIP_URL`: **non-secret config** (public URL, equal to the `settings.py` default). | `git rm --cached backend/.env_dgft`. The file **stays on disk locally and stays in git history**, so rotation and ending the DGFT session remain necessary. Add `backend/.env_dgft.example` with every key name: the URL keeps its public value, identifiers get placeholders, secrets are left empty with comments. | `settings.py:27-35` loads `.env_dgft` only `if _env_path.exists()` (`override=False`). Every `DGFT_*` setting has an `os.getenv(..., default)`. `update_license_ownership.get_dgft_ownership_credentials()` and `views_actions.py:466-476` already return a "credentials not configured" error when the values are missing. Tests (`apps/license/tests/test_dgft_settings.py`, `test_update_license_ownership_config.py`) do not depend on the file. The local copy is not deleted. |

**Implementation status (2026-11-16):** `backend/.env_dgft.example` was added. The `git rm --cached backend/.env_dgft`
step was denied by the session permission system for the agent; the **owner ran it** (2026-11-16). The file is untracked,
kept locally, ignored by `backend/.gitignore:26` and the new root rule, and **still present in git history**.

Not untracked, because they are not secret-bearing (condition 4: `git rm --cached` only for proven secret-bearing files):
`.env` (0 bytes), `frontend/.env` (`VITE_API_URL`, localhost, public), `frontend/.env.production` (`VITE_API_URL` empty,
public bundle config). The Vite build reads `.env.production`, so untracking it could change build output.
Recommendation (owner): untrack the empty root `.env` in a later change so that nobody writes secrets into a tracked file.

## 3. Production configuration validation (code)

| File | Change |
|---|---|
| `backend/lmanagement/security_config.py` (new, stdlib only) | Pure evaluator: SECRET_KEY empty / repo dev or placeholder value / Django W009 weakness (<50 chars, <5 unique, `django-insecure-` prefix); DB password empty / equal to DB user or name / repo dev default / common weak value / placeholder; DEBUG on in production; optional `SECURITY_SECRET_DENYLIST_FILE` (must be outside the repo; sha256 hex lines). The repo ships **no** digests and no exposed values. |
| `backend/lmanagement/checks.py` (new) | Django system checks tagged `security` + `deploy`: errors under `manage.py check --deploy`; at startup in non-production with `DEBUG=False` and not testing, they are advisory warnings. |
| `backend/lmanagement/settings.py` | `_validate_production_security()` (existing import-time fail-closed guard, `DJANGO_ENVIRONMENT=production`) now calls the shared evaluator. The old `len < 32` check is replaced by the stricter W009 criteria. The dev default key constant is unchanged. No `SECRET_KEY_FALLBACKS`. |
| `backend/apps/core/apps.py` | `ready()` imports `lmanagement.checks` to register the checks. |
| `backend/.env.example` | Document `SECURITY_SECRET_DENYLIST_FILE` (key name only, commented). |

Dev, test and CI keep working. The guard is enforced only when `DJANGO_ENVIRONMENT` is `production`/`prod` (the
project's existing switch). CI sets neither `DJANGO_ENVIRONMENT` nor `--deploy`.

## 4. Management commands (built and tested; never executed outside tests)

| File | Purpose |
|---|---|
| `backend/apps/accounts/security_actions.py` (new) | Service: select affected users, set unusable passwords, blacklist outstanding refresh tokens, delete sessions, write `core.ActivityLog` audit rows. |
| `backend/apps/accounts/management/commands/force_password_reset.py` (new) | `--joined-on-or-before YYYY-MM-DD` and/or `--usernames-file`, `--include-superusers`, `--dry-run` (default) / `--execute`. |
| `backend/apps/accounts/management/commands/invalidate_all_sessions.py` (new) | `--dry-run` (default) / `--execute`, `--flush-expired`. |
| `backend/tests/test_od06_security_config.py`, `backend/tests/test_od06_credential_commands.py` (new) | Tests on the local test DB (`TEST_DB_NAME=test_lmanagement_od06`). They sit in `backend/tests/` because that is the path the gate runs (`apps/accounts/tests` is not in the gate). |
| `docs/guides/MANAGEMENT_COMMANDS.md` | Document the two commands. |

Cut-off for "accounts present in the exposed dumps", from git metadata only (`git log --all --format='%h %ad'
--diff-filter=AM` on the dump paths in the assessment; dump contents were never read): the latest dump commit is
`58fa4691`, 2025-12-17T23:57:30+05:30, which added `remote_db_backup_20251216_141927.sql` and
`remote_db_backup_20251217_161720.sql`. The recommended option is `--joined-on-or-before 2025-12-17`.

## 5. `.gitignore` (root): targeted rules and audited matches

Audit commands: `git ls-files -c -i -x '<pattern>'` (tracked) and `git ls-files -o -i -x '<pattern>'` (untracked),
plus `git check-ignore -v --no-index` for templates. Run on 2026-11-16 before the change.

| Rule | Tracked matches | Untracked matches | Exceptions | Effect |
|---|---|---|---|---|
| `.env_dgft` | 1 (`backend/.env_dgft`, being untracked) | 0 | Not needed: `backend/.env_dgft.example` does not match (verified with `check-ignore`) | Root-level backstop for `backend/.gitignore:26` |
| `*.dump` | 0 | 0 | — | Stops `pg_dump -Fc` dumps (history had `lmanagement.dump`, `lmanagement_dump.dump`) |
| `*.pgsql` | 0 | 0 | — | History had `dbexport.pgsql` |
| `*.psql` | 0 | 0 | — | History had `lmanagement.psql` |
| `lmanagement*.backup` | 0 | 0 | — | Output name of the `backend/setup/Backup & Restore Script` recipe |
| `/artifacts/` | 94 (Playwright outputs, 34 PDFs; **stay tracked**, not removed) | 0 | — | New e2e outputs are no longer addable |
| `/adf/` | 18 PDFs (**stay tracked**, not removed) | 0 | — | New licence copies are no longer addable |
| `!backend/setup/reset_lmanagement.sql` | 1 (explicit exception to the existing `*.sql`) | — | itself | Required script stays explicitly un-ignored |

Rejected as too broad (condition 4): `.env*`, `*.bak`, extra `*.sql` rules. Existing `*.sql`,
`remote_db_backup_*.sql`, `/backups/` and `deploy-secrets.env` already cover the current untracked dumps
(4 files under `backups/`, all ignored). Gitignore does not untrack anything. Tracked PDFs are unaffected
(no `git rm` on any PDF, condition 9).

## 6. Docs

`docs/security/OD-06-rotation-runbook.md` (hard-cut rotation runbook), `docs/security/OD-06-history-remediation-assessment.md`
(options, not executed), this manifest.

## 7. OPEN: owner review (not opened, read, grepped or edited; condition 10)

| Item | Why |
|---|---|
| The root deploy script named `auto-…` in the assessment, `deploy-secrets.env.example`, the `update_db_from_server` scripts (`scripts/…`, `backend/setup/…` in history), everything under `backend/deploy/` and `scripts/deploy*` | Deploy tooling. The assessment found `-G` password hits in these paths |
| `backend/setup/deploy` (tracked file, name only seen via `git ls-files`) | Deploy tooling by name, so treated as in scope of condition 10 |
| Commits `119e5572`, `60d189c7`, `b2f26811`, `325f27f2`, `2ad9a063`, `ef018576`, `05a49907` | Deploy-path hits from the assessment, section 2 |

## 8. Out of scope / remaining (see the final report)

- Every exposed value is still in git history (dumps, the 2019 `SECRET_KEY`, the DB password, `.env_dgft`). Untracking
  and scrubbing HEAD do **not** remove them, so rotation (runbook) is mandatory.
- MDS has no production guard against its dev `SECRET_KEY` default (`mds/settings.py`). Follow-up for the MDS owner.
- `frontend/.env*` and the root `.env` stay tracked (not secret-bearing).
- CI and the local gate use the known-exposed literal as the password of their **ephemeral** Postgres containers/local
  DB. That is acceptable for throwaway test DBs, and the new guard rejects it for production.
