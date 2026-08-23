# BL-LEDGER-01 — "Link BOE to Trade" can silently un-hide a genuinely-hidden previous-owner BOE, with no audit trail, inflating the license balance

## Files
- `backend/apps/reconciliation/views.py`, `ReconciliationViewSet.link` (POST `/reconciliation/link/`).
- `backend/apps/trade/services/trade_service.py`, `stamp_boe_invoice_from_trade` (lines ~195-213).
- `backend/apps/bill_of_entry/models.py`, `annotate_and_exclude_hidden` (the hidden-BOE detection this bypasses).

## License(s) / rows used
- License `5211016017`.
- BOE `bill_of_entry_billofentrymodel.id = 27511` (`bill_of_entry_number` `4505467`), `invoice_no = 'OTH'`.
- Its DEBIT row `bill_of_entry_rowdetails.id = 274336`, `cif_fc = 267928.000`.
- Unrelated SALE trade `trade_licensetrade.id = 542`, `invoice_number = 'PUR/2026-27/0007'` — chosen only because it has a real invoice number and does not currently reference this BOE at all.

## What was done
Confirmed via `ReconciliationLog` that BOE 27511 was deliberately, audit-logged **hidden** (a single `HIDE_BOE` entry on 2026-07-30, no later `RESTORE_BOE`) — i.e. `genuinely_hidden_boe_ids([27511])` returns `True` for it today. Then, inside one `transaction.atomic()` block (rolled back afterward — no permanent DB change), reproduced exactly what `ReconciliationViewSet.link()` executes for a `POST /reconciliation/link/` request: `trade.boes.add(boe)` followed by `stamp_boe_invoice_from_trade(trade, boe)`.

## Expected result
Attaching a BOE to a completely unrelated Sale trade for invoicing purposes (the `link` action's stated purpose — "re-stamp the BOE's invoice_no/invoice_date... so the two 'attach a BOE' code paths can't drift apart") should never change whether that BOE counts as a genuinely-hidden, previous-owner utilisation. The hidden/visible state is supposed to be governed exclusively by the sanctioned `hide_boe`/`restore_boe` workflow (`_apply_hide`/`_apply_restore` in `apps/bill_of_entry/services/boe_service.py`), which always writes its own `ReconciliationLog` entry and always calls `update_license_flags` via `_refresh_licenses`.

## Actual result
Because `stamp_boe_invoice_from_trade` unconditionally overwrites `boe.invoice_no` whenever `trade.invoice_number` is set — with no check for whether the BOE currently carries the `OTH_INVOICE_MARKER` hidden flag — it silently rewrote `invoice_no` from `'OTH'` to `'PUR/2026-27/0007'`. `annotate_and_exclude_hidden`'s hidden-row Subquery matches on `invoice_no == OTH_INVOICE_MARKER` first; the instant that string no longer matches, the BOE is unconditionally treated as ordinary, visible debit everywhere (Financial Ledger, Customs Ledger, per-item/per-license balances), regardless of its `ReconciliationLog` history.

Measured effect on license `5211016017`:
- Live `get_balance_cif()` / `calculate_financial_balance()`: `3322.35` → `271250.35` (**+267,928.00**, exactly the un-hidden row's `cif_fc`).
- Cached `license_licensebalance.balance_cif`: stayed at `3322.35` (same signal gap as BL-LEDGER-02 — `BillOfEntryModel` has no `post_save`/`post_delete` receiver in `apps/license/signals.py` at all, only its child `RowDetails` does).
- `ReconciliationLog`: **no new entry** records the `invoice_no` change or the resulting un-hide. `ReconciliationViewSet.link()` only writes one `ACTION_LINK` row with `before`/`after` = `{"boe_ids": [...]}`; it never touches the hidden-state audit trail the way `restore_boe` deliberately does. An auditor reviewing this BOE's `ReconciliationLog` afterward would see only the original `HIDE_BOE` entry from 2026-07-30 and have no way to know it was ever un-hidden, when, or by whom.

## Why the current algorithm fails
`stamp_boe_invoice_from_trade` is a blind field-stamp with no hidden-state guard, shared between the reconciliation panel's `link` action and `LicenseTradeSerializer.update()`'s bulk re-stamp of every BOE on a trade. Neither call site checks `boe.invoice_no == OTH_INVOICE_MARKER` (nor the `ReconciliationLog`-based "genuinely hidden" test that `annotate_and_exclude_hidden` itself insists is the only reliable signal, precisely because raw `invoice_no == 'OTH'` collides with ~35-40% of ordinary legacy data) before overwriting `invoice_no`. Any Sale trade that happens to have its own `invoice_number` set and gets linked to a BOE that a user had previously, deliberately hidden will reproduce this exact un-hide — no malicious intent or unusual input required, just an ordinary reconciliation-workbench click on a BOE that happens to already be flagged hidden.

## Reachability
Directly live: `ReconciliationViewSet.link` is a real `POST` action wired into `apps/reconciliation/urls.py` and callable from the Reconciliation workbench UI by any user with the relevant permission — not a management command or an internal-only code path. `LicenseTradeSerializer.update()`'s own re-stamp-on-every-linked-BOE loop is an equally live second entry point into the same unguarded stamp function.

## Severity
Critical / high: this is a genuine data-integrity + audit-trail defect — a routine action (linking a BOE to a trade for invoicing) can silently reverse a deliberate, audit-logged "this belongs to the previous owner" determination, inflate the license's reported Balance CIF by the full previously-excluded amount, and leave zero trace that the reversal happened.

## Ambiguity
None on the mechanism (directly reproduced, and the "genuinely hidden" precondition was independently verified from real `ReconciliationLog` data before the test). What IS a business decision, not something to guess at: whether the correct fix is (a) have `stamp_boe_invoice_from_trade` refuse/no-op when the BOE is currently genuinely hidden (require an explicit `restore_boe` first), (b) have it go through `_apply_restore`'s audited path when it detects it's about to un-hide a BOE, or (c) something else product-specific (e.g. warn the user and require confirmation). This read-only pass does not pick one.
