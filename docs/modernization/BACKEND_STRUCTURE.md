# Backend Structure

Current-state detail (apps, LOC hotspots, dependency graph, Celery, tests): [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## Decisions (2026-11-16)

- **No new Django apps.** The target domains (companies, customers, imports, exports, invoices, accounting, planning, reporting, audit, notifications, integrations) map onto the existing 8 apps as packages:

  | Domain | App / package |
  |---|---|
  | licences, imports/exports items, planning, reporting | `license` (`services/`, `views/`, `exporters/`) |
  | allotments | `allotment` |
  | BOE | `bill_of_entry` |
  | invoices / trades | `trade` |
  | reconciliation | `reconciliation` |
  | companies / customers / masters / audit log / integrations (sync, MDS) | `core` |
  | accounts, permissions | `accounts` |
  | notifications / tasks | `tasks` |

  Moving models between apps would mean table renames or `db_table` pinning plus migration-history surgery. That risk to historical data is disproportionate; an ADR in `docs/decisions/` is required before doing it.
- **Layering rule:** `core` is the kernel and must not import domain apps at module level. Done in `ca9dad8b`; the remaining 18 edges are runtime-only (`apps.get_model` / function-local).
- Business math lives in `apps/license/services/balance_calculator.py` and sibling services. Views and serializers call services and never re-derive balances (`.claude/rules/backend.md`).
- A selectors layer is introduced only where a query is reused by 2 or more callers (avoid speculative abstraction).

## Remaining candidates (not started)

- Split files over 800 LOC behind re-exporting `__init__`s: `license/models/core.py` (2.6k), `views/item_pivot_report.py` (2.4k), `services/balance_calculator.py` (2.1k; business-rule review needed), `allotment/views_actions.py`.
- Split `settings.py` with `settings/__init__.py` kept as the entry point, so `DJANGO_SETTINGS_MODULE` is unchanged.
- Remove the dead `ledger` Celery queue from the worker unit (a deploy file, so it needs approval).
