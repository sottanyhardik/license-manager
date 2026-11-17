# BOE modernization — documentation index

Status as of 2026-11-17. Phase A = commit `f202cedb`. Phase B = implemented in the working tree, pending lead verification and final gate. Iteration 1 = commit `3ece31f0`.

| Document | Purpose |
|---|---|
| [current-state-and-target-architecture.md](current-state-and-target-architecture.md) | Module shape before and after, and the target layering |
| [business-rules.md](business-rules.md) | BOE business rules, mapped to decisions D1-D15 (links, not copies) |
| [owner-decisions.md](owner-decisions.md) | Approved owner decisions D1-D15 (source of truth) |
| [test-results.md](test-results.md) | Gate and test evidence per phase, with what was not run |
| [security-review.md](security-review.md) | Permissions, PDF handling, media serving, deployment items |
| [financial-integrity-review.md](financial-integrity-review.md) | Merge, frozen rows, CIF ceiling, refresh triggers |
| [final-audit.md](final-audit.md) | Phase A and B status, open items, sign-off state |
| [nginx-nosniff-deployment.md](nginx-nosniff-deployment.md) | Ops change for nosniff (not deployed) |

Related:
- Progress tracker and iteration log: `docs/erp-architecture/boe-modernization-progress.md`
- Generic component registry: `docs/erp-architecture/generic-component-registry.md`
- Module map: `docs/erp-architecture/module-architecture-map.md`
- Project business rule (canonical CIF rule): `.claude/rules/business-rules.md`
