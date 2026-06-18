# Checklist — Security

Run when a change touches auth, permissions, input handling, file upload, or secrets.
Rule: `.claude/rules/security.md`. Deep dive: `docs/08-security.md`.

## AuthZ / AuthN

- [ ] Every new/changed endpoint declares `permission_classes` (no implicit open access).
- [ ] Role boundaries enforced **server-side**, not just hidden in the UI (`ProtectedRoute` is UX).
- [ ] No change weakened JWT refresh rotation / blacklisting or the central axios refresh flow.

## Input & output

- [ ] All input validated in DRF serializers (and on the form layer for UX).
- [ ] Any HTML rendered from data is sanitized with `dompurify`.
- [ ] No string-formatted SQL/shell; queries parameterized (ORM).
- [ ] File uploads validate type/size; parsed PDFs/ledgers handled defensively.

## Secrets & config

- [ ] No secrets in code, tests, logs, or fixtures; `.env*` untracked.
- [ ] New config read from env vars, not hardcoded.
- [ ] `DisableCSRFForAPIMiddleware` scope unchanged (still only `/api/`).

## Audit

- [ ] `ActivityLogMiddleware` still active on the request path.
- [ ] Rate limiting/throttling not weakened without review.
