# Verification record: ISS-011 (superuser protection) and ISS-013 (session persistence)

Date: 2026-11-01. Slice 1 of the decision implementation plan. Branch `version-v1`. Test database names were set through `TEST_DB_NAME`; the developer's database was not used.

## ISS-013 — verified before implementation

Claim (from the audit): logout blacklists only the submitted refresh token; password change and password reset do not end sessions; refresh tokens last 7 days; the revoked-access-token table has no production writer.

### Source evidence (static, lead read)

| Point | Evidence |
|---|---|
| Logout blacklists only the submitted refresh token | `backend/apps/accounts/views/auth.py:11–20` (`LogoutView.post`: `RefreshToken(token).blacklist()`). No other token is touched. |
| Password change does not end sessions | `backend/apps/accounts/views/password.py:108` (`user.set_password`). No blacklisting or token revocation in the view. |
| Password reset does not end sessions | `backend/apps/accounts/views/password.py:149` (`user.set_password`). Same. |
| Admin reset does not end sessions | `backend/apps/accounts/views/user_management.py` `reset_password`: sets the password and saves. No token revocation. |
| Refresh lifetime 7 days, rotation and blacklist after rotation on | `backend/lmanagement/settings.py:328–340` (`REFRESH_TOKEN_LIFETIME` 7 days; `ROTATE_REFRESH_TOKENS` and `BLACKLIST_AFTER_ROTATION` true). |
| Access token is stateless, 30 minutes by default | `backend/lmanagement/settings.py:328–335` (`ACCESS_TOKEN_LIFETIME` from `ACCESS_TOKEN_MINUTES`, default 30). |
| `RevokedAccessToken` has no production writer | Writers across `backend/`: test only (`backend/tests/test_authentication_query_param.py:84`). Read at `backend/apps/core/authentication.py:73`. |

### Runtime evidence

1. Agent G, 2026-11-01 (`evidence/runtime-verification-2026-11-01.md`, section ISS-013): exit 0, 1 passed. Access token works after logout (200); refresh token after password change (200) and after admin reset (200); submitted refresh token after logout is refused (401).
2. Lead re-check (probe at `/tmp/lm-audit-probe/test_iss013_recheck.py`, outside the repository). Exit 0, 1 passed. Result:

| Step | Status |
|---|---|
| Logout of session 1 with its refresh token | 205 |
| Session 1 refresh token after logout | 401 |
| Session 1 access token on `/me` after logout | 200 (stateless until expiry) |
| Session 2 refresh token after session 1 logged out | 200 (other sessions survive logout) |
| Admin resets the user's password | 200 |
| Session 2 refresh token after the admin reset | 200 (sessions survive a password reset) |

Probe defect, recorded for accuracy: the first lead probe run reported 401 for session 2 after the reset. The cause was the probe reusing a refresh token that rotation had already retired. The probe was corrected to use the rotated token, and the result above is from the corrected run.

### Verdict

**ISS-013 CONFIRMED.** Logout ends only the submitted refresh token. Other sessions of the same user survive logout, password change and admin reset. Access tokens remain valid until they expire. Implementation of the session rule (decision Q-009 = A) is Slice 8 and is not part of this record.

## ISS-011 — superuser protection (Slice 1)

Claim: USER_MANAGER can list, view, reset the password of, and delete superusers.

### Before the fix (reproduced in tests)

New file `backend/apps/accounts/test_superuser_protection.py`, run before any change to the view:

- Command: `TESTING=true TEST_DB_NAME=test_slice1_superuser_20261101 ../.venv/bin/python -m pytest apps/accounts/test_superuser_protection.py -q --no-cov -p no:cacheprovider` (from `backend/`)
- Exit 1. 8 failed, 7 passed.
- Failures show the gap: superuser detail 200 (expected 404); superuser reset 200 (expected 404); superuser delete 204 (expected 404); superuser deactivate 200 (expected 404); superuser listed (id 67 found in the list); search by a superuser's username returned the superuser.

Agent G, 2026-11-01 (`runtime-verification-2026-11-01.md`, section ISS-011): exit 0, 24 passed. USER_MANAGER reset of a superuser returned 200 and changed the hash; delete returned 204 and removed the row.

### After the fix

- Change: `backend/apps/accounts/views/user_management.py` `UserManagementViewSet.get_queryset` excludes superuser accounts unless the caller is a superuser. Every action in the viewset (list, search, retrieve, update, partial update, delete, reset-password) uses this queryset, so a superuser id now answers exactly like a missing id.
- Serializer behaviour unchanged: `is_superuser` and `is_staff` remain read-only for non-superusers (`backend/apps/accounts/serializers.py` `get_fields`).

Results (exit codes from the actual runs):

| Command | Exit | Result |
|---|---|---|
| `pytest apps/accounts/test_superuser_protection.py apps/accounts/tests.py tests/test_authorization_permissions.py -q --no-cov -p no:cacheprovider` | 0 | 49 passed (15 new, 34 baseline) |
| Baseline before any change: `pytest apps/accounts/tests.py tests/test_authorization_permissions.py` | 0 | 34 passed |
| `flake8 --select=E9,F` on the two changed files | 0 | no findings |
| `py_compile` on the two changed files | 0 | compiles |

No frontend test was run: no frontend file changed. See the regression note on the superuser count for the list view.

### Verdict

**ISS-011 FIXED in Slice 1, backend-enforced, verified by tests.** Frontend hiding was already present for the delete button and is not relied on.

## Residual risks (not fixed in this slice)

1. **Role assignment escalation among non-superuser roles.** A USER_MANAGER can assign any role code, including USER_MANAGER, to any non-superuser account, including their own (`roles` field, `UserManagementSerializer`). Not a superuser escalation, but a route to any non-superuser role. Needs an owner decision on which roles a USER_MANAGER may grant. Not in the approved register.
2. **Session persistence** (ISS-013): Slice 8, after the owner-approved rule is implemented. Q-009 = A.
3. **Superuser count on the user list**: the screen counts superusers from the list it receives. For a USER_MANAGER the count is now 0 (`frontend/src/pages/admin/UserList.tsx`, around line 71). It is accurate for what the caller can see, but may look like an error. No UI change made.
4. **Django admin** (`/admin/`): mounted. Reachable only by `is_staff` accounts, which only superusers can set through the API. No role group is granted Django permissions in code. Not tested in this slice.
5. **Other user-writing paths**: `migrate_auth` and `check_user_roles` are management commands, not API routes. Not reachable by a USER_MANAGER.
