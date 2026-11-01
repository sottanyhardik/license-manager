# 18 Data integrity and reconciliation

Owner: Agent B. Date: 2026-11-01. Branch: `version-v1`.

Labels: **VERIFIED** = read in code or migration at file:line. **SUSPECTED** = inference. Finding IDs are ISS-030 to ISS-049. Cross-references: ISS-001 to ISS-003, ISS-019 to ISS-027, DEC-01 to DEC-05, Q-001, Q-011, Q-016, UD-002 and UD-003 (`docs/v1/system-audit/execution/user-decisions.md`).

Scope limits: no database was queried, no reconciliation or repair command was run, and no write was made. The procedure in section 6 is described, not executed.

## 1. Summary

The licence balance is calculated live from raw rows, but four copies of it are stored: `LicenseBalance.balance_cif`, `LicenseFlags.is_null` and `is_expired`, and the per-item `available_*`, `debited_*` and `allotted_*` columns. Each copy has its own writer, its own formula and, for the Null DFIA flag, its own threshold. Some readers use the copies and others use the live value. Concretely:

- The Null DFIA flag is written with a threshold of 100 by one writer and 500 by two others (ISS-033).
- The licence API filters on stored balance and stored flags, while the list displays the live balance (ISS-034).
- The ledger upload refreshes item caches and the flag but not the stored balance (ISS-035).
- The stored available quantity uses a different formula from the live one (ISS-036).

Other integrity risks are operational. A repeat hide erases the original invoice number (ISS-030). A BOE merge deletes duplicate debit rows without comparing them or writing an audit row (ISS-039). The reconciliation tooling overwrites stored values without a before-and-after record, and there is no job that reports stored-versus-live differences.

## 2. Stored versus live register

| Item | Stored copy (writer) | Live figure (calculator) | Readers of the stored copy | Known divergence | Finding |
|---|---|---|---|---|---|
| Null DFIA flag `LicenseFlags.is_null` | `signals.py:315-318` (500); `calculate_balance.py:204-212` (100); `sync_licenses.py:194-200` (500); `validation_service.py:322` (500, no callers) | Financial balance (`get_balance_cif`, `models/core.py:330`) | Dashboard counts (`views/dashboard.py:107-113`); stored-flag filters (`filtersets.py:119-121`, `165-173`) | Two writers disagree on balances from 100 to 499.99; last writer wins | ISS-033, ISS-026 |
| Licence list Null (filter) | none (live) | Financial, threshold 200 (`views/license.py:673-678`) | The list itself | Differs from the stored flag for any balance in 100 to 499.99 | ISS-026, ISS-033 |
| `LicenseBalance.balance_cif` | `update_license_flags` (`signals.py:309-328`), `update_balance_cif` command (`update_balance_cif.py:141`), `sync_licenses` (`:183`), `recalculate` action (`license_balance_ledger.py:90-127`), seed command (`seed_browser_2509.py:283`, `:485`) | Financial balance | `balance_cif_min/max`, `has_balance` (`filtersets.py:136-137`, `184-186`); materialised-view export (`apps/core/materialized_views.py:419`) | Not refreshed by ledger upload (`parse_ledger.py:408-415`, `:550-553`) | ISS-035, ISS-034 |
| `LicenseFlags.is_expired` | `update_license_flags` (`signals.py:293-300`) | date comparison | `flags__is_expired` filters | Refreshed only on signal; ledger upload does not refresh it | ISS-035 |
| Item `available_quantity` | `update_balance_values` (`calculate_balance.py:72-99`, `:164-215`) | `ItemBalanceCalculator.calculate_available_quantity` (`balance_calculator.py:1958-1998`) | Item report, allocation filters (per comment `signals.py:565`), plan utilisation reads live (`plan_utilization.py:124`) | Stored truncates to whole units and includes hidden rows and ARO; live does not | ISS-036 |
| Item `available_value` | `update_balance_values` / `_update_all_import_items_available_value` (`signals.py:205-278`) | `available_value_calculated` (`models/core.py:1034`) | Item report, allocation | Serial 1 takes the licence balance under a special rule (`calculate_balance.py:125-160`) | Not assessed further |
| Item `debited_*` and `allotted_*` | `update_balance_values` | `calculate_debited_cif_for_items`, `get_outstanding_allotment_totals_for_items` (`balance_calculator.py:1728`, `:928`) | Item summary | Same as above for hidden rows and ARO | ISS-036 |
| Dashboard active, expired, null | stored flags (`dashboard.py:107-113`) | live list (`views/license.py:673-678`) | dashboard cards | Count of 0 active against 12 in the list (retained DB evidence, ISS-001) | ISS-001 |
| BOE `invoice_no` (hidden marker) | `_apply_hide` (`boe_service.py:403`) and `_apply_restore` (`:449-453`) | none | Invoice matching, hide state, trade invoice stamping | Repeat hide loses the original value | ISS-030 |
| Snapshot `customs_balance` | `balance_snapshot.py:156`, `:252` (non-hidden) | `calculate_customs_balance_for_licenses` (`balance_calculator.py:1434`, computed at `balance_snapshot.py:179` but not emitted) | snapshot consumers | Emits the non-hidden figure | ISS-047 |

