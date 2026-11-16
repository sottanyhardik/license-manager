# BOE one-page workspace — shared API contract (orchestrator-owned, 2026-11-16)

Base SHA: `e6dfc9b7cd74e0cdd485e90bbaa4c87e73011a31` (feature/version5). Tasks T-020 (backend),
T-021 (performance), T-022 (frontend) build against THIS file. Changes go through the orchestrator.

## Principles
- ADDITIVE only. Existing `/api/bill-of-entries/` list/detail/actions are untouched (response shapes,
  permissions, filters). `backend/apps/bill_of_entry/views/boe.py` and `serializers.py` are NOT edited
  (a parallel unreviewed branch `feature/erp-impl-boe-perf` modifies them — avoid conflicts).
- Permission: `apps.accounts.permissions.BillOfEntryPermission` (read roles BOE_MANAGER, BOE_VIEWER,
  ACCOUNT_ACCESS, TL_GENERATE). Both endpoints are GET-only.
- Money/qty: Decimal end-to-end, serialized as STRINGS (cif 2dp, qty 3dp). Never float.
- Mutations reuse EXISTING endpoints (see bottom). No new write endpoints.
- No migrations in this batch unless T-021 proves an index with EXPLAIN on local data (then a separate
  erp-database task is created by the orchestrator).

## URLs (registered in `backend/apps/bill_of_entry/urls.py` BEFORE `include(router.urls)`, otherwise
the router's `bill-of-entries/{pk}/` route swallows `workspace`)
- `GET /api/bill-of-entries/workspace/`                   → list + KPI summary
- `GET /api/bill-of-entries/<int:pk>/workspace-detail/`   → lazy drawer detail

## Reconciliation status (derived, read-only — mirrors EXISTING predicates, no new rule)
Precedence (first match wins):
1. `HIDDEN`    — genuinely hidden previous-owner BOE: `annotate_and_exclude_hidden(qs, hidden_only=True)`
                 semantics (invoice_no == "OTH" AND latest HIDE/RESTORE log is HIDE_BOE).
2. `MATCHED`   — linked to ≥1 `LicenseTrade` via `LicenseTrade.boes` (reverse `license_trades`) —
                 same signal `reconciliation.services.queries.summary()["matched"]` uses.
3. `EXTERNAL`  — any debit row has an ACTIVE + is_current `ExternalInvoiceLink`.
4. `PENDING`   — `invoice_no` stamped (non-null, non-empty) but no trade link and no external link.
5. `UNMATCHED` — no invoice_no and no active external link. This set MUST equal
                 `queries.missing_invoice()` minus HIDDEN/MATCHED BOEs (test it).
Computed with `Exists()` subqueries in the list SQL (no per-row queries).

## 1. GET /api/bill-of-entries/workspace/
Query params (all optional):
- `page` (1-based, default 1), `page_size` (default 25, max 100)
- `search` — icontains over bill_of_entry_number, invoice_no, company name, licence number
- `bill_of_entry_number`, `invoice_no`, `license_number` (icontains), `company` (id), `port` (id)
- `date_from`, `date_to` (YYYY-MM-DD on bill_of_entry_date)
- `reconciliation_status` — comma list of MATCHED,EXTERNAL,PENDING,UNMATCHED,HIDDEN
- `ordering` — one of bill_of_entry_date, bill_of_entry_number, company_name, port_name,
  total_cif_fc, total_quantity, item_count, modified_on; prefix `-` for desc. Default
  `-bill_of_entry_date,-bill_of_entry_number` (+ `-id` tiebreak). Unknown value → default.
- `include_summary` — `true` (default) / `false`
Invalid date / page → 400 `{"detail": "..."}`.

Response 200:
```json
{
  "count": 123, "page": 1, "page_size": 25, "num_pages": 5,
  "results": [{
    "id": 1, "bill_of_entry_number": "1234567", "bill_of_entry_date": "2025-01-31",
    "port_id": 3, "port_name": "INNSA1", "company_id": 9, "company_name": "ACME",
    "invoice_no": "INV-1", "invoice_date": "2025-02-01", "product_name": "…",
    "license_numbers": ["0310000001"], "item_count": 2,
    "total_quantity": "100.000", "total_cif_fc": "1234.56", "total_cif_inr": "104321.00",
    "invoice_allocated_cif_fc": "1000.00",
    "reconciliation_status": "MATCHED", "has_dispute": false, "has_pdf": true, "is_fetch": false,
    "modified_on": "2025-02-01T10:00:00Z"
  }],
  "summary": {
    "total_boes": 123, "total_cif_fc": "…", "total_cif_inr": "…", "total_quantity": "…",
    "matched": 50, "external": 3, "pending": 20, "unmatched": 45, "hidden": 5
  }
}
```
- Totals = SUM over ALL RowDetails of the BOE (identical to existing `get_total_fc/inr/quantity`).
  `total_cif_fc` therefore equals the existing list's `total_fc` before its 0dp quantize — expose 2dp.
