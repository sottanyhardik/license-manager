# OD-06 handover (frozen 2026-11-16)

**Status:** repository-side remediation complete and verified, **uncommitted** in the protected workspace
(`feature/version5` @ `e6dfc9b7`). Commit needs separate owner approval. ERP implementation continues in
`../license-manager-implementation` (branch `feature/erp-implementation`, same base SHA, without OD-06 changes).

**Quality gate (protected workspace):** last complete run: every stage PASS except `audit`, which was NOT RUN
there; the audit stage passed separately (backend 75 / MDS 18 advisories, all excepted, 0 new). The gate now
provisions pip-audit 2.10.1 in an isolated venv (`~/.cache/license-manager/pip-audit-venv`). **Final
`quality-gate.sh all`: exit 0, all 14 stages PASS** (frontend 546; backend `tests/` 303; app-level 2,735; MDS 25;
mds-client 32; OpenAPI 0 errors / 22 warnings; pip-audit backend 75 + MDS 18 advisories, all excepted, 0 new).

**Production deployment: BLOCKED** until owner/ops complete the controlled rotation in
`docs/security/OD-06-rotation-runbook.md` (DB password, Django `SECRET_KEY` hard cut, DGFT session, MDS key,
forced resets + session/JWT cleanup).

**Remaining findings**
- Critical (ops): dumps (hashes, sessions, JWTs, business data), 2019 `SECRET_KEY`, DB password and DGFT cookies are
  in git history on `origin/develop`, `origin/master`, `origin/legacy/archive-baseline-2026-11-14` (GitHub remote
  `sottanyhardik/license-manager`). Repo visibility, forks, other clones' pushes and access history: **unknown**.
- Medium: deployment scripts + 7 commits (manifest §7) await owner review; MDS boots with dev/weak `SECRET_KEY`,
  `DEBUG=True` and `ALLOWED_HOSTS=*` (guard proposed, not implemented; ship only after MDS key rotation, staging first).
- Low: empty denylist passes silently; case-sensitive repo-path check on macOS; legacy credential-looking literals
  (`backend/reconciliation_detailed.py`, `tests/e2e/qa_*`, `frontend/route-authenticated-test.mjs`) need owner confirmation.
- Info: 75 advisories excepted until 2027-01-15 (Django 6.0.8 / DRF 3.18.2 / Pillow 13.0.0 upgrades pending decision).

**Never include in implementation commits:** every OD-06 file in the protected workspace (see `git status` there),
`backend/.env_dgft` (staged removal; local ignored copy), `audit_evidence/pass1/BL-EXP/01/query_result` (redaction,
owner decision), `.claude/hooks/guard_bash.py` (owner change), `frontend/tsconfig.tsbuildinfo`, `.DS_Store`, `.idea/*`.