Checked and found consistent: `is_expired` in the list and in the signal both use the calendar date, and settings set `TIME_ZONE = "UTC"` (`lmanagement/settings.py:233`), so `date.today()` and `timezone.now().date()` agree on a UTC host. No finding.

## 3. Reconciliation tooling and gaps

| Tool | What it does | Writes | Gap |
|---|---|---|---|
| `apps/license/management/commands/sync_licenses.py` | Recomputes balance and flags for every licence and writes them, with a dry-run flag. | Yes (`balance_row.save`, `flags_row.save`, `:183`, `:200`); output to stdout only. | No ReconciliationLog or other audit row per change. Uses threshold 500. (ISS-033) |
| `apps/license/management/commands/update_balance_cif.py` | Recomputes `balance_cif` for one or more licences. | Yes (`:141`). | Writes the stored balance without a before/after record. |
| `apps/license/management/commands/reconcile_item_pivot.py` | Reconciles the item pivot figures. | Not read in full. | Scope not confirmed. |
| `apps/license/management/commands/reconcile_license.py` | Reconciles licence transactions. | Not read in full. | Scope not confirmed. |
| `apps/license/management/commands/repair_license_subtables.py` | Repairs the OneToOne sub-tables after the 0005 split. | Yes, inside `transaction.atomic()` (`:62`). | Repairs by copying from the parent columns that the migration dropped; its source of truth after 0005 needs confirmation. |
| `POST licence/recalculate` (`license_balance_ledger.py:90-127`) | Refreshes items and `balance_cif`, and writes a ReconciliationLog entry with before and after values. | Yes. | The only tool that records before and after. Permission not traced. Good pattern to reuse. |
| `apps/reconciliation/services/boe_link_reconciler.py` | Creates or proposes invoice-to-BOE links. | Yes (within atomic blocks, `:174`). | Automatic links change the debit netting; no reconciliation report. |
| `apps/reconciliation/services/warning_service.py` | Ignore and restore warnings with locks. | Yes. | Acceptable. |

Gaps:

1. **No job compares stored and live values and reports the differences.** The only "drift" evidence is manual (ISS-001 and DEC-03 record one retained-database check).
2. **Repair tools overwrite without a record.** `sync_licenses` and `update_balance_cif` change stored values silently. Only the `recalculate` action writes an audit row.
3. **No duplicate or orphan report exists** for BOE number and date, invoice number on commission trades, debit rows with a null BOE, or allocations whose parent rows changed.
4. **No threshold-consistency check exists** across the five Null DFIA cut-offs (ISS-026).
5. **The ledger upload has no reconciliation step** after it writes.

## 4. Orphan and duplicate risks

