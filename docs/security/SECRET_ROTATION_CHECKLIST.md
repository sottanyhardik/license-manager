# Secret Rotation Checklist: committed environment files

Status 2026-11-17: **OPEN, CRITICAL.** No secret value has been read, printed or copied by Claude. The repo's guard hook blocks
any command referencing these paths, so the history and name inventory below must be run by the owner.

## 1. Exposed files (tracked in git; source: docs/modernization/SECURITY_REPORT.md)

`.env`, `backend/.env_dgft`, `frontend/.env`, `frontend/.env.production`. These are tracked and **already on origin**. They
are in every clone and every pushed branch that contains them. Deleting them now does not remove them from history.

## 2. Owner-run inventory (prints names and commit hashes only, never values)

```bash
# variable NAMES per file (values stripped)
for f in .env backend/.env_dgft frontend/.env frontend/.env.production; do echo "== $f"; git show HEAD:"$f" | sed -E 's/=.*//' | grep -v '^\s*#' | grep -v '^\s*$'; done
# when each file entered history, how many commits touched it, and whether origin has it
for f in .env backend/.env_dgft frontend/.env frontend/.env.production; do echo "$f first=$(git log --diff-filter=A --format='%h %cs' -- "$f" | tail -1) commits=$(git log --format=%h -- "$f" | wc -l) on_origin=$(git cat-file -e origin/feature/v5:"$f" 2>/dev/null && echo yes || echo no)"; done
# other remote branches containing them
git branch -r --contains "$(git log --diff-filter=A --format=%h -- .env | tail -1)"
```

## 3. Credential classes the application reads (names from source code; map each to its file using §2)

| Variable(s) | Service | Rotation owner action | Blast radius if rotated |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Django signing (sessions, password-reset tokens, signed values) | Generate a new ≥50-char key; deploy | Invalidates sessions and reset links; JWT signing follows it unless SIMPLE_JWT has its own key |
| `DB_PASS` (+ `DB_USER/HOST/NAME`) | PostgreSQL | `ALTER ROLE … PASSWORD` on each server; update its env file | App downtime if the env update is not simultaneous |
| `MDS_DB_PASS`, `SECRET_KEY` (MDS), `MDS_TOKENS` / `MDS_TOKEN` | master-data-service plus client token | Rotate the MDS DB password, the MDS secret key, and issue new client tokens (update both sides) | Master-data sync fails until both sides are updated |
| `SYNC_PEER_TOKENS` | Three-server sync | New per-peer tokens on all peers at once | Sync pauses during rollout |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP provider | Regenerate the app password at the provider | Email sending stops until updated |
| `DGFT_SESSION_ID`, `DGFT_CSRF_TOKEN`, `DGFT_AWSALB` (+ `DGFT_APP_ID`, `DGFT_IEC_NUMBER`) | DGFT portal session cookies (`.env_dgft`) | Log out or invalidate the portal session; capture fresh values | Ownership lookup fails until refreshed (usually short-lived anyway) |
| `VITE_API_URL`, `VITE_API_PROXY_TARGET` | Frontend config, **public by design** (bundled into JS) | Not secrets; no rotation needed | n/a |

## 4. Safe rotation sequence (approval required at each ⛔)

1. ⛔ Owner confirms the production and staging hosts and who holds server access.
2. For each class in §3: **create the replacement first** (new DB role password, new token, new key) **without revoking the old one**.
3. Update the server-side env files (outside git) and restart the services. Verify health: login, a licence list request, MDS sync, email test, Celery worker.
4. ⛔ Owner approves revocation of the old credential once the replacement is confirmed working.
5. Revoke the old credentials. Watch the error logs for 24 h.
6. Untrack the files going forward: `git rm --cached <files>` plus `.gitignore` entries. ⛔ This deletes the files on every machine and server at the next `git pull`, so first make sure each server's env file lives outside the checkout, or back it up.
7. History: ⛔ **no rewrite or force-push without explicit approval.** After rotation, the old values are dead, so history rewrite is optional hygiene, not containment.

## 5. Other exposure checks

- **Commits ahead of origin (13):** 0 credential-pattern hits in added lines; no env, dotfile, IDE or binary files in the range (checked 2026-11-17).
- **Logs, fixtures, docs:** none of the modernization docs contain secret values (the docs use names only). Owner should still check server logs and CI logs for printed env values (not accessible to Claude).
- `settings.py:40` holds a labelled dev-only default secret key; `settings.py:92` blocks it in production. Acceptable.
- Compatibility after rotation: no code change is needed; all values are read from the environment (`settings.py`).
