# Final audit: BOE modernization

Date: 2026-11-17. Branch context: worktree `.claude/worktrees/boe-erp`, integration target `feature/v5`.

## Status

| Phase | Commit / state | Status |
|---|---|---|
| Iteration 1 | `3ece31f0` | Done. Progress doc WS1-WS6 done |
| Phase A (D1-D15) | `f202cedb` | Done. Backend and frontend gates PASS; Playwright 29/29 mocked |
| Phase B1 detail page | working tree | Implemented, pending lead verification/final gate |
| Phase B2 MasterForm guard | working tree | Implemented, pending lead verification/final gate |
| Phase B3 save service | working tree | Implemented, pending lead verification/final gate. Opus review requested |
| Phase B4 exporters | working tree | Implemented, pending lead verification/final gate |
| Merge into feature/v5 | NOT DONE | Requires explicit owner approval; not part of this docs task |

## Review verdicts (Phase B)

| Scope | Verdict | Blocking? |
|---|---|---|
| B3 financial write path | approve (read-only, no tests run) | Needs Opus/CIF-auditor review confirmation |
| B1/B2/B4 frontend and exporter | approve_with_fixes | Medium items below should be addressed before merge |

## Open items

| # | Item | Source | Severity | Action |
|---|---|---|---|---|
| 1 | `useUnsavedChangesGuard` `bypassRef` is never reset; after a successful modal save, later edits are unprotected | frontend review | Medium | Reset on new baseline or entity/record change |
| 2 | MasterForm success detection relies on literal `/bill-of-entries` redirect; a duplicate-BOE redirect shows a spurious discard prompt | frontend review | Medium | Explicit onSaved signal from submit hook, or pin path with test |
| 3 | Dirty tracking compares JSON of form data; late async defaults trigger a prompt; guard inactive without form_fields | frontend review, B2 | Low | Baseline after defaults settle |
| 4 | Route guard for `/bill-of-entries/:id` untested | B1, review | Low | Add route-guard test |
| 5 | Viewer test only checks no actions menu | B1 | Low | Strengthen |
| 6 | Golden tests: `UPDATE_BOE_GOLDEN=1` could silently rewrite snapshots in CI; date normalisation may flake across midnight | golden review | Low | Fail when CI=true; freeze time |
| 7 | ProtectedError log now under `apps.bill_of_entry.services.boe_service` (was serializers); check ops log filters | B3 review | Low | Check log routing |
| 8 | Three refactored branches lack API tests (see financial-integrity-review item 2) | B3 review | Low | Add tests |
| 9 | Visual smoke test at 390px and desktop for sticky bars not done | B2 | Medium | Dev-server check |
| 10 | Playwright live/real specs not run | Phase A | Info | Needs seeded backend |
| 11 | nginx nosniff not deployed | Phase A | Ops | Follow nginx-nosniff-deployment.md |
| 12 | Full Phase B gate (backend + frontend + Playwright) not run | Phase B | Required before merge | Lead to run `scripts/dev/quality-gate.sh all` |
| 13 | Cross-app import edge boe_service to license effective_cif_mode | B3 | Info | Accepted (same as before) |
| 14 | Allotment export duplicates BOE helpers | B4 | Info | Later shared base |

## Deferred backlog mapping

| Progress doc deferred item | Now |
|---|---|
| 3 Dedicated /bill-of-entries route on ModuleWorkspace | Detail route implemented (B1); register remains MasterList |
| 4 MasterForm sticky header/footer for BOE | Implemented (B2) |
| 8 Move BOE create/update into save_boe_with_rows | Implemented (B3); ratchet 4 to 0 |
| 9 Moving BOE exporter to services/exporters | Implemented (B4) |
| 13 boe_pdf_copy and parse-pdf validation | Implemented in Phase A (D9, D10) |

## Sign-off

Not signed off. Blocking before merge: items 1, 2, 9 (frontend), item 12 (final gate), and the Opus review in financial-integrity-review item 1. Merge needs explicit owner approval.
