# API contract standards

Rule: **API contracts are frozen; changes are additive only** (ARCHITECTURE_RULES rule 7, ADR-003 §5). Contract tests: `backend/tests/test_api_*.py`, BOE pins in `apps/bill_of_entry/tests/test_boe_api_contract.py` (WS4). Any change → flag `API CONTRACT CHANGE`.

## Lists

| Item | Standard | Source |
|---|---|---|
| Pagination | `{count, next, previous, results}`; 25/page; `?page`, `?page_size` (max 200) | `apps/core/pagination.py:22`, `settings.py:284-285` |
| Master metadata | `MasterViewSet` adds `metadata` incl. `filter_config` to responses | `core/views/master_view.py:638`, `:676` |
| Filtering | advanced filters via `filter_config` (OR logic) + `filterset_class` | `master_view.py:332`; BOE `BOEFilterSet` |
| Ordering | BOE default `-bill_of_entry_date, -bill_of_entry_number` | `bill_of_entry/api/views.py:114` |

## Error envelopes (mixed — FROZEN, do not normalise)

No custom `EXCEPTION_HANDLER` is configured (`lmanagement/settings.py` REST_FRAMEWORK block).

| Shape | Where |
|---|---|
| `{'error': msg}` | `api_error` helper; `fetch-allotment-details` (400 missing id, 500 on any failure: `views.py:226-234`); BOE merge 404/400 (`views.py:265-268`) |
| `{'detail': msg}` | DRF default; `parse-pdf` 400/422; `/reconciliation/merge-boe/` |
| `text/plain` | BOE export 400/503 (`views_export.py:42`) |
| `{success: false, message}` | `update-product-name` (400 only for "No items") |
| field errors `{field: [..]}` | serializer validation |

## Permissions (`backend/apps/accounts/permissions.py`)

| Class | Read | Write | Used by |
|---|---|---|---|
| `BillOfEntryPermission` `:60` | BOE_MANAGER, BOE_VIEWER, ACCOUNT_ACCESS, TL_GENERATE | BOE_MANAGER | BOE viewset default |
| `AccountAccessPermission` `:150` | `_roles` = ACCOUNT_ACCESS, BOE_MANAGER, **BOE_VIEWER** (`:156`) | same | `update-invoice-no` (BOE_VIEWER can write: owner escalation) |
| `TransferLetterPermission` `:166` | see class | — | `generate-transfer-letter` |
| `LicenseBalanceLedgerPermission` `:240` | see `read_roles` `:274` | hide/restore need BOE_MANAGER **and** LICENSE_MANAGER (`:298-299`) | licence-hosted hide/restore |
| `ReconciliationPermission` `:72` | trade/BOE/account roles `:84` | TRADE_MANAGER **and** BOE_MANAGER (`:97-99`) | `/reconciliation/*` |

## Rules for new BOE endpoints

1. Add, never rename or remove fields. New fields are optional.
2. Reuse the existing error shape of the endpoint family; do not introduce a new envelope.
3. Put permission logic in `accounts/permissions.py`, not views.
4. Business logic in `boe_service`; view = parse, call, respond (rule 1).
5. Add a contract test pinning status codes and keys.