| Risk | Mechanism | Evidence | Assessment |
|---|---|---|---|
| Debit row with no BOE | `RowDetails.bill_of_entry` is nullable (`bill_of_entry/models.py:381-388`). The single-licence debit query requires a BOE (`balance_calculator.py:369-400`), the batched queries do not (`:542`, `:645`). | VERIFIED code | SUSPECTED that such rows exist; not queried. A row like this makes the batched and single-licence totals differ. |
| Audit row loses BOE link | `ReconciliationLog.bill_of_entry` SET_NULL (`reconciliation/models.py:146-150`). Deleting a BOE (merge or delete) orphans its log rows. | VERIFIED | ISS-039 |
| Missing sub-table row | `LicenseBalance` and `LicenseFlags` are created by a post-save signal. Readers default to 0 or False when the row is missing (`models/core.py:199-204`). `sync_licenses` uses `get_or_create`. | VERIFIED | A missing row reads as Null DFIA (balance 0 < 200) and as "not expired". SUSPECTED that rows are missing; not queried. |
| Trade with lines deleted | Lines CASCADE from the trade. Payments and invoice documents also CASCADE. | `trade/models.py:513-515`, `:656`, `:690-691` | ISS-040 |
| Paired trade half deleted | `counterpart_line` CASCADE (`:516-521`) deletes the other half, which may be on another licence's trade. | VERIFIED | ISS-040 |
| Licence-level invoice rows | Table exists; no writer. Any row is an orphan. | `license/models/invoice.py:53`, `:168` | ISS-046 |
| Allotment without parent | `AllotmentItems.allotment` CASCADE (`allotment/models/core.py:221-224`). Allotment delete releases quantity unless PROTECTed. | VERIFIED | ISS-040 class; a read-only check is step R7 in section 8. |
| Stale allocation after row change | Allocation writers lock and version. A hard delete of a `RowDetails` row is blocked by PROTECT. A hard delete of an `InvoiceBOEAllocation` has no signal to refresh caches (only `post_save` is wired, `signals.py:584-593`). | VERIFIED | SUSPECTED gap for hard deletes of allocations. Not found through a reachable endpoint. |
| Duplicate BOE | `unique_together (bill_of_entry_number, bill_of_entry_date)` (`bill_of_entry/models.py:235`). Repair migrations exist (`0012`, `0013`). | VERIFIED | Enforced. Merge is the only path that collapses duplicates (ISS-039). |
| Duplicate debit row | `unique_together (bill_of_entry, sr_number, transaction_type)` (`:429`). Merge skips duplicates and deletes them (ISS-039). | VERIFIED | Enforced by DB; merge bypasses comparison. |
| Duplicate trade invoice number | Enforced for non-blank PURCHASE and SALE per company (`trade/models.py:302-318`). Not enforced for COMMISSION directions. | VERIFIED | SUSPECTED duplicates on commission trades; not queried. |
| Duplicate licence number | `license_number` unique (`:125`). | VERIFIED | Enforced. |
| Duplicate ledger rows | `bulk_get_or_create_boe_details` and `bulk_get_or_create_boe` key on `(bill_of_entry, sr_number, transaction_type)` (`apps/core/scripts/ledger.py:262-322`, `scripts/parse_ledger.py:392-415`). | VERIFIED | Keys match the DB constraint. Upload updates existing rows and sets `is_frozen`. |

## 5. Manual override paths

| Path | What it can change | Audit | Evidence | Finding |
|---|---|---|---|---|
| Licence create or update payload with flag fields | `is_null`, `is_expired`, `is_active`, `is_au`, and other flags | None beyond the usual model audit fields | `serializers/license.py:515-525`; `_license_write.py:32-37` (write mapping), `:131-140` | ISS-033, document 08 section 4.1 |
| `POST licence/recalculate` | Item caches and `balance_cif` | ReconciliationLog before and after | `license_balance_ledger.py:90-127` | Permission not traced |
| `sync_licenses` command | `balance_cif` and `is_null` | Stdout only | `sync_licenses.py:139-200` | ISS-033 |
| `update_balance_cif` command | `balance_cif` | None | `update_balance_cif.py:90-141` | ISS-035 |
| BOE hide and restore | `invoice_no` (BOE data) | ReconciliationLog with the pre-hide value | `boe_service.py:377-476`; `license_balance_ledger.py:186-240` | ISS-030 |
| BOE merge | BOE rows, allotments and the source BOE | None | `boe_service.py:203-318` | ISS-039 |
| Trade `_force_save` and `auto_create_paired` | Line CIF and debit | None | `trade/serializers.py:129`, `:147-148`, `:542` | ISS-031 |
| Seed command | `balance_cif` | Not applicable | `seed_browser_2509.py:283`, `:485` | Must not run against a target database. Documented here as a risk, not a finding. |

