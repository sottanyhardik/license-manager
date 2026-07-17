# Stateful Work Queue

Work is processed in priority order. Completed tasks are removed or marked `DONE`; changed files are requeued as `REQUIRES_RECHECK` in `audit-database.json`.

| ID | Priority | Stream | Status | Work | Verification |
|---|---:|---|---|---|---|
| `P7-REPORTING-EXPORTS-AUDIT` | 1 | Reporting & Exports | DONE | Phase 7 Reporting & Exports is frozen; do not reopen completed Phase 7 files unless the Repository Knowledge Graph marks them `REQUIRES_RECHECK`. | Existing Phase 7 file-level verification recorded in `docs/audit/phase-07-reporting-report.md`, audit database, dashboard, and work queue history. |
| `P8-BILLS-OF-ENTRY-AUDIT` | 1 | Bills of Entry | DONE | Phase 8 Bills of Entry completed all queued `NOT_STARTED` and `REQUIRES_RECHECK` files in the active audit database. | Focused backend tests, Ruff, py_compile, compileall, Django check, makemigrations check, git diff checks, and security-tool availability blockers are recorded in the Phase 8 report. |
| `P9-INVENTORY-AUDIT` | 1 | Inventory | DONE | Phase 9 Inventory is frozen; do not reopen completed Phase 9 files unless the Repository Knowledge Graph marks them `REQUIRES_RECHECK`. | Phase 9 queue query returned zero Inventory or Balance files marked `NOT_STARTED` or `REQUIRES_RECHECK`; completed unit verification is recorded in `docs/audit/phase-09-inventory-report.md`. |
| `P10-REPORTS-AUDIT` | 1 | Reports | DONE | Phase 10 Reports is frozen; Phase 7 Reporting & Exports remains frozen and was not reopened. | Active report/export/PDF/Excel/CSV/ledger query returned zero files marked `NOT_STARTED` or `REQUIRES_RECHECK`. |
| `P11-DOCUMENTS-AUDIT` | 1 | Documents | IN_PROGRESS | Continue Phase 11 Documents from the existing audit database and process the next document/media/file/PDF/copy/upload item marked `NOT_STARTED` or `REQUIRES_RECHECK`. | `backend/templates/500.html` completed in source commit `6ed96a35cfed4a23c98530b8e232c90d22511876`; select the next Phase 11 item from the audit database queue. |

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
- `2026-07-17T12:08:27+05:30` - Phase 9 Inventory reopened only for dependency-marked `REQUIRES_RECHECK` allocation helpers and deleted `frontend/src/components/AllotmentAllocationModal.tsx` plus `frontend/src/services/calculators/allocationCalculator.js` in commit `b36a90c3aaf436ca025ebe3f4c5f4c0fbe00db6e` (`cleanup(inventory): remove dead allocation helpers`); continue with the next Inventory file marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T10:49:39+05:30` - Phase 10 Reports frozen without reopening Phase 7 after the active report/export/PDF/Excel/CSV/ledger query returned zero files marked `NOT_STARTED` or `REQUIRES_RECHECK`; latest recovery commit `919f53d1f8273eaf59e8e5d70b98593c4b86b6f3` (`docs(audit): freeze inventory phase`).
- `2026-07-17T12:10:25+05:30` - Phase 10 Reports recovery confirmation kept Phase 10 frozen after the latest Phase 9 recheck; active report/export/PDF/Excel/CSV/ledger query again returned zero files marked `NOT_STARTED` or `REQUIRES_RECHECK`, from recovery commit `0d2e7faa16aa49362351de4e7917c14af8e93dff` (`docs(audit): record allocation helper recheck`).
- `2026-07-17T10:54:25+05:30` - Phase 11 Documents deleted verified-dead `backend/templates/profile.html` in commit `08269148be7f2eea870d8c61158372764e388572` (`cleanup(documents): remove dead profile template`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T10:58:35+05:30` - Phase 11 Documents completed `docs/media-security-cutover.md` in commit `96f0da8f0903b8a18c7ddc1460146572b8994689` (`docs(documents): update media security cutover`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T11:02:48+05:30` - Phase 11 Documents completed `frontend/src/hooks/useFileUpload.js` and `frontend/src/test/useFileUpload.test.ts` in commit `70602d69d878a865aa7b71bd064f194cd927ad5b` (`fix(documents): harden file upload hook`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T11:08:56+05:30` - Phase 11 Documents completed `frontend/src/pages/Profile.tsx` plus AuthContext user-update contract in commit `f0bb9e719b23ad4dc17ae53f187366e135bfdb64` (`fix(documents): harden profile page updates`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T11:14:12+05:30` - Phase 11 Documents completed `nginx-protected-media.conf` in commit `95bc45513b56f735540d92aefc6508c08cba34ae` (`fix(documents): harden protected media nginx snippet`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T11:18:04+05:30` - Phase 11 Documents completed `scripts/diagnostics/sync-media.sh` in commit `9bddcf84789ce0825b165f34b1db940a44a2532c` (`fix(documents): harden media sync diagnostics`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T11:21:21+05:30` - Phase 11 Documents completed `nginx-http-only-tractor.conf` in commit `45a2223bc7f7ad1ac954e2c87de62c775cd106ac` (`fix(documents): harden tractor http nginx bootstrap`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T16:04:27+05:30` - Phase 11 Documents deleted verified-dead legacy allotment Django templates and `app_tags` in commit `99ed3080ed82f0923fe5538108dca80353cdd5a9` (`cleanup(documents): remove dead allotment templates`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T16:08:27+05:30` - Phase 11 Documents completed `backend/templates/404.html` and route-template regression coverage in commit `d7e55f2ef8b03c4fe95cab4f751641f16fd36892` (`fix(documents): harden production 404 template`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.
- `2026-07-17T16:11:22+05:30` - Phase 11 Documents completed `backend/templates/500.html` and route-template regression coverage in commit `6ed96a35cfed4a23c98530b8e232c90d22511876` (`fix(documents): harden production 500 template`); continue with the next document item marked `NOT_STARTED` or `REQUIRES_RECHECK`.

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
