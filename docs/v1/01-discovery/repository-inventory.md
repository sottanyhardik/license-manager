# Repository inventory

**Verified by code/static index.** The checked baseline contains 933 tracked Python files, 502 tracked frontend script files, 448 test-named paths and 645 tracked Markdown files. The generated `.claude/index` reports 1,013 backend files and 8,046 indexed backend symbols; its scope is regex-based and excludes runtime-only registration.

| Area | Inventory | Principal ownership |
| --- | --- | --- |
| Django apps | accounts, allotment, bill_of_entry, core, license, reconciliation, tasks, trade | Domain modular monolith |
| Frontend | React 19, TS strict, Vite/Rolldown, Router 7, React Query 5, Tailwind 4, Radix/shadcn | SPA |
| Backend migration files | 127 | accounts 6; allotment 16; BOE 14; core 19; license 56; reconciliation 5; tasks 1; trade 10 |
| Backend services/views/tests | 102 service files / 49 view files / 254 test files | Domain and API layer |
| Documentation | Root reports plus `docs/`, notably `enterprise-rebuild`, assessment, audit, architecture, modules and UI modernization | Retained evidence |

Ignored local artifacts are not V1 inputs and were not opened: credentials, environments, DBs, media, PDFs, logs, reports and generated indexes.

Static source inventory cannot alone prove dynamically registered signals, tasks, router actions, templates or production configuration; those are tracked as coverage limitations.
## Operational entry points

The discovered non-HTTP surface is **73 management-command modules** and **11 signal/task modules** across backend/MDS/MDS client. See [operational entry-point inventory](operational-entrypoints.md). These modules are included in V1 traceability; they must not be dismissed as internal tooling because several can backfill, repair, synchronize, upload, delete, or recalculate consequential data.