## 6. Concurrency: two users editing the same balance

| Scenario | Current behaviour | Finding |
|---|---|---|
| Two users allocate sibling items of one licence | Each validates against the licence balance without a licence lock. Both can succeed. | ISS-037 (document 07) |
| Two users edit one BOE (hide and restore) | Each runs in `transaction.atomic()` without locking the BOE. The second may read the first's log and overwrite `invoice_no`. | ISS-030 |
| Two ledger uploads for one licence | Each writes rows and recalculates. Stored caches can be left from the earlier run. | ISS-035, ISS-037 |
| Merge while another user allocates against the source BOE | Source is not locked. The allocation can reference a row that is then deleted or moved. Protected rows block the merge (`boe_service.py:250-266`), so the risk is limited to unprotected rows. | ISS-039 |
| Trade edit while the sale is being allocated | Allocation locks the trade line (`allocation_service.py:257-261`). Trade nested write does not lock the trade. | Not separately assessed |

## 7. Findings (full entries)

#### ISS-030: A repeat hide overwrites the saved invoice number, so restore returns the BOE blank

- **Severity:** HIGH. **Confidence:** VERIFIED (code path read; runtime NOT RUN).
- **Evidence:**
  - `apps/bill_of_entry/services/boe_service.py:400`: `was_hidden = previous_invoice_no == OTH_INVOICE_MARKER`. Line `:403`: `boe.invoice_no = OTH_INVOICE_MARKER` is written unconditionally. Line `:416`: the HIDE log stores `before={"is_hidden": was_hidden, "invoice_no": previous_invoice_no}`, which is `OTH` on a second hide.
  - `_apply_restore` (`:449-453`) reads the most recent HIDE log and keeps the value only when it is not OTH. On a second hide the most recent log holds OTH, so `restored_invoice_no` is `None`.
  - `hide_boe` (`:487`) documents case 2 as an "idempotent no-op (still logs the repeated action)". The code does not skip the overwrite.
  - The endpoint `license_balance_ledger.py:186-210` has no guard, and its docstring says "Idempotent".
- **Business impact:** a BOE hidden twice and then restored loses its original invoice number. That number links the BOE to its sale invoice and to invoice matching, so the BOE can drop out of the invoice picture and its utilisation can be treated as unbilled.
- **Technical impact:** the only copy of the pre-hide value is the latest HIDE log, and a repeat hide overwrites it. A read-only check can find affected BOEs (step R8 below).
- **Suggested remediation:** in `_apply_hide`, when `was_hidden` is true, do not change `invoice_no` and do not write a new HIDE log that replaces the saved value. In `_apply_restore`, search backwards through HIDE logs for the most recent non-OTH `before.invoice_no`. Add an endpoint guard that returns 200 with no change on a repeat hide.
- **Acceptance criteria:** (a) a test hides a BOE with invoice "INV-A", hides it again, restores it, and asserts `invoice_no == "INV-A"`; (b) a repeat hide writes no change to `invoice_no`; (c) the read-only check in R8 finds zero affected BOEs after remediation, and the affected rows are listed for owner review before any correction.

#### ISS-033: The stored Null DFIA flag has two writers with different thresholds

- **Severity:** MEDIUM. **Confidence:** VERIFIED (static); runtime oscillation SUSPECTED.
- **Evidence:**
  - Threshold 500: `apps/license/signals.py:315-318` (`update_license_flags`, called from licence, import, export, allotment, BOE and trade signals); `apps/license/management/commands/sync_licenses.py:37`, `:194-195`; `apps/license/services/validation_service.py:322` (no callers found).
  - Threshold 100: `apps/core/scripts/calculate_balance.py:204-212` (`update_balance_values`, called from the ledger, BOE save on commit, trade-line and allocation signals, and from `recalculate`), with `LicenseFlags.objects.update_or_create`.
  - Both use the Financial balance (`get_balance_cif`).
