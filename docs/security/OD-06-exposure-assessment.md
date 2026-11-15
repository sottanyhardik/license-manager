# OD-06 — Secrets & sensitive-document exposure assessment

Status: investigation only (OD-06, approved 2026-11-15). Nothing was rotated, untracked, deleted or
rewritten. **No secret values are in this document.** Findings are given as key names, paths, commit
hashes, sizes and counts. Branch inspected: `feature/version5` (6 commits ahead of `origin/develop`).
Verifies SEC-01 and SEC-02 in `docs/erp-transformation/08-security-assessment.md`.

## 0. Headline

SEC-01 understated the problem. The four tracked env files matter less than the **history**:

1. **Full production-style database dumps were committed and pushed** (2019–2025). They include
   `remote_db_backup_2025121*.sql` (5 files, up to 62 MB each) and 9 older dumps. All of them
   are reachable from `origin/develop`, `origin/master` and `origin/legacy/archive-baseline-2026-11-14`.
   They contain user password hashes, 3,457 `django_session` rows, JWT outstanding tokens,
   879 companies, 2,067 licences and 18,534 BOEs (row counts from `remote_db_backup_20251216_141927.sql`).
2. **One Postgres application password** was committed as a literal from 2019-07-19 (`c02d5b32`,
   `lmanagement/settings.py`) to at least 2026-07-15 (server/DB scripts). It is the same value in
   every place checked, and it is trivially guessable. **Likely active.**
3. **A real Django `SECRET_KEY`** was hard-coded in `lmanagement/settings.py` from `c02d5b32`
   (2019-07-19) until `7a449249` (2025-11-04). A second, `insecure`-style literal key sat in
   `setup-labdhi-server.sh` (`06cf446e`, 2025-12-04 → removed `9ad5454f`, 2026-07-15).
4. `backend/.env_dgft` (tracked, `79a08ac2`, 2026-08-31) holds DGFT browser-session credentials and the
   company's IEC/scrip identifiers. The session values are probably expired by now, but the identifiers are business data.

## 1. Tracked env / config files (HEAD)

`git ls-files` matches for `.env*`, `*.pem`, `*.key`, `*secret*`, `*credential*`:

| Path | Bytes | Key names (values not shown) | Class | First / last commit | Ignored now? |
|---|---|---|---|---|---|
| `.env` | 0 | none (always empty) | n/a | `23f72f84` 2026-09-28 (only commit; `--follow` hits before it are unrelated empty-file copies) | **No** |
| `backend/.env_dgft` | 474 | `DGFT_OWNERSHIP_URL`, `DGFT_SCRIP_NUMBER`, `DGFT_SCRIP_ISSUE_DATE`, `DGFT_IEC_NUMBER`, `DGFT_APP_ID`, `DGFT_SESSION_ID`, `DGFT_CSRF_TOKEN`, `DGFT_AWSALB` (all non-empty) | **Secret** (session/CSRF/ALB cookie) + business identifiers (IEC, scrip no., app id) | `79a08ac2` 2026-08-31 (single commit) | Yes (`backend/.gitignore:26`), but still tracked: it was added in the same commit as the ignore rule |
| `frontend/.env` | 35 | `VITE_API_URL` (localhost value) | Public frontend config | `b8102427` 2025-11-15 → `13166aad` 2026-10-14 | No |
| `frontend/.env.production` | 233 | `VITE_API_URL` (empty), 3 comment lines | Public frontend config | `1b6354e8` 2026-05-13 | No |
| `*.env.example` (5 files), `deploy-secrets.env.example` | — | key names + `CHANGE_ME` placeholders | Templates (fine) | — | No (intended) |
| `backend/apps/core/sync/credentials.py`, migration `0017_hash_sync_peer_credentials.py` | — | code only; peer tokens stored hashed (`make_password`) | Non-secret | — | — |

All `VITE_*` values ship in the browser bundle by design, so they are not secrets. The root `.gitignore` has no
`.env` / `.env.*` rule (only `.env.local`, `.env.*.local`, `deploy-secrets.env`).

Secret-like paths that exist **only in history** (deleted from HEAD but still in every clone):

