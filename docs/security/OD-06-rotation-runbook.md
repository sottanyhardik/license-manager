# OD-06: hard-cut credential rotation runbook

Status: **prepared, not executed.** This is for ops/the owner to run. It contains no secret values.
Why rotation is mandatory: the DB application password, a 2019 `SECRET_KEY` and full database dumps (password
hashes, sessions, JWTs) are in git history (`docs/security/OD-06-exposure-assessment.md`). Untracking files or
scrubbing HEAD does **not** remove anything from history, clones, forks or GitHub caches. Rotation is what
neutralises the exposure, so it is required **whatever** is decided about a history rewrite.

Strategy: **hard cut.** No `SECRET_KEY_FALLBACKS` (deliberately not configured). The old key stops being accepted
at the moment of the restart.

Order: **staging first** (full run, verification, sign-off), **then production**, then any other backend host (for
example the labdhi/tractor servers named in the assessment) with the same procedure. Each environment gets its
**own** new values. Never reuse a value across environments.

## 0. Preconditions (per environment)

- [ ] Owner approval for this environment and a maintenance window (expect forced re-login for everyone).
- [ ] The deploy that contains the OD-06 code is installed (`lmanagement/security_config.py`, `lmanagement/checks.py`,
      the commands `force_password_reset` and `invalidate_all_sessions`).
      Note: with `DJANGO_ENVIRONMENT=production` this code **refuses to start** on a weak, placeholder or
      denylisted `SECRET_KEY`/DB password. Rotate (steps 2–3) **before or together with** this deploy, not after.
- [ ] A fresh DB backup, stored outside the repo (never commit dumps).
- [ ] You know where each process reads its env: the supervisor `environment=` line or `EnvironmentFile=`, systemd
      units, the server-side env file. **The deploy-tooling files are under owner review (OD-06 manifest §7) and
      are not described here.**
- [ ] Generate new values on the server, never on a laptop or in chat:
      `python -c 'import secrets; print(secrets.token_urlsafe(64))'` (SECRET_KEY, 86 chars) and
      `python -c 'import secrets; print(secrets.token_urlsafe(32))'` (DB password).

## 1. Inventory: everything that must share the new values

| Process / consumer | Reads | Notes |
|---|---|---|
| Gunicorn app instance(s) (supervisor `[program:dgftglobalexim]` per `backend/setup/supervisord.conf`, or systemd) | `DJANGO_SECRET_KEY`, `DB_PASS` | Every worker of every app instance on every host behind the load balancer |
| Celery worker(s) (`lmanagement/celery.py`) | same | Workers sign nothing user-facing, but load settings, so they must have the same env or they will fail closed |
| Celery beat (`app.conf.beat_schedule` in `lmanagement/celery.py`: 4 schedules) | same | Restart together with the workers |
| Cron or manual management commands (`manage.py ...` run by cron, operators, sync scripts) | same | Search the host crontabs; each one loads settings |
| Shell sessions or one-off scripts with an exported old env | same | Close them, or re-export the new env |
| **MDS** (`master-data-service`, own Django project) | its **own** `SECRET_KEY` and `MDS_DB_PASS` | Rotate separately (section 6). Its key is independent of the backend key |
| Integrations | `MDS_TOKEN(S)`, `SYNC_PEER_TOKENS` | Not derived from `SECRET_KEY` (peer tokens are stored hashed with `make_password`; MDS uses static bearer tokens). Rotate them only if the deploy-tooling review finds real values (assessment §6.1-4) |
| Signature verifiers outside Django | none found | JWTs are verified only by this backend. `SIMPLE_JWT` sets **no `SIGNING_KEY`** (`settings.py` `SIMPLE_JWT` block), so simplejwt signs with `SECRET_KEY` |

## 2. Rotate the DB password first (inside the restart window)