- **Business impact:** for a licence with balance 100 to 499.99, the stored flag changes with whichever operation ran last. The dashboard Null DFIA count (stored, `dashboard.py:107-113`) therefore changes without any change in the business position. Users see different Null DFIA counts on different days.
- **Technical impact:** one state, two writers, two thresholds. A third view (the list, 200) is live. See ISS-026 for the five cut-offs.
- **Suggested remediation:** one function, `is_null_for(balance)`, that returns the owner-approved result, and every writer calls it. Remove the unused duplicate at `validation_service.py:299-322`. Apply the threshold only after DEC-01 and UD-003 are reconciled (see document 08 section 3). Do not pick a value in code.
- **Acceptance criteria:** (a) a parameterised test runs every writer against the same balances and asserts one result per balance; (b) the threshold is defined once; (c) the owner-approved value is recorded and the boundary tests use it.

#### ISS-034: Licence API filters on stored balance and stored flags disagree with the live balance the list shows

- **Severity:** HIGH. **Confidence:** VERIFIED (static); runtime NOT RUN.
- **Evidence:**
  - `LicenseDetailsViewSet` uses `LicenseFilterSet` (`apps/license/views/license.py:251`).
  - Stored-balance filters: `balance_cif_min` and `balance_cif_max` on `balance__balance_cif` (`apps/core/filtersets.py:136-137`); `has_balance` on `balance__balance_cif` (`:184-186`).
  - Stored-flag filters: `is_active`, `is_expired`, `is_incomplete` (`:119-121`); `status` (`:165-173`).
  - The list displays the live balance (`views/license.py:315`, serializer `serializers/license.py:955-967`).
  - `is_expired` and `is_null` are excluded from the parent filter by `views/license.py:729-745`, so the custom live path handles them. The other stored filters are not.
- **Business impact:** `?balance_cif_min=1000` returns licences whose stored balance is at least 1,000, while each row shows its live balance. A licence showing 1,200 can be missing from the result, and a licence showing 800 can be present. Anyone using these filters for reporting or exports gets different licences from the list.
- **Technical impact:** the same concept is computed two ways in one endpoint.
- **Suggested remediation:** the owner decides whether API filters promise the live balance or the stored value (this is a contract decision, not a code choice). If live, route `balance_cif_min`, `balance_cif_max` and `has_balance` through the same live map that `apply_advanced_filters` uses. If stored, document it and add a freshness guarantee (ISS-035). Make `status` and `is_active` consistent with the flags the rest of the app uses.
- **Acceptance criteria:** for any threshold T, `?balance_cif_min=T` returns exactly the licence ids whose displayed balance is at least T; the same holds for `has_balance` at zero.

#### ISS-035: The ledger upload leaves the stored balance and expiry flag stale

- **Severity:** MEDIUM. **Confidence:** VERIFIED (static); runtime SUSPECTED.
- **Evidence:**
  - `scripts/parse_ledger.py:408` (`RowDetails.objects.bulk_create`) and `:409-415` (`bulk_update`) skip `post_save`.
  - `scripts/parse_ledger.py:550-553`: per-item `update_balance_values`, which writes item caches and the stored `is_null` (100) and does not write `LicenseBalance.balance_cif` (`apps/core/scripts/calculate_balance.py:164-215`).
  - `apps/core/scripts/ledger.py:322` and `:281` follow the same pattern.
  - `update_license_flags`, the only writer of `balance_cif` and `is_expired` from signals, is not called on either path. Its callers are listed at `signals.py` lines 352, 398, 412, 445, 513, 529, 545, 569 and `_license_write.py:300`, `:894`.
- **Business impact:** after an upload, the stored balance, the stored-column API filters (ISS-034) and any stored reader show the pre-upload position until another signal fires. `is_expired` is not refreshed either.
- **Technical impact:** a write path that bypasses the refresh contract.
- **Suggested remediation:** call the licence refresh (`update_license_flags` or a shared function that refreshes balance, flags and item caches) once at the end of each upload, inside the licence lock (ISS-037).
- **Acceptance criteria:** after a ledger upload fixture, `LicenseBalance.balance_cif` equals the live Financial figure for every licence touched, and `is_expired` equals the date comparison.

#### ISS-036: The stored item available quantity uses a different formula from the live one