| Path(s) | Added → deleted | Size | Content type (counts only) |
|---|---|---|---|
| `remote_db_backup_20251209_112849.sql`, `…_172630.sql` | `f596b9db` 2025-12-09 → `c7f72034` 2025-12-25 | 7.7 MB, 59 MB | pg_dump plain; users, sessions, JWT outstanding tokens, all business tables |
| `remote_db_backup_20251210_233659.sql` | `a824387a` 2025-12-10 → `c7f72034` | 7.7 MB | same |
| `remote_db_backup_20251216_141927.sql`, `…20251217_161720.sql` | `58fa4691` 2025-12-17 → `c7f72034` | 62 MB, 7.8 MB | same (66 tables) |
| `lmanagement_backup.sql` | `650bd0ed` 2024-08-22 → `6c61eb0a` 2025-04-01 | 12.4 MB | plain dump, 48 tables, password hashes |
| `lmanagement.dump`, `lmanagement_dump.dump` | `35f131cf` / `e0c087c5` 2025-04 → `23977eb8` / `442e834b` | 4.2 MB each | pg_dump custom format (compressed) |
| `29_12_19.sql`, `dump_name.sql`, `dbexport.pgsql`, `lmanagement.sql`, `lmanagement.psql`, `abc.json`, `db.json`, `basic_dump.json` | 2019–2020 | 2–3 MB each | early dumps and fixtures, incl. password hashes and sessions |
| `id_rsa.pub` | `8d031055` 2021-01-15 → `ade74c8b` 2021-10-18 | 593 B | SSH **public** key (no private key found) |
| `Release.key`, `backend/Release.key` | 2022 → 2026-05-11 | 0 B | empty |

`.gitignore` now covers `*.sql` and `remote_db_backup_*.sql`, which stops new dumps from being added. It
does nothing about history. `*.dump`, `*.pgsql`, `*.psql` and `*.bak` are **not** ignored.

## 2. History scan (2,674 commits, 9 contributors, `.git` = 343 MB)

**gitleaks 8.30.1** (already installed): `gitleaks git --redact=100`, JSON report written to `/tmp` and not kept.
It found 12,084 findings:

| Rule | Count | Where |
|---|---|---|
| generic-api-key | 11,310 | `public.django_session` rows inside the dumps above |
| jwt | 698 | `public.token_blacklist_outstandingtoken` rows in `remote_db_backup_*` |
| generic-api-key | 55 | `contenttypes.contenttype` in 2019 JSON fixtures (false positive) |
| github-app-token | 6 | substrings of base64 session data in `django_session` (very likely false positive) |
| curl-auth-header | 14 | `AUTOPLAN_API_EXAMPLES.md` (tracked, `e4cdf2f2`), `debug_401.md` (history, `4b73a515`): placeholders (`TOKEN`, `YOUR_TOKEN`) |
| generic-api-key | 1 | `backend/apps/core/models.py:401` (`60d189c7`): a docstring, false positive |

Gitleaks does not recognise the custom DGFT keys or the literal DB password. Targeted `git log -G`
scans, excluding dumps and with values never printed, found:

| Pattern | Result (commit · path) |
|---|---|
| AWS key `AKIA…` | none |
| Private-key headers (`BEGIN … PRIVATE KEY`) | none |
| URL with embedded credentials (`postgres://u:p@`, redis, amqp) | `adc54409` `backend/apps/accounts/management/commands/migrate_auth.py`; `a5538438` `backend/apps/accounts/tests.py`. Not value-checked; owner to confirm whether these are test placeholders |
| Django `SECRET_KEY` literal (≥20 chars) | **`c02d5b32` → `7a449249` `lmanagement/settings.py` (real-looking, 52 chars, live 2019-07-19 → 2025-11-04)**; `06cf446e` `setup-labdhi-server.sh` (38 chars, `insecure`-style); `60d189c7` `backend/lmanagement/settings.py` (current dev default; prod guard rejects it); `a045cbb3` `mds-client/tests/settings.py`, `0c74c743` `scripts/dev/quality-gate.sh` (test-only) |
| DB password literal (`DB_PASS`/`DB_PASSWORD`/`'PASSWORD':`) | **One 11-char value, identical in all of:** `c02d5b32`/`f6daa3ab` `lmanagement/settings.py`, `f4ee35b2` `setup/update_db_from_server.sh`, `06cf446e` `setup-labdhi-server.sh` (supervisor `environment=` line), `36472756` `download-and-load-db.sh`, `079ef516` `db-tools.sh`, `9ad5454f` `backend/setup/…update_db_from_server.sh`. The value is low-entropy and also appears as an ordinary identifier in 158 tracked files, so treat it as public |
| Same `-G` hits in deploy-tooling paths | `119e5572`, `60d189c7`, `b2f26811`, `325f27f2`, `2ad9a063` (`auto-deploy.sh`, `update_db_from_server.sh` under `scripts/`), `ef018576`/`05a49907` `deploy-secrets.env.example`. **Not inspected**: the repo's bash guard blocks deploy paths. Owner to check |
| `MDS_TOKEN` literals | `a045cbb3` `mds-client/mds_client/settings.py` (placeholder-like), `d4bca314`, `a5538438` (tests). Test values, likely synthetic |

## 3. Are the exposed credentials still active?

