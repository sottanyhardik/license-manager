# 04 — API Reference

All endpoints are prefixed with `/api/`. Authentication: `Authorization: Bearer <access_token>` header required on all endpoints except `/api/auth/login/` and `/api/health/`.

---

## Authentication (`/api/auth/`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login/` | Authenticate; returns `{access, refresh, user}` |
| POST | `/api/auth/logout/` | Blacklist refresh token |
| GET | `/api/auth/me/` | Current user profile |
| PUT/PATCH | `/api/auth/me/` | Update own profile |
| POST | `/api/auth/refresh/` | Refresh access token |
| GET | `/api/auth/users/` | List users (USER_MANAGER / superuser) |
| POST | `/api/auth/users/` | Create user |
| GET | `/api/auth/users/:id/` | Get user |
| PUT/PATCH | `/api/auth/users/:id/` | Update user |
| DELETE | `/api/auth/users/:id/` | Delete user |
| POST | `/api/auth/users/:id/reset-password/` | Reset user password |
| GET | `/api/auth/users/available-roles/` | List 15 available role codes |

---

## Licenses (`/api/licenses/`)

### CRUD
| Method | Path | Description |
|---|---|---|
| GET | `/api/licenses/` | List licenses (paginated, filtered) |
| POST | `/api/licenses/` | Create license |
| GET | `/api/licenses/:id/` | Get license detail |
| PUT/PATCH | `/api/licenses/:id/` | Update license |
| DELETE | `/api/licenses/:id/` | Delete license |

**Key Query Params** (GET list):
- `search` — license_number, exporter, port, sion_norm
- `license_type` — `DFIA` | `INCENTIVE` | `ALL`
- `is_active` — boolean
- `is_expired` — boolean
- `is_null` — boolean
- `company` — importer company ID
- `ordering` — e.g. `-license_date`
- `purchase_status` — comma-separated codes (e.g. `GE,MI,GO`)
- `active_only` — boolean

### Custom Actions
| Method | Path | Description |
|---|---|---|
| GET | `/api/licenses/:id/nested_items/` | Load nested items on demand |
| GET | `/api/licenses/:id/item-usage/` | BOE + allotment usage for item |
| GET | `/api/licenses/:id/balance_pdf/` | Generate balance PDF |
| POST | `/api/licenses/bulk_balance_excel/` | Multi-license Excel export |
| POST | `/api/licenses/parse-pdf/` | OCR parse uploaded license PDF |

---

## License Ledger (`/api/license-ledger/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/license-ledger/` | Paginated license ledger list |
| GET | `/api/license-ledger/:id/` | Single license ledger |
| GET | `/api/license-ledger/:id/ledger_detail/` | Per-company transaction detail |

**Key Query Params**:
- `company` — filter by importer company ID
- `purchase_date_from` / `purchase_date_to` — date range
- `license_type` — `ALL` | `DFIA` | `INCENTIVE`
- `active_only` — boolean
- `no_purchases` — show licenses with no purchase transactions

---

## Incentive Licenses (`/api/incentive-licenses/`)

Standard CRUD endpoint (`GET`, `POST`, `PUT/PATCH`, `DELETE`).

---

## Bill of Entry (`/api/bill-of-entries/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/bill-of-entries/` | List BOEs |
| POST | `/api/bill-of-entries/` | Create BOE |
| GET | `/api/bill-of-entries/:id/` | Get BOE |
| PUT/PATCH | `/api/bill-of-entries/:id/` | Update BOE |
| DELETE | `/api/bill-of-entries/:id/` | Delete BOE |
| POST | `/api/bill-of-entries/:id/generate-transfer-letter/` | Generate transfer letter |

---

## Allotments (`/api/allotments/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/allotments/` | List allotments |
| POST | `/api/allotments/` | Create allotment |
| GET | `/api/allotments/:id/` | Get allotment |
| PUT/PATCH | `/api/allotments/:id/` | Update allotment |
| DELETE | `/api/allotments/:id/` | Delete allotment |
| GET | `/api/allotment-actions/:id/` | Full allotment detail with line items + filters |
| POST | `/api/allotment-actions/:id/generate-transfer-letter/` | Generate transfer letter |