- **Severity:** MEDIUM. **Confidence:** VERIFIED (both formulas read).
- **Evidence:**
  - Stored (`apps/core/scripts/calculate_balance.py`): `_get_aggregated_values` (`:7-70`) sums DEBIT rows from `item_details` with no hidden-row exclusion, and includes `aro_qty`. `calculate_available_quantity` (`:72-99`) computes `credit − debited − allotted − direct_sale`, applies `round_down(..., 0)` (whole units), and floors at zero via `max(..., 0)`.
  - Live (`apps/license/services/balance_calculator.py:1958-1998`): `quantity − BOE debit (hidden excluded) − outstanding AT allotment − direct sale`, no ARO term, no rounding, floored at zero.
  - The stored docstring (`calculate_balance.py:81-91`) states that 2909.261 − 857 = 2052.261 is the correct value; the code returns 2052.00.
- **Business impact:** the item's available quantity shown in the item report and the stored column differ from the value the allocation gate uses (`validation_service.py:167-196` reads live). Hidden BOEs reduce the stored figure but not the live one. ARO allotments reduce the stored figure but not the live one. Fractional kilograms are removed.
- **Technical impact:** two formulas for the same field, with the stored one written on every item save.
- **Suggested remediation:** make the writer call the live function. Keep fractional quantity to the field's three decimals. ARO semantics are an owner decision (ISS-024).
- **Acceptance criteria:** for a fixture with a hidden BOE, an ARO allotment and a fractional quantity, the stored field equals the live `calculate_available_quantity` to three decimals; the docstring example matches the code.

#### ISS-039: A BOE merge discards duplicate debit rows without comparing or auditing them

- **Severity:** HIGH. **Confidence:** VERIFIED (static); runtime NOT RUN.
- **Evidence:**
  - `apps/bill_of_entry/services/boe_service.py:203-318` (`merge_boe`). Source rows whose `(sr_number, transaction_type)` already exists on the target are added to `skipped_row_ids` (`:~233-242`). They are not moved. `source_boe.delete()` cascades to them (`bill_of_entry/models.py:381-388`). Their CIF and quantity are never compared with the target's row.
  - Protected duplicates (referenced by an allocation or external link) block the merge (`:~250-266`). Unprotected duplicates are deleted.
  - Moved rows are updated by `RowDetails.objects.filter(...).update(bill_of_entry=target_boe)` (`:~280`), which bypasses signals, so caches and flags are not refreshed for the target.
  - No ReconciliationLog is written by the merge. The source BOE's log rows are SET_NULL (`reconciliation/models.py:146-150`).
  - The source BOE is not locked.
  - Endpoints: `apps/bill_of_entry/views/boe.py:247-260`; `apps/reconciliation/views.py:180-200`.
- **Business impact:** if two copies of the same BOE carry different CIF or quantity for one item, the merge keeps the target's values and deletes the source's without a record. The debit that was removed cannot be reconstructed from the audit trail. The hide state of moved rows follows the target's `invoice_no`, so a licence balance can change without a refresh.
- **Technical impact:** destructive write with no audit row, no value comparison, and no refresh of derived data.
- **Suggested remediation:** refuse the merge when any duplicate row differs in CIF or quantity, and return the diff. Write a ReconciliationLog merge entry that stores the source BOE snapshot and the removed row ids and values. Refresh every affected licence (flags and item caches) after commit. Lock both BOEs.
- **Acceptance criteria:** (a) a merge with a differing duplicate is refused and returns the diff; (b) an accepted merge writes one log entry listing removed rows; (c) balances before and after the merge match the expected values, with a test for a hidden source BOE.

## 8. Recommended read-only reconciliation procedure (described, not run)

Purpose: produce a dated report of stored-versus-live differences, orphans, duplicates and threshold disagreements, without changing any data. Nothing in this section has been run, and nothing should be run against a production database without owner approval and a change ticket.

Preconditions:

