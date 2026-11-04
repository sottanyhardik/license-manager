# Opening CIF — Data Lineage and Consumer Audit

**Subject:** `LicenseBalanceCalculator.calculate_opening_balance_for_licenses`
**Location:** `backend/apps/license/services/balance_calculator.py:1549–1587`
**Status:** Investigation complete. System-wide fix **NOT COMPLETE**: one business decision is required (section 7).
**Supersedes:** nothing. Linked from `ledger-serverreadiness-checkpoint.md`.
**Instruction:** "Establish one authoritative Opening CIF calculation used consistently throughout License Manager."

## 1. Answer

`calculate_opening_balance_for_licenses` stores and reads no opening value. It derives one from three original records through a three-way gate.

- **Credit (authoritative base):** `SUM(LicenseExportItemModel.cif_fc)` per licence. These rows are the licence's export entitlement. They are written by the licence serializer from submitted or parsed licence data (`apps/license/serializers/_license_write.py:271, 408`). Nothing derives them from trades or BOEs.
- **Hidden debit:** `SUM(RowDetails.cif_fc)` for `transaction_type = DEBIT` on hidden (previous-owner) BOEs.
- **Purchase:** `SUM(LicenseTradeLine.cif_fc)` for PURCHASE and COMMISSION_PURCHASE trades, plus a presence test on the same trades.

So the authoritative source is the licence's export-item CIF. The function is an aggregator over that record, not an independent source.

## 2. Exact formula (from source)

```
credit        = Σ LicenseExportItemModel.cif_fc                     (licence master entitlement)
hidden        = Σ RowDetails.cif_fc, DEBIT, hidden BOE              (previous-owner debit)
purchase      = Σ LicenseTradeLine.cif_fc, PURCHASE/COMMISSION_PURCHASE
has_purchase  = ∃ PURCHASE/COMMISSION_PURCHASE trade line

opening = credit − hidden − purchase    if hidden > 0
          0                             elif has_purchase
          credit                        otherwise
```

Source lines: gate `balance_calculator.py:1565–1586`; hidden `591–614`; credit `616–640`; has_purchase `1184–1200`; purchase `1305–1325`.

## 3. Call hierarchy

```
GET /api/licenses/{id}/overview-summary/          views/license_overview.py:32
 └─ balance_snapshot.get_snapshot                  services/balance_snapshot.py:169
     └─ calculate_opening_balance_for_licenses

calculate_financial_components_for_licenses        balance_calculator.py:1700
 ├─ calculate_credit_for_licenses                  (map passed as credit_map — added this cycle)
 ├─ calculate_purchase_credit_for_licenses         (map passed as purchase_credit_map)
 └─ calculate_opening_balance_for_licenses
     ├─ calculate_hidden_boe_debit_total_for_licenses  (591)
     ├─ calculate_credit_for_licenses                  (616, skipped when credit_map supplied)
     ├─ has_purchase_for_licenses                      (1184)
     └─ calculate_purchase_credit_for_licenses         (1305, skipped when map supplied)
```

Reference implementation: `calculate_opening_balance` (line 1501), the single-licence gate that anchors `calculate_financial_balance`.

## 4. Tables and fields

| Component | Model / table | Field | Filter |
|---|---|---|---|
| Credit | `LicenseExportItemModel` / `license_licenseexportitemmodel` | `cif_fc`, `license_id` | none |
| Hidden debit | `RowDetails` / `bill_of_entry_rowdetails` | `cif_fc`, `sr_number.license_id` | `transaction_type=DEBIT`, hidden-BOE annotation (`annotate_and_exclude_hidden`) |
| Purchase | `LicenseTradeLine` / `trade_licensetradeline` | `cif_fc`, `sr_number.license_id` | `trade.direction ∈ {PURCHASE, COMMISSION_PURCHASE}` |

Dates do not enter the formula. Cancellation and reversal are handled only inside the underlying helpers' filters. I did not re-derive those filters.

## 5. Competing implementations

| Location | Definition | Status |
|---|---|---|
| `LicenseDetailsModel.opening_balance` (`models/core.py:293`) | Credit only, no gate | Legitimate distinct concept: **entitlement** |
| `LicenseDetailsModel` `_calculate_license_credit` (`models/core.py:314`) | Credit via `calculate_credit` | Same source as above |
| `calculate_opening_balance` (`balance_calculator.py:1501`) | Gated, single licence | Reference for the batched gate |
| `calculate_opening_balance_for_licenses` (`:1549`) | Gated, batched | Function under investigation |
| `LicenseImportItemsModel.opening_balance` (`models/core.py:1176`) | Sum of `item_details.qty` with `transaction_type='C'` | Quantity, not CIF. Different unit. Not a duplicate. |
| Canonical ledger opening (`canonical_ledger_batch.py:192`, `canonical_ledger_service.py`) | Credit only | Same concept as the model property. The ledger suppresses the opening row when a purchase exists, so purchase is not double-counted. |

