# ADR-010 — Legacy Read-Only Rule

**Status:** Accepted
**Date:** 2026-07-14

## Context

The hybrid parallel-run strategy (ADR-001) places the existing application
under `legacy/` as a read-only reference implementation. The purpose of
keeping legacy is to have a ground-truth reference for every business rule,
edge case, and data shape that exists in production — not to continue
developing it in parallel with the new app.

If legacy continues to receive feature development, two problems arise:
(a) the new app must keep up with legacy changes, creating a moving migration
target, and (b) the legacy codebase is no longer a stable reference —
developers cannot trust that what they read in legacy reflects what was there
at the start of the migration.

## Decision

**Zero commits to `legacy/` except emergency hotfixes.**

The full policy:

1. `legacy/README.md` states the read-only rule explicitly at the top of the
   file so every developer encounters it before touching the directory.
2. A git pre-commit hook (or CI check) warns when a commit touches any file
   under `legacy/`. The warning does not block the commit (emergency hotfixes
   must be possible), but it requires the committer to confirm the exception.
3. **Emergency hotfix exception:** A change to `legacy/` is permitted only
   when all of the following conditions are met:
   - A production bug is actively causing data loss or system unavailability.
   - The PM and tech lead both provide written sign-off (Slack thread or
     ticket comment is sufficient).
   - The committer opens a backport ticket immediately, targeting the same
     fix to the new app within **5 business days**.
4. **No feature development in legacy.** New features are built only in the
   new app. If a stakeholder requests a feature that is not yet available in
   the new app, the answer is "it will be available after cutover" — not
   "add it to legacy".
5. **After production cutover + rollback window (30 days) + business
   acceptance:** the cleanup operation is `rm -rf legacy/`. No migration
   scripts, no archival, no branch preservation — the git history already
   preserves every legacy commit. The directory deletion is the only cleanup
   step needed.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Periodic legacy updates (sync feature changes to both apps) | Creates a moving migration target; doubles development effort for every feature; the entire purpose of parallel-run is undermined if legacy is not a stable baseline. |
| Archive legacy to a separate git branch at project start | A branch is less visible than a directory; developers exploring the repo would not immediately encounter the reference code when looking at the file tree. The `legacy/` directory makes the reference implementation immediately discoverable. |
| Delete legacy immediately and rely on git history | Git history is useful for `git blame` and `git log`, but not for quick side-by-side comparison (e.g. "what does legacy's balance algorithm look like?"). The directory makes diffing trivial during the transition period. |
| Keep legacy running indefinitely as a fallback | Creates operational burden (two apps to monitor, patch, and operate) with no time limit. The 30-day rollback window + business acceptance is the defined exit. |

## Consequences

**Positive:**
- `legacy/` is a stable, trustworthy reference for every business rule.
  Developers can run `diff legacy/backend/apps/licenses/ backend/apps/licenses/`
  to verify parity.
- The cleanup path is simple and total: one `rm -rf` command with no residual
  infrastructure to remove.
- Banning feature development in legacy forces stakeholders to accept that new
  features arrive with the new app — this creates healthy urgency around the
  migration timeline.
- The 5-day backport window ensures emergency fixes do not create a permanent
  divergence between legacy and new app.

**Negative:**
- Production bugs in legacy that require a fix during the transition period
  must be fixed in two places (legacy + new app backport). This is an
  unavoidable cost of the parallel-run model and is mitigated by the expectation
  that such bugs are rare.
- The CI warning on legacy commits adds a small friction for the emergency
  hotfix case. Teams must understand that the warning is expected and intentional
  for legitimate hotfixes.
- If the rollback window extends beyond 30 days (business delays acceptance),
  the team is operating two live systems for longer than planned. The rollback
  window duration should be treated as a hard deadline, not a soft target.

## Related ADRs

- ADR-001 — Migration Strategy: Hybrid Parallel-Run
- ADR-002 — Database Strategy: Single Shared PostgreSQL
- ADR-009 — Production Cutover Gate: 6 Simultaneous Criteria