`CONN_MAX_AGE` is not set (default 0): Django opens a **new** DB connection per request and per Celery task. From the
moment the role password changes, every process still holding the old `DB_PASS` fails to connect. So steps 2.1–2.2
and the coordinated restart in 3.3 happen **in one window, back to back**.

1. First write the new `DB_PASS` (and the new `DJANGO_SECRET_KEY`, section 3.1) into the server env store for
   **every** process in section 1 — without restarting yet.
2. Then, as a DB admin on the DB host (not via the app), change the role password with psql's interactive prompt only:
   `\password <app_role>`. Do **not** use `ALTER ROLE ... PASSWORD '<value>'`: the literal can be written to the
   Postgres log (`log_statement` = ddl/all) and to psql history.
3. Immediately run the coordinated restart (3.3). Expect errors only for requests in the seconds between 2.2 and 3.3.
4. Restrict access: `pg_hba.conf` and the firewall allow only the app host(s). Confirm `listen_addresses`.
5. If any other DB copy uses the same role password (sync source, labdhi, tractor, local copies restored from dumps),
   rotate it too, each with its own value.

## 3. Rotate `DJANGO_SECRET_KEY` (hard cut, coordinated restart)

1. Write the new `DJANGO_SECRET_KEY` into the server env store of **every** process in section 1.
2. (Recommended) Create the ops denylist **outside the repo**, for example
   `/etc/license-manager/secret-denylist.sha256` (mode 0400, owned by the app user), with one lowercase sha256 hex
   digest per line of every value known to be exposed (the 2019 key, the `insecure`-style labdhi key, the old DB
   password). Compute each digest on the server without the value reaching shell history or the process list:
   `read -rs v; printf %s "$v" | sha256sum; unset v` (paste the value at the silent prompt). Never write the values or the
   digests into the repo, a ticket or chat. Set `SECURITY_SECRET_DENYLIST_FILE` to that path for every process.
   From then on, the app refuses to start if anyone restores an exposed value.
3. **Coordinated restart:** stop beat → stop workers → restart every gunicorn instance → start workers → start beat.
   Do every host in one window. Every process must come up on the new key, because a mixed fleet produces random 401s.
4. Run `python manage.py check --deploy` with the production env. Expect **no** `lmanagement.E0xx` errors.
   (A startup failure lists `lmanagement.E00x` ids and never prints values.)

## 3a. DGFT portal session (cookies are in git history)

1. In the DGFT portal, **log out** of the browser session that issued the `DGFT_SESSION_ID`, `DGFT_CSRF_TOKEN` and
   `DGFT_AWSALB` cookies that were tracked in `backend/.env_dgft` (untracked in OD-06, still in history) — this ends
   that server-side session.
2. Log in again and copy fresh values **into the server env only** (never into a tracked file; template:
   `backend/.env_dgft.example`). Restart the processes that call the ownership lookup.
3. `DGFT_IEC_NUMBER`, `DGFT_SCRIP_NUMBER`, `DGFT_SCRIP_ISSUE_DATE`, `DGFT_APP_ID` cannot be rotated; treat them as
   business-confidential identifiers that are disclosed in history.

## 3b. Redis

Nothing in Redis/cache is derived from `SECRET_KEY` (cached pivot/dashboard data only), so no flush is required for
the key rotation. Still: if `REDIS_URL` ever carried a password in history or in a shared env file, rotate it
(`requirepass`/ACL) together with this window, and confirm Redis is bound to localhost or firewalled.

## 4. Cleanup and forced resets (data operations; owner approval required)

Dry run first and record the counts in the ticket:
```bash
python manage.py invalidate_all_sessions --flush-expired
python manage.py force_password_reset --joined-on-or-before 2025-12-17 --include-superusers
```
Then execute:
```bash
python manage.py invalidate_all_sessions --flush-expired --execute --reason "OD-06 rotation <ticket>"
python manage.py force_password_reset --joined-on-or-before 2025-12-17 --include-superusers \
    --execute --reason "OD-06 rotation <ticket>"
```
- `2025-12-17` = the date of the latest dump commit `58fa4691` (git metadata only). Accounts created later were never
  in a dump. Add `--usernames-file` if the owner keeps an explicit list.