## 6. Verification against data

Method: for every DFIA licence in the development database, read-only: compute credit, purchase and has-purchase with direct ORM aggregates, compute hidden debit with the single-licence method, apply the gate in Python, and compare with the batched output.

| Result | Count |
|---|---|
| DFIA licences | 222 |
| Hidden debit > 0 | 97 |
| Purchase, no hidden debit | 118 |
| Neither | 7 |
| Mismatches | **0** |

Limitation: hidden-debit lineage was checked against the single-licence method, not a raw `RowDetails` query. Credit, purchase and has-purchase were checked against raw ORM aggregates.

Not yet verified: RODTEP and other incentive licence types (the batched gate is DFIA-only in its inputs), the Excel and PDF reconciliation, and browser display.

## 7. Blocker: two openings for one licence

The system has two legitimate-looking opening figures for the same licence.

- **Entitlement (ungated):** the canonical ledger and the model property use credit alone.
- **Financial opening (gated):** the Financial Available Balance and the overview use the three-way gate.

They differ whenever hidden debit or purchase is present. Both are documented in their own modules. Merging them is a financial business decision, not a code fix. Choosing one changes reported balances. Until the owner decides, the system must keep the two concepts separate, with distinct names.

Required decision: which figure is shown as "Opening CIF" in each screen, and whether the ledger should show entitlement or the gated opening.

## 8. Consumer matrix (current state)

| Screen / API / report | Current source | Intended source | Status |
|---|---|---|---|
| Overview summary API | Gated opening via snapshot | Gated financial opening | Consistent with the financial engine. Not reconciled against the UI. |
| Financial Available Balance | Gated opening | Gated financial opening | Consistent. |
| Canonical ledger (list and detail) | Credit (entitlement) | Decision required (section 7) | Ungated by design, documented. |
| Frontend display of opening | Not yet inspected | Backend value only | **Not verified** |
| Excel export | Not yet inspected | Same as the screen it mirrors | **Not verified** |
| PDF export | Not yet inspected | Same as the screen it mirrors | **Not verified** |

## 9. Recommended single source of truth

- Keep `calculate_opening_balance_for_licenses` as the single gated implementation for financial opening. No second gate anywhere.
- Name the ungated figure "entitlement" everywhere it appears, and keep it separate from "opening".
- Keep `LicenseImportItemsModel.opening_balance` out of CIF calculations entirely.
- Consumers must display the backend value. The frontend must not recompute it.

## 10. Regression tests required

1. Batched output equals independent per-licence aggregates for a fixture covering all three branches (partly covered by the reconciliation above; needs a permanent test).
2. Hidden-debit lineage from raw `RowDetails`, removing the single-licence dependency.
3. Partial purchase: purchase CIF below export credit.
4. Mixed PURCHASE and COMMISSION_PURCHASE trades.
5. Cancelled and reversed trade and BOE rows excluded.
6. Entitlement and gated opening differ only where expected, asserted explicitly.
7. Incentive licence types, or an explicit test that they are out of scope.

## 11. Changes made in this investigation

None to logic or data. The earlier `credit_map` pass-through is in the working tree and unchanged. The overview query budget of 47 still holds.

## 12. Exact next action

Obtain the business decision in section 7. Then add regression tests 1 and 4–6, and inspect the frontend, Excel and PDF consumers in section 8.

## 13. Correction to sections 5 and 7

`LicenseDetailsModel.opening_balance` (`models/core.py:291–296`, a `@cached_property`) is the **credit input**, not an alternative opening. It returns `calculate_credit()`, the export CIF. Its consumers:

- `license_balance_ledger_builder.py:291` (`build_financial_ledger`): uses it as the opening, then applies the hidden-BOE debit and purchase adjustments as its own rows. **This builder implements the gate row by row.**
- `license_balance_ledger_builder.py:789`: same credit input.
- `item_report.py:66, 450`, `tables.py:47`, and `apps/core/management/commands/report_fetch.py` (several `TOTAL CIF` lines): display or report use of the credit.

Consequence: there are two implementations of the same gate, the numeric `calculate_opening_balance_for_licenses` and the row-based `build_financial_ledger`. Both start from the same credit. The "two openings" blocker in section 7 is therefore about which gate output a screen shows, not about the property. The two gate implementations must be reconciled by a test before any consolidation. No formula has been changed.
