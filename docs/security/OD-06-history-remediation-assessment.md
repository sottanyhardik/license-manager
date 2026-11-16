# OD-06: git history remediation assessment (NOT executed)

Status: assessment only. No history was rewritten, nothing was force-pushed, and no PDF was removed. The repo's
bash guard blocks `git filter-repo`/`filter-branch` by design, so this needs an explicit owner decision and an
owner-run operation. There are no secret values in this document.

Facts (from `docs/security/OD-06-exposure-assessment.md`, 2026-11-15): **2,674 commits**, **9 contributors**,
`.git` = 343 MB (over 160 MB of that is the 2025 dumps). Sensitive blobs are reachable from `origin/develop`,
`origin/master` and `origin/legacy/archive-baseline-2026-11-14`. **197 distinct commit hashes are cited in 69 tracked
Markdown files.**

## 1. Options

| Option | What it does | Pros | Cons |
|---|---|---|---|
| A. No rewrite (rotate only) | Keep history and neutralise the credentials by rotation (`OD-06-rotation-runbook.md`) | No disruption; doc hash references stay valid | The dumps (business data, password hashes, PII-like data) stay readable by anyone with a clone, forever |
| B. `git filter-repo` targeted purge (recommended tool) | `--invert-paths --paths-from-file purge-paths.txt` plus `--replace-text` for literal credentials | Precise, fast, keeps everything else, writes a `commit-map` for remapping doc references | Every commit from 2019-07-19 onward gets a new hash; force-push; everyone re-clones |
| C. BFG Repo-Cleaner | `--delete-files` / `--replace-text` | Simple | Coarser (filename-based, protects HEAD by default), no path-precise control, no commit-map in the same form; less suitable here |

## 2. Exact path list to purge (option B, `purge-paths.txt`)

Dumps (history only; already deleted from HEAD):
```
remote_db_backup_20251209_112849.sql
remote_db_backup_20251209_172630.sql
remote_db_backup_20251210_233659.sql
remote_db_backup_20251216_141927.sql
remote_db_backup_20251217_161720.sql
lmanagement_backup.sql
lmanagement.dump
lmanagement_dump.dump
29_12_19.sql
dump_name.sql
dbexport.pgsql
lmanagement.sql
lmanagement.psql
abc.json
db.json
basic_dump.json
```
Secret-bearing config:
```
backend/.env_dgft
```
`--replace-text` (expressions file kept **outside** the repo, never committed): the literal 11-character DB password
in `lmanagement/settings.py`, the setup/DB scripts listed in the assessment §2 and `backend/setup/*`; the 2019 52-char
`SECRET_KEY` (`lmanagement/settings.py`, `c02d5b32`→`7a449249`); the `insecure`-style key (`setup-labdhi-server.sh`).
**Caution:** the DB password value is also an ordinary identifier (the DB/role name) in 158 tracked files. A plain
`--replace-text` of that value would corrupt code and docs. Use **regex replacements anchored to the assignment
context only** (for example `PGPASSWORD=`, `DB_PASS=`, `'PASSWORD': '`, `WITH PASSWORD '`), and review the result
with a diff before you push.

Documents (owner decision, because of the retention question in the assessment §5). PDFs must **not** be dropped
from HEAD (OD-06 condition 9). If the owner decides to purge them from history, they must first be archived to the
system of record (DMS/`media/`/encrypted backup). History-only document paths: 84 root PDFs, `Qr/`, `NR/`, `Reports/`,
`REPORTS/`. Tracked ones: `backend/DFIA_COPY/`, `adf/`, `artifacts/`, root company PDF. **Not included** by default.

Not included: `id_rsa.pub` (public key, harmless), `Release.key` (empty), and deploy-tooling paths (owner review
pending, OD-06 manifest §7). The owner may add the deploy commits' files after that review.

## 3. Impact

- **Every commit hash from 2019-07-19 onward changes** (practically all 2,674 commits), along with every branch and
  tag: `develop`, `master`, `legacy/archive-baseline-2026-11-14`, `feature/*`.
- **Force-push** to protected branches (temporarily lift branch protection) and close or rebase every open PR (count
  unknown).
- **9 contributors and every server or CI checkout must re-clone.** Anyone who pushes from an old clone brings the
  data back. Announce a freeze, and reject pushes containing the old root commit (a server-side hook or a check that
  the old SHAs are absent).
- **197 commit hashes cited in 69 Markdown files** (`docs/audit/`, `docs/modules/`, `docs/erp-transformation/`,
  `.claude/memory/`, …) go stale. Remap them with filter-repo's `.git/filter-repo/commit-map` (old→new), using a
  scripted find/replace over tracked `*.md` in the **same** rewrite (`--replace-text` cannot see the new hashes,
  so do it as a follow-up commit right after the rewrite, before the force-push).
- **GitHub keeps** `refs/pull/*` heads, cached views, and any forks. Purging them requires a **GitHub Support** request
  (sensitive-data removal) after the force-push. Forks are outside the owner's control.
- CI caches (setup-* npm/pip, keyed on lockfiles) hold no repo content, so their impact is low. Invalidate them anyway.
- Benefit: the repository shrinks by more than 160 MB, and the business data and password hashes stop being
  distributed to every new clone.

## 4. Prerequisites (all required before any rewrite)

1. **Rotation is complete in every environment** (`OD-06-rotation-runbook.md`). A rewrite never replaces it.
2. **The owner confirms repository visibility** (public now or ever?), the collaborator list and the forks. If it is
   or was public, assume the data is already copied, and the rewrite is mainly hygiene plus a GitHub Support purge.
3. Owner decisions on documents (retention, system of record) and on the deploy-tooling review (manifest §7).
4. Freeze window agreed; all open PRs merged or parked; contributor list notified with the re-clone instructions.
5. A full mirror backup (`git clone --mirror`) stored **offline and encrypted**, because it contains the same secrets.
   Destroy it after the agreed retention period.

## 5. Recommendation

1. **Now:** option A (rotate) in all environments. Mandatory, and independent of everything below.
2. **Then**, if the owner confirms a private repo with a known set of collaborators, do **option B as one planned
   operation**: purge the dump paths and `backend/.env_dgft`, apply context-anchored `--replace-text` for the
   literals, remap the doc hashes in the same window, force-push, file a GitHub Support purge, and have everyone
   re-clone. Option C (BFG) is not recommended, because it lacks path precision and the commit-map workflow.
3. If the repo is or was public: do the same, and in addition treat all dumped data as disclosed (owner/legal
   assessment of notification duties).

Indicative commands, for the owner to run in a fresh mirror clone, **not here**:
```bash
git clone --mirror <origin> lm-rewrite.git && cd lm-rewrite.git
git filter-repo --invert-paths --paths-from-file ../purge-paths.txt --replace-text ../replacements.txt
# remap doc hashes from filter-repo/commit-map in a working clone, commit, then:
git push --force --mirror origin   # owner only, after sign-off
```