---

## Trades (`/api/trade/trades/`)

**Note:** The URL prefix is `/api/trade/` (registered in `apps/trade/urls.py`), so the full trade endpoint path is `/api/trade/trades/`.

### CRUD

| Method | Path | Description |
|---|---|---|
| GET | `/api/trade/trades/` | List trades (paginated, filtered) |
| POST | `/api/trade/trades/` | Create trade (with nested lines, incentive_lines, payments) |
| GET | `/api/trade/trades/:id/` | Get trade detail |
| PUT/PATCH | `/api/trade/trades/:id/` | Update trade |
| DELETE | `/api/trade/trades/:id/` | Delete trade |

**Key Query Params** (GET list):
- `search` — invoice_number, from_company__name, to_company__name, remarks, lines__sr_number__license__license_number, incentive_license__license_number
- `direction` — `PURCHASE` | `SALE` | `COMMISSION_PURCHASE` | `COMMISSION_SALE`
- `license_type` — `DFIA` | `INCENTIVE`
- `from_company` — company ID (FK autocomplete endpoint: `/masters/companies/`)
- `to_company` — company ID (FK autocomplete endpoint: `/masters/companies/`)
- `boes` — BOE ID (FK autocomplete endpoint: `/bill-of-entries/`)
- `incentive_license` — incentive license ID (FK autocomplete endpoint: `/incentive-licenses/`)
- `invoice_date` — date range filter
- `ordering` — e.g. `-invoice_date` (default ordering enforced on list)

### Custom Actions

| Method | Path | Description |
|---|---|---|
| GET | `/api/trade/trades/:id/summary/` | Trade summary with computed fields |
| POST | `/api/trade/trades/:id/link-trade/` | Bidirectionally link two trades (body: `{"partner_id": <int>}` or `null`) |
| POST | `/api/trade/trades/:id/copy-to-purchase/` | Copy SALE → PURCHASE counterpart |
| POST | `/api/trade/trades/:id/copy-to-sale/` | Copy PURCHASE → SALE counterpart |
| GET | `/api/trade/trades/:id/counterpart/` | Get the paired counterpart trade |
| GET | `/api/trade/trades/:id/generate-bill-of-supply/` | Generate Bill of Supply PDF (SALE only) |
| GET | `/api/trade/trades/:id/generate-purchase-invoice/` | Generate Purchase Invoice PDF (PURCHASE only) |
| POST | `/api/trade/trades/:id/generate-transfer-letter/` | Generate transfer letter |
| POST | `/api/trade/trades/:id/resolve-final-party/` | Authorise final-party classification (SALE only) |
| GET | `/api/trade/trades/prefill-invoice-number/` | Generate next invoice number (query: `direction`, `company_id`, `invoice_date`) |
| GET | `/api/trade/trades/sales-classification-review/` | List SALE trades needing classification |
| POST | `/api/trade/trades/sales-classification-review/import/` | Bulk import classification decisions (CSV) |
| POST | `/api/trade/trades/:id/sales-classification-review/` | Apply classification decision to a SALE |

### POST `/api/trade/trades/` — Create Trade (Sale Quantity Validation)

**Sale Quantity Validation** (applies only to direct SALE without BOEs):

When creating a SALE trade with no BOEs attached (`"boes": []`), the server validates that the total requested quantity per import item does not exceed the available quantity. This prevents over-selling imported goods.

**Validation trigger**: `direction == "SALE"` AND `boes` array is empty.

**Available quantity formula**: `total_quantity − BOE_debited − outstanding_allotted − direct_sale_quantity`

Where:
- **total_quantity**: The import item's stored quantity
- **BOE_debited**: Physical consumption already recorded via BOE RowDetails DEBIT rows
- **outstanding_allotted**: Allotment quantity not yet linked to a BOE
- **direct_sale_quantity**: Quantity consumed by existing unpaired direct SALE lines (no counterpart, no linked BOE)

