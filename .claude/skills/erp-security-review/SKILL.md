---
name: erp-security-review
description: Project security review checklist for License Manager ERP task diffs — RBAC/authz on DRF endpoints, single-tenant scoping (OD-04), OD-06 secret handling, OD-07 cookie/CSRF flags, PDF/upload parsing, injection and error leakage — layered on ECC django-security. Named erp-security-review to avoid shadowing Claude Code's built-in /security-review. Use in the REVIEW phase for security-relevant tasks.
metadata:
  origin: project
---

# erp-security-review

1. **Purpose** — catch authorization, exposure and secret-handling defects before integration.
2. **Invocation criteria** — diffs touching `apps/accounts/**`, `permissions.py`, views/serializers/urls,
   `lmanagement/settings.py`/`security_config.py`/`checks.py`, auth/JWT/cookies, uploads/PDF parsing, management
   commands handling users or credentials. Used by `erp-security-reviewer`; built-in `/security-review` remains
   available for whole-branch reviews.
3. **Required context** — ECC `django-security`, `rules/ecc/common/security.md`, `rules/ecc/python/security.md`;
   decisions OD-04, OD-06, OD-07; `docs/security/OD-06-*.md` (never the secret values).
4. **Workflow** — for each touched endpoint: authentication class, permission class, object-level check,
   queryset scoping, fields returned, throttling; settings: DEBUG, hosts, cookie Secure/HttpOnly/SameSite, CSRF;
   secrets: none in code/tests/logs/fixtures, no committed fingerprints; inputs: ORM only (no raw SQL with
   interpolation), file type/size limits on uploads; errors: no stack traces/PII in responses; tests: negative
   (denied) + positive (allowed role) exist.
5. **Restrictions** — read-only; never read/print `.env*`, `backend/.env_dgft`, keys, tokens; never run
   credential/cleanup commands; no network scanning of real hosts.
6. **Acceptance criteria** — severity-ranked findings with exploit scenario and fix; CRITICAL/HIGH ⇒ changes requested.
7. **Verification commands** — `git -C <worktree> diff <base_sha>`; `cd backend && TEST_DB_NAME=<db> python -m pytest <security tests> -q`;
   `python manage.py check --deploy` (local settings only, read the output, don't change settings).
8. **Documentation references** — `.claude/skills/django-security/SKILL.md`, `.claude/agents/erp-security-reviewer.md`,
   `.claude/agents/security-auditor.md`, `docs/security/`.