- Run against a restored copy of the database, or a read replica, under a role with `SELECT` only. Begin every session with `SET TRANSACTION READ ONLY` and do not grant write privileges.
- Use only read calculators: `calculate_financial_balance_for_licenses`, `calculate_customs_balance_for_licenses`, `calculate_balance_for_licenses`, `ItemBalanceCalculator.calculate_available_quantity`. Do not call `update_license_flags`, `update_balance_values`, `sync_licenses`, `update_balance_cif`, `recalculate`, or any `save()`, `update()`, `delete()` or `bulk_*` call.
- Record the code revision, database name, server time, and the threshold parameters the owner has approved. Do not hard-code a threshold in the procedure.
- Write output only to a location outside the repository and handle it under data governance (DEC-03). Licence numbers and BOE numbers are business identifiers; no other personal data should be exported.
- Set tolerances as parameters. Proposed, not approved: money 0.00 difference, quantity 0.001 difference.

Steps:

- **R0 Identify.** Record revision, database, time, parameters, and the approved threshold values (or the explicit statement that the threshold is pending).
- **R1 Sub-rows.** Count licences, `LicenseBalance` rows and `LicenseFlags` rows. Report any licence without a sub-row (expected: none).
- **R2 Live figures.** For every licence, compute Financial, Customs and non-hidden figures using the batched calculators. Record the engine name and the as-of time with each value.
- **R3 Balance copy.** Compare `LicenseBalance.balance_cif` with the Financial figure. Report every difference above tolerance (ISS-035).
- **R4 Null flag matrix.** For each licence, record the stored `is_null` and the result of each candidate threshold at 99.99, 100, 199.99, 200, 499.99 and 500. Report licences where the stored value matches only some writers' thresholds (ISS-033, ISS-026).
- **R5 Expiry.** Compare stored `is_expired` with `license_expiry_date < current UTC date`.
- **R6 Item copy.** For every import item, compare `available_quantity` with the live figure to three decimals, and `available_value` with `available_value_calculated`. Report truncation and hidden-row differences separately (ISS-036).
- **R7 Orphans.** Run SELECT-only checks for: debit rows with `bill_of_entry_id` null; allocations with `is_current = true` whose parent row has been superseded; allotment items whose allotment is missing; trade lines whose counterpart line belongs to a different licence; trades with zero lines and non-zero totals; payments on trades with zero total.
- **R8 Hidden BOEs.** Report BOEs with `invoice_no = OTH` and no HIDE log; BOEs whose latest log is HIDE but whose `invoice_no` is not OTH; HIDE logs whose `before.invoice_no` is OTH (the ISS-030 signature). Report, do not correct.
- **R9 Duplicates.** Report duplicate `(bill_of_entry_number, bill_of_entry_date)` (expected zero); duplicate invoice numbers per company on commission trades (ISS-045 context); duplicate ledger keys if any.
- **R10 Negative values.** Report any money or quantity column below zero on RowDetails, import and export items, balances, trade lines and payments (ISS-043).
- **R11 Trade checks.** Report QTY-mode SALE lines with `cif_fc = 0` (ISS-042); trades whose payments exceed the total (ISS-041); trades whose stored total does not equal the sum of line amounts plus round-off.
- **R12 Commission.** Count COMMISSION_SALE trades with lines on licences (ISS-045).
- **R13 Output.** One CSV per check, with counts and identifiers, and a summary table listing each check as pass, fail or not run.
- **R14 Review and change control.** The owner and the lead review the report. Any correction is a separate, approved change with: a database backup identifier; a dry run; one audit record per changed row; a rollback plan; and the rule for which figure is authoritative (DEC-02, DEC-03). No flag or balance is rebuilt silently.

Stop conditions: any statement that is not read-only, any connection to the live database, or any missing threshold approval.

## 9. Limits and dependencies

- No database was queried. Every "SUSPECTED" count above needs R1 to R12.
- The Null DFIA threshold is pending (Q-001). UD-003 records an owner answer of 200 with the currency pending (Q-011); the lead must reconcile the two records. This document does not pick a value.
- Q-016 asks whether UD-002 should be reconsidered in light of ISS-019 to ISS-021 and ISS-032. This document does not decide it.
- DEC-02 (live versus stored classification) and DEC-03 (historical flag reconciliation) remain open and are the basis for R14.
- Migrations listed as NOT READ in document 07 (planning backfills) could change planning balances; they were not reviewed for this document.
