# Stateful Work Queue

Work is processed in priority order. Completed tasks are removed or marked `DONE`; changed files are requeued as `REQUIRES_RECHECK` in `audit-database.json`.

| ID | Priority | Stream | Status | Work | Verification |
|---|---:|---|---|---|---|
| `P7-REPORTING-EXPORTS-AUDIT` | 1 | Reporting & Exports | PENDING | Continue Phase 7 Reporting & Exports audit from the next pending report/export file | Run focused backend tests, Ruff, py_compile, compileall, Django check, migration checks, static analysis, and available security tooling after each completed file. |

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
