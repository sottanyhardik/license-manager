# Stateful Work Queue

Work is processed in priority order. Completed tasks are removed or marked `DONE`; changed files are requeued as `REQUIRES_RECHECK` in `audit-database.json`.

| ID | Priority | Stream | Status | Work | Verification |
|---|---:|---|---|---|---|
| `P7-REPORTING-EXPORTS-AUDIT` | 1 | Reporting & Exports | DONE | Phase 7 Reporting & Exports is frozen; do not reopen completed Phase 7 files unless the Repository Knowledge Graph marks them `REQUIRES_RECHECK`. | Existing Phase 7 file-level verification recorded in `docs/audit/phase-07-reporting-report.md`, audit database, dashboard, and work queue history. |
| `P8-BILLS-OF-ENTRY-AUDIT` | 1 | Bills of Entry | DONE | Phase 8 Bills of Entry completed all queued `NOT_STARTED` and `REQUIRES_RECHECK` files in the active audit database. | Focused backend tests, Ruff, py_compile, compileall, Django check, makemigrations check, git diff checks, and security-tool availability blockers are recorded in the Phase 8 report. |
| `P9-INVENTORY-AUDIT` | 1 | Inventory | DONE | Phase 9 Inventory is frozen; do not reopen completed Phase 9 files unless the Repository Knowledge Graph marks them `REQUIRES_RECHECK`. | Phase 9 queue query returned zero Inventory or Balance files marked `NOT_STARTED` or `REQUIRES_RECHECK`; completed unit verification is recorded in `docs/audit/phase-09-inventory-report.md`. |

## Work Queue History

- `2026-07-16T16:21:03+05:30` - `P7-REPORTING-EXPORTS-AUDIT` frozen in commit `f5e4f3f80f81907a67f505455db75dc0459e9032`.
- `2026-07-16T16:19:33+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/__init__.py`; continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T16:24:27+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/migrations/0001_initial.py`; continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T16:25:46+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/migrations/0002_initial.py`; continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T16:26:49+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/migrations/0003_alter_billofentrymodel_unique_together.py`; continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T16:27:57+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/migrations/__init__.py`; continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T16:29:02+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/parsers/__init__.py`; continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T16:30:12+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/scripts/__init__.py`; continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T16:57:31+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/scripts/boe.py` in commit `e912f2242b1202cf87524998e4cdd1c2ca2d5230` (`fix(bill_of_entry): harden icegate helpers`); continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T17:05:46+05:30` - Phase 8 Bills of Entry deleted obsolete `backend/apps/bill_of_entry/scripts/generate_tl.py` in commit `1e4ecac9cb814cdb40dfbee97401e0de10c5a9ae` (`cleanup(bill_of_entry): remove dead transfer letter script`); continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T17:08:36+05:30` - Phase 8 Bills of Entry completed `backend/apps/bill_of_entry/scripts/utils.py`; retained live ICEGATE port dictionary unchanged and continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T17:11:47+05:30` - Phase 8 Bills of Entry deleted obsolete `backend/apps/bill_of_entry/tasks.py` in commit `b6bb035b05c8497f9c6c9a71fb3f609bf02ef521` (`cleanup(bill_of_entry): remove dead balance task`); continue with the next `backend/apps/bill_of_entry` file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T17:17:06+05:30` - Phase 8 Bills of Entry deleted the verified-dead BOE legacy Django template-view stack in commit `0d42a515b6349520b665ad388f49fe92a78d45bc` (`cleanup(bill_of_entry): remove dead legacy template views`); continue with `backend/apps/bill_of_entry/tests.py`, the remaining BOE file marked `REQUIRES_RECHECK`.
- `2026-07-16T17:27:18+05:30` - Phase 8 Bills of Entry deleted empty `backend/apps/bill_of_entry/tests.py` in commit `07cc55e742f061e66643eb02034f7c9078531b4c` (`cleanup(bill_of_entry): remove empty test stub`); Phase 8 now has zero BOE files marked `NOT_STARTED` or `REQUIRES_RECHECK`, and Phase 9 Inventory is queued next.
- `2026-07-16T17:40:25+05:30` - Phase 9 Inventory deleted stale `backend/scripts/char_license_list_balance.py` in commit `1d7fb0713b09b25b7375f749c076a43b4734a9f0` (`cleanup(inventory): remove stale balance probe`); continue with the next Inventory file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T17:42:58+05:30` - Phase 9 Inventory deleted stale `backend/scripts/test_balance_calc.py` in commit `8058036a1a16d037cdd27c99ba2a26e81d7ba395` (`cleanup(inventory): remove stale balance test script`); continue with the next Inventory file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T17:50:32+05:30` - Phase 9 Inventory completed `docs/architecture/BALANCE_CALCULATION_CONSOLIDATION.md` in commit `a6246911dab2fcf96053f3e5b87dc6f92a93e74d` (`docs(inventory): update balance architecture guide`); continue with the next Inventory file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-16T17:55:39+05:30` - Phase 9 Inventory completed `frontend/src/components/LicenseBalanceModal.tsx` in commit `e9a690e24c02dd80960299e2e213b3b879e77c38` (`fix(inventory): harden license balance modal`); continue with the next Inventory file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T10:47:57+05:30` - Phase 9 Inventory frozen after the active audit database query returned zero Inventory or Balance files marked `NOT_STARTED` or `REQUIRES_RECHECK`; latest recovery commit `3c18e899a67b024418137ed7f8232694751715b3` (`docs(audit): record license balance modal audit`).

## Module Pipeline

1. Authentication
2. Authorization
3. Users
4. Roles & Permissions
5. Master Data
6. License
7. Allotments
8. Bills of Entry
9. Inventory
10. Reports
11. Documents
12. Uploads
13. Background Tasks
14. Shared Services
15. Utilities
16. Scripts
17. Frontend Shared Components
18. Frontend Hooks
19. Frontend Pages
20. Trade