**Error Response** when quantity exceeds available:
```json
{
  "lines": "SALE quantity 342672.0200 exceeds available quantity 327420.7200 for import item 38728."
}
```
HTTP status: `400 Bad Request`

**When BOEs ARE attached**: This validation is skipped — the BOE linkage itself serves as the physical quantity debit.

**Concurrency protection**: The validation uses `select_for_update()` row locks on import items to prevent two concurrent direct sales from both over-consuming the same item.

**⚠️ UI Balance Discrepancy Warning**: The available quantity shown in the frontend's Customs Ledger section may be **higher** than what this API accepts. The frontend calculates `quantity - boe_debited_quantity` only, omitting `outstanding_allotted` and `direct_sale_quantity`. The stored `item.available_quantity` field (used by the Items Tab) includes all four components and matches the API's validation formula. See BR-17E for the complete analysis of all four calculation paths.

### DELETE `/api/trade/trades/:id/` — Delete Trade

**Permissions:** `TRADE_MANAGER` role required.

**Request:**
```
DELETE /api/trade/trades/677/
Authorization: Bearer <token>
```

**Success Response:** `204 No Content`

**Error Responses:**
- `400 Bad Request` — Trade has a linked counterpart (`counterpart_id` is set). Error: `"This trade has a linked counterpart. Use the audited pair-deletion workflow."`
- `400 Bad Request` — Trade is referenced by protected objects (e.g., `SaleClassificationDecision`, `TradePairAudit`). Error lists the referencing objects.
- `403 Forbidden` — User lacks `TRADE_MANAGER` role.
- `404 Not Found` — Trade ID does not exist.

