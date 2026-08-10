# SEC-03 — Hardcoded, committed fallback value for DJANGO_SECRET_KEY

## Location
`backend/lmanagement/settings.py:24-27`

```python
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "local-dev-only-secret-key-change-for-production-7f8e6d5c4b3a2910",
)
```

## What & why

If the `DJANGO_SECRET_KEY` environment variable is ever unset in a deployed
environment (misconfigured server, a new environment stood up from
`server-envs/*.env` without copying the secret, a container image built
without the env file), the app silently falls back to this fixed, publicly
committed string rather than failing to start. `SECRET_KEY` backs Django's
session signing, CSRF token signing, and (via `default_token_generator`) the
password-reset token in `backend/apps/accounts/views/password.py`. If this
fallback is ever live in production, anyone who has read this source file
(it's committed to the repo) can forge a valid Django signed session cookie,
forge a CSRF token, or — most concretely — forge a password-reset token for
any username/user id and take over any account without ever knowing their
password (Django's `default_token_generator.check_token` only validates
against `SECRET_KEY` + a few user/timestamp fields, all of which are
guessable/knowable for a targeted account).

## Exploit scenario (conditional on the misconfiguration described above)

1. Attacker confirms `DJANGO_SECRET_KEY` isn't set in the target's runtime
   env (no direct way to check remotely, but git history/repo leaks, a
   misconfigured `.env` copy step in `scripts/deployment/`, or an internal
   contractor with repo access are realistic vectors for an internal app like
   this one).
2. Using the known fallback secret, the attacker computes a valid
   `default_token_generator` token for a target `user.pk` (obtainable via
   `PasswordResetRequestView`'s generic response doesn't leak it directly,
   but internal user IDs are often low, sequential integers guessable by
   brute-forcing `uid` values 1..N, or known from other exposed responses
   such as `UserManagementSerializer`'s `id` field for `USER_MANAGER`-role
   accounts, or activity logs).
3. Attacker calls `POST /api/auth/password-reset-confirm/` with the forged
   `uid`/`token` and a new password of their choosing, taking over the
   account.

## Business risk

Full account-takeover / session-forgery capability if this default is ever
live, entirely from a value visible in this git repository. Low likelihood
under correct ops discipline (the constant is clearly labeled dev-only and
`server-envs/*.env` presumably sets the real value), but the *impact* if it
ever does apply is total compromise, and there is no runtime assertion in
`settings.py` that would catch the misconfiguration before it ships.

## Mitigation recommendation

Fail fast instead of silently falling back when not in `DEBUG`:

```python
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "local-dev-only-secret-key-change-for-production-7f8e6d5c4b3a2910"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set outside DEBUG mode")
```
This is additive/defensive and does not change any public API behavior.

## Confidence

Medium — the defect (silent insecure fallback with no production guard) is
proven by source. Whether it is *currently* live anywhere is an operational
fact I cannot verify from the repository alone (see assumption below).

## Unverifiable assumptions
- Whether `DJANGO_SECRET_KEY` is actually set to a unique secret value in
  every currently-deployed environment (not visible from source; would need
  access to the live servers'/containers' environment to confirm).
