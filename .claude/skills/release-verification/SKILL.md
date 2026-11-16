---
name: release-verification
description: Final verification of an integrated ERP batch in the License Manager before owner approval — CI-equivalent quality gates, migration check, schema/pip-audit ratchets, ownership audit, decision compliance and a factual report — layered on ECC verification-loop and django-verification. Use in the FULL QUALITY GATE and OWNER APPROVAL phases; never deploys.
metadata:
  origin: project
---

# release-verification

1. **Purpose** — prove an integration branch is ready for the owner to review/merge; report honestly.
2. **Invocation criteria** — after INTEGRATE, before `orch.py transition T completed`; before asking the owner to merge.
3. **Required context** — `.github/workflows/ci.yml` (authoritative), `scripts/dev/quality-gate.sh`,
   ECC `verification-loop`, `django-verification`; queue entries of the batch; `.claude/commands/report.md`.
4. **Workflow** — (a) one gate at a time, in the integration worktree: `sh scripts/dev/quality-gate.sh <areas>`
   (exit 0 pass, 1 fail, 3 = a gate could not run → say so); (b) `python manage.py makemigrations --check --dry-run`;
   (c) `orch.py validate` and `worktree verify` for each task; (d) diff audit: only owned files changed, no secrets,
   no deploy files; (e) decision compliance per task; (f) `/report`.
5. **Restrictions** — never push, merge into develop/master, tag, release or deploy (owner actions); never claim
   a gate passed without its output; don't run gates concurrently with other heavy jobs.
6. **Acceptance criteria** — all relevant gates PASS (or explicitly NOT RUN with reason), migrations consistent,
   reviews approved, report delivered.
7. **Verification commands** — `sh scripts/dev/quality-gate.sh all`; `python3 .claude/orchestration/bin/orch.py validate`;
   `git diff --stat <base_sha>..HEAD`.
8. **Documentation references** — `.claude/skills/verification-loop/SKILL.md`, `.claude/skills/django-verification/SKILL.md`,
   `.claude/commands/quality-gate.md`, `.claude/commands/report.md`, `.claude/orchestration/INTEGRATION_POLICY.md`.
