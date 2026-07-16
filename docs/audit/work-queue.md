# Stateful Work Queue

Work is processed in priority order. Completed tasks are removed or marked `DONE`; changed files are requeued as `REQUIRES_RECHECK` in `audit-database.json`.

| ID | Priority | Stream | Status | Work | Verification |
|---|---:|---|---|---|---|
| `P7-REPORTING-EXPORTS-AUDIT` | 1 | Reporting & Exports | DONE | Phase 7 Reporting & Exports is frozen; do not reopen completed Phase 7 files unless the Repository Knowledge Graph marks them `REQUIRES_RECHECK`. | Existing Phase 7 file-level verification recorded in `docs/audit/phase-07-reporting-report.md`, audit database, dashboard, and work queue history. |
| `P8-BILLS-OF-ENTRY-AUDIT` | 1 | Bills of Entry | PENDING | Continue Phase 8 Bills of Entry audit from the highest-priority `NOT_STARTED` or `REQUIRES_RECHECK` file in the existing audit database and repository knowledge graph. | Run focused backend/frontend tests as applicable, Ruff, py_compile, compileall, Django check, makemigrations check, git diff checks, and available security tooling after each completed logical unit. |

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