**Delete Side Effects:**
1. Linked BOE `invoice_no` and `invoice_date` are cleared (if they match the trade's `invoice_number`)
2. Child objects deleted via CASCADE: `LicenseTradeLine`, `IncentiveTradeLine`, `LicenseTradePayment`, `TradeInvoiceDocument`, `InvoiceDocumentAccessToken`, `InvoiceDocumentAuditEvent`
3. M2M relation `boes` is cleared

**Constraints:**
- A trade with a `counterpart` (paired Sale↔Purchase) **cannot** be deleted alone — the `prevent_single_counterpart_delete` signal blocks it
- A trade referenced by `SaleClassificationDecision` or `TradePairAudit` records **cannot** be deleted (PROTECT FK)

### Force Delete (Manual — No API Endpoint)

There is no `DELETE /api/trade/trades/:id/?force=1` endpoint. Force deletion must be performed manually via Django shell or direct database operations when a trade has protecting references.

**Prerequisites**: Django superuser access or database admin access.

**Steps**:

1. **Clear the counterpart link** on both trades:
   ```python
   from apps.trade.models import LicenseTrade, TradePairAudit, SaleClassificationDecision
   
   trade = LicenseTrade.objects.get(pk=<TRADE_ID>)
   counterpart = trade.counterpart
   
   trade.counterpart = None
   trade.save(update_fields=['counterpart'])
   
   if counterpart:
       counterpart.counterpart = None
       counterpart.save(update_fields=['counterpart'])
   ```

2. **Delete protecting audit records**:
   ```python
   TradePairAudit.objects.filter(source=trade).delete()
   TradePairAudit.objects.filter(counterpart=trade).delete()
   SaleClassificationDecision.objects.filter(trade=trade).delete()
   ```

3. **Delete the trade**:
   ```python
   trade.delete()
   ```

**Warning**: Force delete destroys audit trail integrity. The `TradePairAudit` records and `SaleClassificationDecision` records are permanently lost. Use only for data cleanup or error recovery.

**Note**: Django's `QuerySet.delete()` bypasses `pre_delete` signals (including `clear_boe_invoice_on_trade_delete` and `prevent_single_counterpart_delete`), but does NOT bypass `PROTECT` FK constraints. The PROTECT references must still be cleared first.

---

## Tasks (`/api/tasks/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/tasks/` | List tasks (own tasks only; superuser sees all) |
| POST | `/api/tasks/` | Create task |
| GET | `/api/tasks/:id/` | Get task |
| PUT/PATCH | `/api/tasks/:id/` | Update task |
| DELETE | `/api/tasks/:id/` | Delete task |
| POST | `/api/tasks/:id/complete/` | Mark task completed |
| POST | `/api/tasks/:id/reject/` | Reject task (body: `{reason}`) |
| POST | `/api/tasks/:id/reopen/` | Reopen rejected/completed task |
| GET | `/api/tasks/:id/remarks/` | List remarks on task |
| POST | `/api/tasks/:id/remarks/` | Add remark |
| GET | `/api/tasks/assignable_users/` | List users who can be assigned tasks |

---

## Ledger Upload (`/api/upload-ledger/`, `/api/ledger-task-status/`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/upload-ledger/` | Upload CSV/HTM ledger files |
| GET | `/api/ledger-task-status/:task_id/` | Poll Celery task status |

**POST body**: `multipart/form-data` with file(s) field.

**Response**: `{tasks: [{license, task_id}], file}` per uploaded file.

**Task status response**:
```json
{
  "state": "SUCCESS" | "FAILURE" | "PENDING" | "PROGRESS",
  "result": { ... },
  "progress": 42,
  "error": "error message if failed"
}
```

---

## Masters (`/api/masters/`)

All masters follow standard CRUD: `GET`, `POST`, `PUT/PATCH`, `DELETE`.

| Endpoint | Model |
|---|---|
| `/api/masters/companies/` | CompanyModel |
| `/api/masters/ports/` | PortModel |
| `/api/masters/hs-codes/` | HSCodeModel |
| `/api/masters/sion-classes/` | SionNormClassModel |
| `/api/masters/item-names/` | ItemNameModel |
| `/api/masters/exchange-rates/` | ExchangeRateModel |
| `/api/masters/transfer-letters/` | TransferLetterModel |
| `/api/masters/purchase-statuses/` | PurchaseStatus |
| `/api/masters/scheme-codes/` | SchemeCode |
| `/api/masters/notification-numbers/` | NotificationNumber |
| `/api/masters/groups/` | Group (Django) |
| `/api/masters/activity-logs/` | ActivityLog (read-only) |

---

## Reports

| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/` | Dashboard KPI data |
| GET | `/api/expiring-licenses/` | Licenses expiring within N days |
| GET | `/api/active-licenses/` | All active licenses with balances |
| GET | `/api/item-pivot/` | Item pivot report (by SION norm) |
| GET | `/api/item-pivot/available-norms/` | Available SION norm classes for pivot |
| GET | `/api/item-report/` | Item-level balance report |
| GET | `/api/inventory-balance/` | Full inventory balance |
| GET | `/api/reports/inventory-balance/` | Inventory balance Excel download |
| GET | `/api/reports/expiring-licenses/` | Expiring licenses report |
| GET | `/api/reports/active-licenses/` | Active licenses report |
| GET | `/api/reports/item-pivot/` | Item pivot data (JSON format) |
| GET | `/api/reports/item-report/` | Item report data |

---

## SION Planning Rules (`/api/sion-planning-rules/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/sion-planning-rules/` | List rules (filter: `sion`, `is_active`) |
| POST | `/api/sion-planning-rules/` | Create rule |
| GET | `/api/sion-planning-rules/:id/` | Get rule detail |
| PATCH | `/api/sion-planning-rules/:id/` | Update rule |
| DELETE | `/api/sion-planning-rules/:id/` | Delete rule |
| POST | `/api/sion-planning-rules/plan/` | Execute planning for a SION norm |
| POST | `/api/sion-planning-rules/preview/` | Preview planning impact without saving |
| GET | `/api/sion-planning-rules/preview-scoped/` | Preview for exact license + SION |
| POST | `/api/sion-planning-rules/:id/test/` | Test a single rule |
| POST | `/api/sion-planning-rules/reorder/` | Reorder rule priorities |
| GET | `/api/sion-planning-rules/import-items/` | List import items for a SION norm |

**POST /api/sion-planning-rules/ body**:
```json
{
  "sion": 5,
  "name": "DIETARY FIBRE",
  "expression": {
    "operator": "AND",
    "conditions": [
      {
        "field": "PRODUCT_DESCRIPTION",
        "comparator": "CONTAINS",
        "value": "dietary fibre"
      },
      {
        "operator": "OR",
        "conditions": [
          { "field": "HSN", "comparator": "STARTS_WITH", "value": "0802" },
          { "field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "0802" }
        ]
      }
    ]
  },
  "max_unit_price": "2.70",
  "unit": "KG",
  "is_active": true,
  "strategy": "STANDARD",
  "import_item": 42,
  "percentage_rows": [],
  "unit_value_rows": [],
  "cif_restriction_percentage": "5"
}
```

**Expression JSON Format**:

The `expression` field is a JSON tree with AND/OR/NOT boolean operators and leaf conditions. The backend evaluator (`sion_rule_engine.py`) uses a safe whitelist — no `eval` or SQL injection.

- **Boolean nodes**: `{ "operator": "AND" | "OR" | "NOT", "conditions": [...] }`
- **Leaf conditions**: `{ "field": "HSN" | "PRODUCT_DESCRIPTION", "comparator": "...", "value": "..." }`
- **Depth limit**: 12 levels, **node limit**: 128 nodes
- **Empty root** `{}` matches nothing (not the vacuous truth of `all([])`)

**Match Fields Available in UI**:

| Field | Allowed Comparators | Backend Context Key |
|---|---|---|
| `HSN` | `STARTS_WITH`, `NOT_STARTS_WITH` | `hs_code` |
| `PRODUCT_DESCRIPTION` | `CONTAINS`, `NOT_CONTAINS` | `description` |

**Backend-Only Fields** (not exposed in planning UI but supported by evaluator):

| Field | Backend Context Key |
|---|---|
| `HSN_DIGITS` | `hs_code` |
| `ITEM_KEY` | `item_key` |
| `available_qty`, `total_qty`, `cif_fc`, `license_balance_cif`, `unit`, `serial_number`, `condition_type`, `is_restricted`, `available_value` | Same name |

**Text Normalization**: Case-insensitive, whitespace-collapsed. HSN values have non-alphanumeric characters stripped before comparison.

**cif_restriction_percentage** (Feature Request — Not Yet Implemented):
- Nullable Decimal field on the rule and on each percentage/unit-value row
- Allowed values: `2`, `3`, `5`, `10`, or `null` (no restriction)
- When set, the planner skips items whose `debited_cif + allotted_cif` exceeds this percentage of the item's total CIF value

**POST /api/sion-planning-rules/plan/ body**:
```json
{
  "sion": 5,
  "mode": "NEW"
}
```
- `mode`: `"NEW"` (plan only unlicensed) or `"ALL"` (re-plan all eligible)

**Preview response**:
```json
{
  "sion": "E5",
  "summary": {
    "licenses_matched": 10,
    "licenses_new": 3,
    "licenses_changed": 5,
    "licenses_unchanged": 2,
    "licenses_shortage": 0,
    "rules_processed": 8
  },
  "licenses": [ ... ]
}
```

---

## System

| Method | Path | Description |
|---|---|---|
| GET | `/api/health/` | Health check |
| GET | `/api/masters/throttle-status/` | Throttle status |
| POST | `/api/masters/throttle-reset/` | Reset throttle (superuser) |

---

## Common Response Formats

### Paginated List
```json
{
  "count": 150,
  "next": "/api/licenses/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

### Validation Error (DRF)
```json
{
  "field_name": ["Error description"],
  "non_field_errors": ["Cross-field error"]
}
```

---

## Authentication Tokens

| Token | Lifetime | Notes |
|---|---|---|
| Access token | 60 minutes | Bearer header; auto-refreshed 5 min before expiry |
| Refresh token | 7 days | Stored in localStorage; blacklisted on logout |

Frontend auto-refreshes access tokens proactively. Idle > 30 minutes → auto logout with redirect to `/login?reason=idle`.