- `invoice_allocated_cif_fc` = SUM of ACTIVE + is_current `InvoiceBOEAllocation.allocated_cif_fc`
  on the BOE's rows. It is NOT "Utilised CIF" (a licence-level canonical term) — never label it so.
- `summary` is over the FILTERED set (all pages), excluding the `reconciliation_status` filter for the
  status counts? NO — keep it simple: summary is over exactly the filtered set. `total_quantity` sums
  mixed units; UI must label it "mixed units".
- Query budget: ≤ 8 queries total for page_size 25 AND 100 (count, page, licence-numbers batch,
  summary aggregate(s), auth/session). Must not grow with page size.

## 2. GET /api/bill-of-entries/<pk>/workspace-detail/
404 for unknown pk. Response 200:
```json
{
  "boe": { "...all list-row fields...", "exchange_rate": "84.5000", "appraisement": null,
           "ooc_date": null, "cha": null, "comments": null, "planning_target_item_name": null,
           "allotment_ids": [4], "created_on": "…", "created_by": "user", "modified_by": "user" },
  "items": [{ "id": 10, "license_id": 7, "license_number": "…", "item_serial_number": 1,
              "item_description": "…", "hs_code": "…", "transaction_type": "D", "qty": "10.000",
              "cif_fc": "100.00", "cif_inr": "8450.00", "is_frozen": false, "is_dispute": false,
              "invoice_allocated_cif_fc": "100.00", "external_invoice_number": null }],
  "licences": [{ "license_id": 7, "license_number": "…", "boe_cif_fc": "100.00", "boe_qty": "10.000",
                 "financial_available_cif": "-25.00", "is_over_utilised": true }],
  "allotments": [{ "id": 4, "item_name": "…", "invoice": "…", "company": "…",
                   "required_quantity": "…", "allocated_cif_fc": "…" }],
  "invoices": [{ "trade_id": 2, "invoice_number": "…", "invoice_date": "…", "direction": "SALE",
                 "allocated_cif_fc": "…" }],
  "reconciliation": { "status": "MATCHED", "total_cif_fc": "…", "invoice_allocated_cif_fc": "…",
                      "notes": [{ "id": 1, "status": "…", "text": "…", "created_on": "…" }] },
  "documents": [{ "kind": "boe_pdf", "name": "x.pdf", "url": "/api/media/boe_copies/x.pdf" }],
  "audit": [{ "id": 1, "action": "LINK", "reason": "", "user": "u", "created_on": "…" }],
  "permissions": { "can_write": true }
}
```
- `financial_available_cif` MUST come from
  `LicenseBalanceCalculator.calculate_financial_balance_for_licenses(ids)` (batched twin of
  `calculate_financial_balance`) — SIGNED, never floored (OD-01). `is_over_utilised = value < 0`.
  Do NOT use `customs_available_cif` / `calculate_balance` here.
- `audit` = latest 50 `ReconciliationLog` rows for the BOE (newest first).
- Fixed query count (does not grow with item count / licence count beyond the bulk balance calls).

## Existing endpoints the UI reuses for actions (no new writes)
- Create / Edit BOE: existing pages `/bill-of-entries/create`, `/bill-of-entries/:id/edit` (MasterForm;
  RHF/Zod validation lives there). Workspace opens them and refetches on return.
- Inline invoice number: `POST /api/bill-of-entries/{id}/update-invoice-no/` `{invoice_no}`
- Resolve dispute: `POST /api/bill-of-entries/{id}/resolve-dispute/`
- Update product name: `POST /api/bill-of-entries/{id}/update-product-name/`
- Transfer letter: page `/bill-of-entries/:id/generate-transfer-letter`
- Export: `GET /api/bill-of-entries/export/?…` (existing action in views_export.py — pass same filters it accepts)
- Allocate / match invoice / reconcile / audit log: Reconciliation panel `/reconciliation` and
  `/api/reconciliation/*` (link, merge-boe, note, recalculate, audit-log).
- Document: `boe_pdf_copy` URL via protected media; upload stays in existing Fetch/PDF-parse flow
  (`POST /api/bill-of-entries/parse-pdf/`).