- Superusers: include them (`--include-superusers`). Their hashes are the most valuable offline-cracking target.
  Make sure at least one admin can still get in: an admin with a working email, or an admin who sets a new password
  right away through `manage.py changepassword <user>` on the server.
- The command prints how many selected accounts **have no email**. Those users cannot self-serve, so an admin sets a
  temporary password and tells them through a trusted channel.
- Both commands write `core.ActivityLog` rows (module `security`) as the audit trail.

## 5. Consequences (communicate these before the window)

- **All access and refresh JWTs become invalid** at the restart (signed with `SECRET_KEY`, no separate
  `SIGNING_KEY`). The blacklist cleanup only removes residual rows.
- **All Django sessions** (admin site) become invalid. Step 4 also deletes the rows.
- **Password-reset links** issued before the rotation become invalid: they are signed with `SECRET_KEY` and bound to
  the password hash, which the forced reset changes.
- Any other `SECRET_KEY`-signed value becomes invalid too (Django signing/messages cookies). Invoice secure links
  (`trade/services/invoice_secure_links.py`) are random tokens stored as SHA-256 and **do not** depend on `SECRET_KEY`.
  They keep working until they expire. Revoke them separately if the owner wants that.
- **Everyone must log in again.** Accounts from the dumps must reset their password first.

## 6. MDS (separate)

MDS has its own `SECRET_KEY` (`master-data-service/mds/settings.py`) and DB role (`MDS_DB_PASS`). Rotate them with the
same pattern (staging → production; DB password → key → restart the MDS gunicorn). Consumers authenticate with
`MDS_TOKENS`, not with the MDS key, so they are unaffected unless the tokens are also rotated. Note: MDS has **no**
startup guard against its dev default key yet (follow-up). Verify by hand that the env file sets it.

## 7. Verification (per environment)

- [ ] `manage.py check --deploy`: no `lmanagement.E0xx`; the process starts with `DJANGO_ENVIRONMENT=production`.
- [ ] An old JWT (captured before the window, from a test account) gets 401. A fresh login works. A refresh token
      issued before the window is rejected.
- [ ] The old DB password fails: `psql` with the old value is rejected, the new one works, and the app health
      endpoint `/api/health/` is OK.
- [ ] Celery: a beat-scheduled task runs successfully after the restart (worker log).
- [ ] A dump account cannot log in with its old password. Its reset email arrives and the reset works.
- [ ] `ActivityLog` has the `system:invalidate_all_sessions` and `system:force_password_reset` summary rows.
- [ ] The denylist file exists outside the repo and is referenced by every process (ops check by hash only).

## 8. Rollback = roll forward

**Never** restore the compromised key or password, even "temporarily". If the new values are broken (a typo, a
process that was missed), generate **another new** value, put it everywhere, and redo the coordinated restart. The
denylist enforces this: an exposed value refuses to boot. Data rollback of step 4 is not needed. Users simply
reset their passwords, and restoring old password hashes would re-expose them.

## 9. User communication template

> Subject: Security maintenance: please sign in again and reset your password
>
> On <date, time IST> we rotated the security keys of License Manager as a precaution. All users were signed out.
> If you see "invalid credentials", use **Forgot password** on the login page to set a new password (the link
> expires; request a new one if needed). Choose a password you do not use anywhere else. We will never ask for your
> password by email or phone. If you have no email on your account, contact <admin contact>.

## 10. After all environments

- Record completion in `docs/erp-transformation/12-decisions-register.md` (OD-06) and in the incident ticket.
- Decide on the history rewrite (`docs/security/OD-06-history-remediation-assessment.md`). It should only follow
  rotation, never replace it.
