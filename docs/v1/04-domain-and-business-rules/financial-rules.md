# Financial and entitlement rules

## Verified current behavior

`balance_calculator.py` has two intentional engines, both two-decimal quantized and floored at zero:

| Output | Formula summary | Material inputs |
| --- | --- | --- |
| Customs balance | export CIF − visible BOE debit − allotment debit | hidden BOE treatment, allotments |
| Financial balance | opening + purchases − sales − unmatched BOE debit − outstanding allotment | trade linkage, purchases, matching/allocation state |

### Verified against source, 2026-10-31 — three formulas, not two

The table above is incomplete. `balance_calculator.py` contains **three** public balance figures, all quantized to 2 dp and floored at zero:

| Method (`balance_calculator.py`) | Formula | Hidden BOE rows | Used by (non-test callers) |
| --- | --- | --- | --- |
| `calculate_balance` (lines ~1349–1403) | Credit − (non-hidden BOE debit + outstanding allotment) | **Excluded** | `balance_snapshot.py` `balance_map` (`calculate_balance_for_licenses`, line ~156) → snapshot `customs_balance` (and `balance_difference`) |
| `calculate_customs_balance` (lines ~1406–1431) | Credit − (all BOE debit incl. hidden + outstanding allotment) | **Included** | Customs ledger reconciliation; `build_customs_ledger` final `computed_balance` matches it |
| `calculate_financial_balance` (lines ~1572–1651) | Opening + purchase credit − sale trade debit − `calculate_debit` (allocation-aware) − outstanding allotment | Via opening-balance rule | Model property `LicenseDetailsModel.get_balance_cif`; list view `live_balance_map` (`views/license.py:315`); export `_live_balance_export_map` (`views/license.py:331`); snapshot `balance_cif` and `financial_balance`; about 20 other modules |

Consistent today: the model property, list view, export and persisted `balance_cif` all use the financial formula.

**Discrepancy under D2 (not changed):** the snapshot's `customs_balance` uses `calculate_balance` (hidden rows excluded), while the customs ledger and `calculate_customs_balance` include hidden rows. For a licence with hidden BOEs these differ, and `balance_difference` (financial − customs) inherits the gap. The docstring of `calculate_balance` says it "does NOT reconcile with `build_customs_ledger()`" for licences with hidden BOEs.

**Stale docstring:** the serializer docstring at `apps/license/serializers/license.py` (~lines 826–839) says the list view uses `calculate_balance_for_licenses`. The view actually injects `calculate_financial_balance_for_licenses`.

**Characterization evidence:** `backend/apps/license/tests/test_balance_semantics_d2_characterization.py` pins all three values on one synthetic hidden-BOE licence (93,000.00 / 63,000.00 / 48,000.00), the customs ledger final figure (63,000.00), and the snapshot divergence. **6 passed, exit 0**, 2026-10-31, on an isolated test database. Those tests assert current behaviour only and must be updated together with any approved D2 change.

**Worked example (synthetic):** export CIF 100,000; hidden BOE 30,000; visible BOE 5,000; outstanding allotment 2,000; purchase 20,000; sale 15,000.
- `calculate_balance` = 100,000 − (5,000 + 2,000) = **93,000**
- `calculate_customs_balance` = 100,000 − (30,000 + 5,000 + 2,000) = **63,000**
- `calculate_financial_balance` = 100,000 − 50,000 (hidden + purchase) + 20,000 − 5,000 − 2,000 − 15,000 = **48,000** (matches the repro test `test_license_5211016017_repro_case` expectation of 48,000)

Owner decision required: which figure the snapshot's `customs_balance` and `balance_difference` must show. Options are (a) keep and rename to match `calculate_balance` semantics; (b) switch to `calculate_customs_balance` (changes stored values and every consumer of `balance_difference`); (c) keep the non-hidden figure for an explicit "visible BOE" column. No option is applied until D2 is approved.

Allocation behavior is protected by tests for stale-cache handling, live CIF validation, plan-line isolation, reversal and exact boundaries (**Verified by test**). Hidden BOEs, legacy BOE-to-sale linkage and plan residuals materially alter results (**Verified by code**).

Canonical-ledger tests include company-isolation and multi-company scenarios (**Verified by test**). This is a calculation/grouping contract; it must not be misread as a tenant-security guarantee. Authorization tests separately document that legitimate roles can read multiple companies.

## V1 rule

Keep outputs independently named, sourced and contract-tested. A value must state its engine, as-of point, exclusions and source rows. No algebraic consolidation is approved.

## Owner decisions

Authoritative restriction bases, shared pools/AU treatment, priority of SION rules, cancellation/reversal policy, and customer-facing meaning of each balance are **Requires owner approval**.
