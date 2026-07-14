# Workflow Graph

> Living document. Add a workflow when a module is implemented.
> Source: `docs/07-user-flows.md` for full user flows.

## Core Business Workflows

### License Lifecycle

```
Create License (DFIA / Incentive)
  ↓
Add Import Items (SR numbers, CIF values, HS codes)
  ↓
License Balance materialised (post_save signal → LicenseBalance)
  ↓
┌──────────────────────────────────────────────────────┐
│  Consumption paths (any combination)                 │
│                                                      │
│  Allotment (AT/TR)          Bill of Entry (BOE)      │
│  AllotmentItems.save()  →   RowDetails.save()  →     │
│  allotted_qty += n          debited_qty += n         │
│       └─────────────────────┘                        │
│       available_qty = authorised - debited - allotted│
└──────────────────────────────────────────────────────┘
  ↓
License Expiry (nightly: update_license_expiry command)
  ↓
Balance Reports / Ledger PDFs
```

### Trade Invoice Workflow

```
Select License SRs + Billing Mode (QTY / CIF_INR / FOB_INR)
  ↓
Enter line items (pct, qty, rates)
  ↓
Amount computed: pct × base / 100  (3 decimal precision)
  ↓
Incentive lines (license_value × rate_pct / 100)
  ↓
Save Trade → recompute_totals() → total_amount_inr
  ↓
Generate Purchase Invoice PDF or Bill of Supply PDF
  ↓
Record payments (LicenseTradePayment)
  ↓
due_amount = total - paid_or_received
```

### BOE Ledger Upload Workflow

```
Upload government ledger file (PDF/Excel)
  ↓
Parse → match rows to LicenseImportItemsModel by sr_number
  ↓
Match found → create RowDetails (frozen=True)
No match    → create RowDetails (is_dispute=True)
  ↓
Frozen rows: cannot be edited/deleted via API
Dispute rows: manually link to correct import item
  ↓
License balance auto-recomputed
```

### User Authentication Workflow

```
POST /api/v1/auth/login/ {username, password}
  ↓
Validate credentials → issue access token (30 min) + refresh token (7 days)
  ↓
Frontend stores tokens → attaches Bearer header to every request
  ↓
401 received → attempt token refresh → retry original request
  ↓
Refresh fails → logout + redirect to /login
  ↓
Idle 30 min → auto-logout (client-side timer)
```