The backend now reads (`backend/lmanagement/settings.py`): `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASS`,
`DB_HOST`, `DB_PORT`, `REDIS_URL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `MDS_TOKEN`, `SYNC_PEER_TOKENS`,
`DGFT_*` (8 keys, from process env or `backend/.env_dgft` via `load_dotenv(override=False)`), plus
non-secret flags. The templates (`backend/.env.example`, `deploy-secrets.env.example`,
`master-data-service/.env.production.example`) use the same names plus `DATABASE_URL`,
`CELERY_BROKER_URL`, `MDS_DB_PASS`, `MDS_TOKENS`. `backend/deploy/` contains only `celery.service`.
No login or credential test was attempted.

| Credential (key name · system) | Exposure | Assessment | What the owner must check |
|---|---|---|---|
| `DB_PASS` · Postgres app role (prod, the labdhi server, any DB-sync source) | literal 2019 → 2026, pushed | **Likely active** (unchanged across 7 years and several servers) | Is the prod/labdhi DB role still on this password? Is Postgres reachable from outside (`listen_addresses`, `pg_hba.conf`, firewall)? |
| Django `SECRET_KEY` (2019 literal) · backend prod | in `settings.py` 2019-07-19 → 2025-11-04 | **Unknown → likely active if prod never set `DJANGO_SECRET_KEY`** | On the server, compare the prod key to the historical literal by hash only. Rotate either way (cheap, see §6) |
| `SECRET_KEY` (`insecure` literal) · labdhi server | `06cf446e` → `9ad5454f` | Unknown | Same check on the labdhi host's supervisor/env |
| User password hashes · `auth_user`/`accounts_user` | dumps up to 2025-12-17 (3 hashed rows in latest dump) | **Likely active** for any account whose password has not changed | Force a reset for every account present at 2025-12-17. Hashes can be cracked offline |
| Sessions / JWTs · backend | 3,457 session rows, 698 outstanding JWTs (Dec 2025) | **Likely stale**: refresh lifetime is 7 days (`SIMPLE_JWT`, settings.py:335), signed with `SECRET_KEY` | Rotating `SECRET_KEY` and flushing `django_session` removes residual risk |
| `DGFT_SESSION_ID`, `DGFT_CSRF_TOKEN`, `DGFT_AWSALB` · DGFT portal | `79a08ac2` 2026-08-31 | **Likely stale** (short-lived browser cookies, per the comment at settings.py:24-26) | Log out of that DGFT session and confirm no long-lived DGFT token is used |
| `DGFT_IEC_NUMBER`, `DGFT_SCRIP_NUMBER`, `DGFT_APP_ID` · DGFT | same | Not rotatable (identifiers); business-confidential | Accept or remove |
| `EMAIL_HOST_PASSWORD`, `MDS_TOKEN(S)`, `SYNC_PEER_TOKENS`, `MDS_DB_PASS`, Redis | no real-looking literal found outside the deploy paths not inspected | **Unknown** | Review the deploy-script commits listed in §2 |

## 4. Repository exposure

- Remote: `origin` = `git@github.com:sottanyhardik/license-manager.git` (SSH; no credentials embedded in the URL).
- Visibility (public or private), forks, collaborators with read access, open PRs: **unknown. The owner must confirm**
  (`gh` is not authenticated, and no network check was made). If the repo is or ever was public, treat everything in
  §1–§3 as published.
- 9 distinct commit authors (`git shortlog -sn --all`). Every one of them, and every machine or CI runner that
  cloned the repo, holds a full copy of the dumps.
- Sensitive commits are on `origin/develop`, `origin/master` and `origin/legacy/archive-baseline-2026-11-14`.

## 5. Customs PDFs and sensitive documents

There are 327 tracked document files (322 PDF, 3 CSV, 2 DOCX), about 228 MB on disk. 491 PDF/XLSX/CSV paths appear in history.

| Directory | Files | Filename pattern | Referenced by code/tests? | Assessment |
|---|---|---|---|---|
| `backend/DFIA_COPY/` | 210 PDF | all named by 10-digit number (licence-number shape) | No code reads the directory (only `.gitignore:95` and `.idea`). Some stems match licence numbers used in tests, but the files are not loaded | **Real DFIA licence copies (likely).** Gitignored, yet still tracked (`46374a70` 2025-12-07 → `64e87022` 2026-04-17) |
| `exc_pdf/` | 59 PDF | `exchange_rate (N).pdf` | No | Probably public customs exchange-rate notifications; low sensitivity (`e77cc2cb` 2026-05-14) |
| `adf/` | 18 PDF | 10-digit numeric names | No | Likely real licence/ADF documents (`d89d9d91` 2026-10-08) |
| `artifacts/` | 34 PDF (+ txt) | dirs and files named after licence numbers; ledger and invoice exports | Written by Playwright specs (`frontend/e2e/*download*.spec.ts`, `financial-ledger-invoices.spec.ts` save to `../artifacts/`), which are outputs, not inputs | **Real-data e2e outputs committed by accident** (`79a08ac2` → `0da86766`). `artifacts/` is not ignored |
| repo root | 1 PDF | company-name + number filename | No | SEC-02 confirmed. Likely a real customer document (`ac5af453` 2026-08-04) |
| `backend/tests/fixtures/ledgers/` | 3 CSV (L1, L2, l3; 18–21 rows) | ledger exports | **Yes**: `backend/tests/test_ledger_parser.py` and ledger tests | Needed by tests. `L1.csv` contains 2 licence-number-shaped tokens and should be checked for real data |
| `backend/extra/` | 2 DOCX | consent / request letter templates | No | Probably templates; owner to confirm |
| History only | 84 root, 62 `Qr/`, 5 `NR/`, 4+2 `Reports/`/`REPORTS/`, others | — | — | Deleted from HEAD but still in history |

Retention question for the owner (not a legal assertion): Indian Customs/DGFT record-keeping obligations may require keeping licence and BOE copies for
a statutory period. Even if they do, **a source-code repository is not the place to keep them.** Does the business
have a retention obligation, and where is the system of record (DMS, the app's `media/` storage, or backups)?

## 6. Recommendations (instructions only; nothing below has been executed)

**6.1 Rotate (urgent first).** Rotation is independent of any history rewrite and should happen even if history is left alone.
1. Postgres app-role password (`DB_PASS`) on prod, labdhi and any sync source. Then update the server env, Celery and supervisor.
   Restrict `pg_hba.conf` and the firewall to the app host.
2. `DJANGO_SECRET_KEY` on every backend host (and MDS `SECRET_KEY`). There is no persistent data encrypted with it (only
   sessions, JWTs and password-reset tokens are signed), so the impact is limited to a forced re-login. Afterwards, flush `django_session` and the token blacklist tables. This is a data operation and needs approval.
3. Force a password reset for all users present in the 2025-12 dumps. This matters most for admin and superuser accounts.
4. Review the deploy-script commits in §2. Rotate `EMAIL_HOST_PASSWORD`, `MDS_TOKEN(S)`, `SYNC_PEER_TOKENS`, `MDS_DB_PASS` and the Redis
   password if any real values were committed there.
5. DGFT: end the committed portal session, and from now on keep `DGFT_*` only in server env or an untracked `backend/.env_dgft`.

**6.2 Untrack safely.** This keeps the files on disk and needs a feature branch plus approval to push.
```
git rm --cached backend/.env_dgft frontend/.env frontend/.env.production .env
git rm -r --cached backend/DFIA_COPY adf artifacts "<root company PDF>"
# exc_pdf/: keep only if confirmed public; otherwise move it out of the repo too
```
Add to the root `.gitignore`:
```
.env
.env.*
!.env.example
!*.env.example
**/.env_dgft
*.dump
*.pgsql
*.psql
*.bak
/artifacts/
/adf/
```
Add `backend/.env_dgft.example` and `frontend/.env.production.example` listing **key names only**.
`backend/.env.example` already covers the backend. Add a gitleaks pre-commit hook and a CI job (`gitleaks git --redact`).

**6.3 History rewrite: impact assessment.**
- Tool: `git filter-repo --invert-paths` with a path list of the dumps, `backend/.env_dgft`, document directories and
  setup scripts, plus `--replace-text` for the DB password and the 2019 `SECRET_KEY`.
- Every commit from 2019-07-19 onward gets a new hash. 2,674 commits and 9 local/remote branches would be rewritten.
- **197 distinct real commit hashes are cited in 69 tracked Markdown files** (mostly `docs/audit/`, `docs/modules/`,
  `docs/erp-transformation/`, `.claude/memory/`). Every one of those references would break unless they are remapped
  from filter-repo's `commit-map`.
- All 9 contributors and every server or CI checkout must re-clone. Old clones re-introduce the data if anyone pushes from them.
- Requires a force-push to `develop`, `master` and `legacy/archive-baseline-2026-11-14`, and closing or rebasing open PRs (count unknown).
- CI caches (`actions/setup-*` npm/pip, keyed on lockfiles) hold no repo content, so the impact there is low.
- GitHub keeps PR refs, cached views and forks. Purging those requires a GitHub Support request, and forks are outside the owner's control.
- Benefit: `.git` drops well below 343 MB. More than 160 MB is the 2025 dumps alone.
- **Recommendation:** rotate first (6.1), because rotation neutralises the credentials whether or not history is rewritten.
  If the repo is private and has a small, known set of collaborators, a rewrite mainly protects the business data and
  password hashes in the dumps. That is still worth doing, as **one planned operation** with a commit-map-based doc
  update, a freeze window and a re-clone instruction. If the repo is or was public, do the rewrite plus a GitHub Support
  purge, and assume the data has already been copied.

**6.4 Test documents.** Tests only depend on `backend/tests/fixtures/ledgers/*.csv`. Replace any real
licence/IEC/company values in them with synthetic ones (fake 10-digit licence numbers, a dummy IEC and an "ACME Exports"-style party),
and generate e2e PDFs under an ignored `artifacts/` directory at test time. No committed PDF is needed as a test input.

## 7. Owner decisions needed

1. **Visibility**: is or was the GitHub repo public? Who has access, and are there forks?
2. **Rotate now?** The DB password, `DJANGO_SECRET_KEY` (all hosts) and a forced user-password reset. Recommended: yes, immediately.
3. **Flush sessions and the JWT blacklist after the key rotation?** This is a data operation and needs approval.
4. **Untrack** the env files, `backend/DFIA_COPY/`, `adf/`, `artifacts/` and the root PDF, and add the `.gitignore` rules (§6.2)?
5. **Rewrite history** with `git filter-repo` (§6.3), accepting a force-push, re-clones and 197 broken doc hash references
   unless they are remapped? If yes, choose a freeze window.
6. **Documents**: is there a statutory retention requirement, and where should the PDFs live (DMS, `media/` storage, encrypted
   backup)? Is `exc_pdf/` public material that can stay?
7. **Deploy-script commits** (§2) were not inspected because of the repo guard. Should the owner review them, or approve inspection?
