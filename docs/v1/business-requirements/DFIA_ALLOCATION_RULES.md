# DFIA Allocation Rules

| Field | Value |
|---|---|
| Document | DFIA allocation rules: BOE to allotment, one BOE across allotments, partial invoices, currency, limits, negative balance |
| Version | 0.1 (draft) |
| Status | **Draft / Under Review. Not Approved. Not Frozen.** |
| Date | 2026-11-01 |
| Parent | `DFIA_BALANCE_MANAGEMENT_MASTER_SPECIFICATION.md` (§§3, 4, 5, 6, 8) |
| Decisions | `DFIA_BUSINESS_DECISION_REGISTER.md`. This file covers BD-02, BD-03, BD-04, BD-05, BD-06, BD-08 and BD-10. |
| Companion | `DFIA_TRANSACTION_LIFECYCLE.md` (object states, editing, cancellation, BD-07, BD-09, BD-11, BD-12) |
| Evidence basis | Static reading of `backend/` on branch `version-v1`, working tree as of 2026-11-01. No test was run, no database was queried, no migration or write command was executed. |

**Legend**

- **VERIFIED**: what the code does today. Each statement cites `file:line`. Paths are relative to `backend/` unless shown otherwise.
- **PROPOSED**: a rule suggested by this draft. Not approved and not existing behaviour.
- **OPEN (BD-xx)**: an owner decision that is still pending. Options are listed with their trade-offs. No option is adopted.
- **Recommendation**: a suggestion only.

---

## 1. Brief parts and decision IDs

The brief itself is not in the repository. The mapping below uses the master specification §5 and the register. The D7 mapping is an assumption and the owner should confirm it.

| Brief part | Subject | Decision ID | Where covered |
|---|---|---|---|
| D1 | Allocation when a BOE exceeds an allotment | BD-02 (with BD-01 coupling) | §4 |
| D2 | One BOE across several allotments | BD-03 | §5 |
| D3 | Partial invoices | BD-04 | §6 |
| D4 | Foreign currency and INR | BD-05 | §7 |
| D5 | Item-level and aggregate limits | BD-06, and BD-10 for quantity | §8, §13 |
| D6 | Editing and cancellation after downstream rows exist | BD-07, BD-12 | Lifecycle §5 and §8 |
| D7 | Duplicate prevention (assumed) | BD-09 | Lifecycle §8.4 |
| D8 | Negative balance | BD-08 | §12 |
| Part E | Allocation record fields | none | §10 |
| Part F, last paragraph | Enforcement level | none | §11 |

**BD-01 is not decided here.** Several rules below depend on it. Section 3 shows the figures under each reading.

---

## 2. The balance figures as implemented today

The spec requires one balance engine (principle A1). The code has several figures. Each is listed below with its formula as coded.

| Figure | Code | Formula as coded | Used for |
|---|---|---|---|
| Financial Balance CIF | `LicenseBalanceCalculator.calculate_financial_balance` (`apps/license/services/balance_calculator.py:1572-1651`) | Opening + Purchase − Sale − allocation-netted BOE debit − allotment, floored at 0 (`:1649-1651`) | `LicenseDetailsModel.get_balance_cif` (`apps/license/models/core.py:330-349`). Stored in `LicenseBalance.balance_cif` (`core.py:2360-2373`). |
| Customs Balance CIF | `calculate_balance` (`balance_calculator.py:1349-1403`) | Credit − (non-hidden raw BOE debit + allotment), floored at 0 (`:1403`) | Comparison with the Customs ledger. |
| Customs all-in | `calculate_customs_balance` (`:1406-1431`) | Credit − (all BOE debit, hidden included, + allotment), floored at 0 (`:1431`) | Matches the Customs ledger exactly. |
| Item CIF (availability) | `ItemBalanceCalculator.calculate_item_balance` (`:1846-1858`) | Item `cif_fc` − item BOE debit − outstanding allotment, floored at 0 (`:1858`) | Item-level CIF only. |
| Item CIF for allocation | `LicenseImportItemsModel.available_value_calculated` (`apps/license/models/core.py:1034-1110`) | `0.01` marker; `%` pool (`:1085-1091`); attributed item balance; otherwise the licence financial balance (`:1093-1110`) | The ceiling used by the allotment draw (`apps/allotment/views_actions.py:1374-1384`) |
| Item quantity (live) | `ItemBalanceCalculator.calculate_available_quantity` (`balance_calculator.py:1958-1998`) | Quantity − raw BOE qty − outstanding allotted qty − direct sale qty, floored at 0 (`:1998`) | Live figure. Not used by the draw. |
| Item quantity (stored) | `apps/core/scripts/calculate_balance.py:72-98` and `update_balance_values` (`:164-`) | Quantity − (raw BOE qty + ARO qty) − outstanding allotted − direct sale qty, floored to a whole unit (`:97`), then floored at 0 (`:98`) | Stored `available_quantity`, read by the draw (`views_actions.py:1341-1349`). |

**Observations (VERIFIED)**

1. The financial and customs CIF figures disagree whenever a hidden BOE, a purchase, a sale or an unconsumed allotment is present. Both are live. Only the financial one is stored in `LicenseBalance` and shown in lists.
2. The stored and live quantity figures differ in two ways. ARO allotments reduce the stored figure but not the live one (`calculate_balance.py:54-65` and `:90` against `balance_calculator.py:1958-1998`). The stored figure floors to whole units (`:97`), the live figure does not.
3. Sales reduce quantity (`balance_calculator.py:1861-1927`) but not item CIF (`:1846-1858`).
4. The financial figure's BOE term is the allocation-netted debit (`calculate_debit`, `:459-510`). The customs term is the raw debit (`:512-527`).
5. Every figure floors at zero (`:1403`, `:1431`, `:1651`, `:1858`, `:1998`). The overrun is then hidden (ISS-049 in the register).
6. The live functions in `balance_calculator.py` use `Decimal`. The stored-field writer `apps/core/scripts/calculate_balance.py` aggregates in `float` (`:38-39`, and `to_float` at `:64-65`) and compares in `float` inside `update_balance_values`. Spec Part F item 1 forbids floating-point financial values. Not fixed here.

---

## 3. Reference scenarios

The table gives the balance for one licence item with Credit 100 (CIF FC). Each figure is worked from the code, not executed. Values are in CIF FC.

| # | Facts | Spec §4.2 (reservation) | Financial (live) | Customs | Remarks |
|---|---|---|---|---|---|
| S1 | Allotment 40 with no BOE. | 60 | 60 | 60 | Both agree. |
| S2 | Allotment 40 linked to a BOE of 25 through the header M2M. | 60 | **75** | **75** | Header link zeroes the allotment (`balance_calculator.py:826`, `:835`). The unconsumed 15 is released. This is the UD-002 result. |
| S3 | Allotment 40 with a BOE of 25 linked by an allotment-side allocation row of 25 (no header link). | 60 | 60 | 60 | Matches the spec. **No production code creates this state** (§5.1). |
| S4 | Allotment 40 linked by header to a BOE of 50. | 50 | 50 | 50 | Matches the spec, because the remaining reservation is zero either way. |
| S5 | One BOE of 50 linked by header to two allotments of 40 each. Spec split is 40 to A and 10 to B. | 20 | **50** | **50** | Overstated by 30. Both allotments are zeroed although only 50 is consumed (D2 risk). |
| S6 | Direct BOE of 50 with no link, and an unlinked allotment of 40. | 10 | 10 | 10 | A direct BOE never reserves (spec §3.3). Both agree. |

**Reading the table.** The current engine matches the spec whenever a BOE is at least as large as its allotment (S4), or whenever the link is an allocation row rather than a header link (S3). It does not match the spec when a header-linked BOE is smaller than the allotment (S2) or when one BOE is linked to several allotments (S5).

---

## 4. D1: allocation when a BOE exceeds an allotment (BD-02)

### 4.1 Current behaviour (VERIFIED)

- **No automatic allocation step exists.** No code splits a BOE row between an allotment and direct use.
- The BOE's debit is counted in full by the customs figure (`calculate_boe_debit_total`, `balance_calculator.py:512-527`). The financial figure counts the unmatched part (`calculate_debit`, `:459-510`). Any excess above an allotment is therefore counted as direct utilisation by default.
- The only allotment netting is:
  - (a) a header M2M link, which zeroes the allotment (`:826`, `:835`); and
  - (b) allotment-side allocation rows, which are capped and netted (`:711-845`), but which no production code creates (§5.1).
- Consequence: the BOE-exceeds-allotment case (S4) gives the same balance under the current code and under the brief's recommendation, because the remaining reservation is zero either way. The two diverge only when the BOE is smaller than the allotment (S2: current 75, recommendation 60).
- The header link is not audited. `BillOfEntrySerializer.update` changes it with no `ReconciliationLog` row (`apps/bill_of_entry/serializers.py:322-345`).
- The BOE create and edit paths check CIF against the balance only for licences in individual-item mode (`serializers.py:82-111`). For other licences a BOE can exceed the balance (see §12).

### 4.2 Proposed rule (PROPOSED; the brief's recommendation, marked as a recommendation)

Auto-allocate up to the remaining allotment. The excess is direct utilisation. The allocation is subject to the licence balance and writes an audit record.

Defined per dimension, independently:

- `allocated_qty = min(BOE row qty, remaining allotment-item qty)`
- `allocated_cif_fc = min(BOE row CIF FC, remaining allotment-item CIF FC)`
- `allocated_cif_inr = min(BOE row CIF INR, remaining allotment-item CIF INR)`, with the INR value taken as recorded (see §7)
- Excess per dimension = BOE amount − allocated amount, counted as direct utilisation.
- Each allocation writes one `BOEAllotmentAllocation` row (no such writer exists today) and one `ReconciliationLog` row with action `ALLOCATE`, in the same transaction.

**Dependencies.**

- BD-01. Under option A (reservation) the remaining reservation is the figure that falls. Under option B (utilisation only) the automatic split has no balance effect beyond the audit record. The result must be re-checked once BD-01 is decided.
- BD-03. The automatic split needs an order when several allotments are candidates.
- BD-08. The excess is direct utilisation and so must pass the negative-balance rule.

### 4.3 Options (BD-02)

| Option | Description | For | Against |
|---|---|---|---|
| **A. Automatic** (brief's and register's recommendation) | The system allocates up to the remaining allotment, as in §4.2. | Matches how an import consumes entitlement. The audit row keeps the split visible. Removes a manual step. | Creates allocations the user did not choose. Needs an order (BD-03) when several allotments qualify. Needs a new writer for `BOEAllotmentAllocation`. |
| **B. Explicit** | The user must allocate every amount. The system blocks the BOE until the user does. | Nothing is allocated without a choice. | Adds steps. Blocks entry until the user acts. Risk of a BOE left open for a long time. |
| **C. Hybrid** | Automatic only when the allotment is unambiguous: one allotment item for that licence item and allocation basis. Explicit otherwise. | Automatic in the common case. The ambiguous case is never guessed. | Two code paths to test. Needs a definition of "unambiguous". |

**Recommendation (not a decision).** Option A, with the ambiguity guard from C. The guard limits automatic allocation to cases with a single candidate allotment item.

### 4.4 Edge cases to settle under any option (PROPOSED)

- Allotment item smaller than the BOE in one dimension and larger in another. Each dimension is capped separately (§4.2).
- The allotment item already has draws. Only the remaining amount is available.
- The BOE row is later reduced below its allocation. Today nothing re-checks the allocation (§6.1). See the lifecycle §3.3.
- The BOE is already invoiced. The invoice-side and allotment-side tracks are independent (§5.3), so both can apply.
- The licence cannot cover the excess. Under BD-08 this is blocked, not silently allowed.

---

## 5. D2: one BOE across several allotments (BD-03)

### 5.1 Current behaviour (VERIFIED)

- **Allotment-side ledger.** `BOEAllotmentAllocation` (`apps/reconciliation/models.py:331`) allows many rows per BOE row, one per allotment item. Each row is capped by the BOE row's remaining allotment-side capacity (`apps/reconciliation/services/allocation_service.py:486-490`, using `remaining_for_row_details_allotment_side`, `:147-171`). Each (BOE row, allotment item) pair is unique (`:474-484`).
- **No production writer.** `create_boe_allotment_allocation` (`:437-519`) is called only by tests (`apps/reconciliation/tests/test_allocation_service.py`, `apps/license/tests/test_balance_calculator.py`, `apps/license/tests/test_balance_ledger_views.py`).
- **Header M2M.** `BillOfEntryModel.allotment` (`apps/bill_of_entry/models.py:212`) allows one BOE to link to many allotments. But each linked allotment is zeroed, whatever the BOE amount (`balance_calculator.py:826`, `:835`). This is the S5 overstatement (30 released without consumption).
- **Ownership of the split.** No code records how much of a BOE went to which allotment, except the allocation rows that §5.1 says are never written. Under the header link the split is not recorded at all.

### 5.2 "The same BOE amount cannot be allocated twice" (Part D2)

Checks in place today (VERIFIED):

- Pair uniqueness: `allocation_service.py:474-484`.
- Row capacity per dimension: `:486-490` and `_validate_fits` at `:209-217`.
- Row and item locks before the check: `:471-472`.

Not checked today:

- The header M2M path (S5).
- Any database-level aggregate. A plain `CHECK` cannot sum rows. The module comment says so (`apps/reconciliation/models.py:213-222`), and no trigger exists in the migrations (search of `apps/*/migrations` for `CREATE TRIGGER` returned none).

**PROPOSED.** The invariant holds for each BOE row and each dimension: the sum of ACTIVE, current allotment-side allocations is at most the row's amount. Equivalently, for each allotment item, the sum is at most the item's amount. Enforcement options:

- A service-level check under the existing row locks (already the pattern).
- A deferred database trigger that sums on commit. Not used anywhere in the codebase today, so it would be new.

The header M2M path must also be brought under the invariant, or retired in favour of allocation rows. That depends on BD-01 and BD-07.

### 5.3 Two independent tracks (VERIFIED, by design)

The invoice-side track (`InvoiceBOEAllocation`) and the allotment-side track (`BOEAllotmentAllocation`) are independent by design (`apps/reconciliation/models.py:14-25`, `apps/reconciliation/services/allocation_service.py:14-25`, `:108-114`). Each nets only its own engine term. This does not cause a double debit. Worked example: one BOE row of 100, with an invoice allocation of 100 and an allotment allocation of 100.

- Financial: row debit contributed = 100 − 100 = 0. Sale counted in full = 100. Allotment contributed = 100 − 100 = 0. Total deducted = 100.
- Customs: raw row debit = 100. Allotment contributed = 0. Total deducted = 100.

Both are correct. The independence is a deliberate design and is not a defect.

### 5.4 Options (BD-03)

| Option | Description | For | Against |
|---|---|---|---|
| **A. Owner-specified order** | Allocate the BOE item to allotments in an order (for example, by allotment date), each up to its unallocated amount per dimension. | Quick. Needs no user choice for each BOE. | Hides the choice. Needs a rule for ties and for partial allotments. |
| **B. Explicit split** | The user chooses the split for each allotment. The system checks that the totals never exceed the BOE item in any dimension. | Transparent. The split is recorded. | More steps for the user. |

**Register recommendation.** B, with a system check on the sum (the register's wording). Recorded here as the register's recommendation, not as a decision.

**Interaction with BD-02.** Automatic allocation (BD-02 option A) needs an order, so BD-02 option A and BD-03 option A go together.

---

## 6. D3: partial invoices (BD-04)

### 6.1 Current behaviour (VERIFIED)

- **Invoice-side allocation.** `InvoiceBOEAllocation` links one sale line to one BOE row, with `allocated_qty`, `allocated_cif_fc` and `allocated_cif_inr` (`apps/reconciliation/models.py:226-330`). It is checked against the sale line's remaining amount and the row's invoice-side remaining amount, per dimension (`allocation_service.py:275-284`; `:344-353` on edit).
- **Financial netting.** The row's unmatched debit = CIF − allocated − linked-excluded (`balance_calculator.py:369-457`; allocated subquery at `:415-426`). The sale line is counted in full (`calculate_trade`, `:1063-1090`).
- **Legacy whole-BOE tag.** A BOE in `LicenseTrade.boes` is excluded whole from the debit, wherever that row has no formal allocation of its own (`_linked_boe_debit_exclusion_case`, `:294-367`). The unbilled rest of a partly billed BOE is therefore dropped (ISS-020).
- **No quantity-to-CIF relation on the invoice side.** The allotment draw checks the canonical unit-price pair (`apps/allotment/views_actions.py:1296-1330`). The invoice-side allocation does not (`allocation_service.py:243-246` checks only non-negative values).
- **External mark.** `ExternalInvoiceLink` uses invoice-side capacity (`allocation_service.py:127-144`) but is not read by the balance's debit path (`balance_calculator.py:415-426` reads `InvoiceBOEAllocation` only).
- **Invoice edits are not re-checked.** See the lifecycle §3.5.

**Scenarios (VERIFIED by reading; not executed).** BOE row CIF 100.

| # | Facts | Spec §3.4 | Financial | Remarks |
|---|---|---|---|---|
| I1 | Sale line 60, formal allocation 60. | 100 deducted (60 replaced, 40 at BOE value) | 100 | Correct. |
| I2 | Sale line 60, legacy tag only (no allocation). | 100 | **60** | The whole row is excluded. 40 is dropped (ISS-020). |
| I3 | Two sale lines of 60 and 40, two formal allocations. | 100 | 100 | Correct. |
| I4 | Formal allocation of 120 to a row of 100. | Blocked | Blocked | `_validate_fits` rejects it against the row's invoice-side remaining (`allocation_service.py:275-289`). |

### 6.2 Proposed quantity and CIF mechanism (PROPOSED)

- The invoice replaces only the invoiced quantity and CIF of the BOE item. The uninvoiced remainder counts at BOE value (spec §3.4).
- Each dimension is checked separately. Quantity and CIF FC are both checked. CIF INR is stored as recorded (see §7).
- A sale line may not allocate more than its own remaining amount, or more than the BOE row's uninvoiced amount, in any dimension. Both checks exist today (I4).
- A quantity-to-CIF relation may be checked against a unit price, as the allotment draw already does. This is an option, not a requirement (see the open question in §6.3).
- The legacy whole-BOE tag should be replaced by formal allocations, so that the balance no longer depends on whole-row exclusion. This requires a decision under BD-04.

### 6.3 Options (BD-04)

| Option | Description | For | Against |
|---|---|---|---|
| **A. Strict** (register's recommendation) | Block any invoice amount above the BOE's uninvoiced value in any dimension. | Keeps invoice and BOE reconciled. Avoids a second debit. | Blocks legitimate over-invoicing without a process. Owners may need an amendment route. |
| **B. Permitted excess, recorded as an amendment, with owner approval** | Excess is allowed, recorded as an amendment event, and approved. | Handles real-world differences. | Needs an approval workflow and a new event type. A poor fit with the append-style pattern unless BD-12 is decided first. |

**Recommendation (not a decision).** Option A, as the register recommends. The register also recommends that the legacy whole-BOE tag be converted to formal allocations, which this draft supports as a recommendation.

**Open question for the owner, as a statement.** Whether the quantity-to-CIF relation in §6.2 is required for invoices, or only for allotments.

---

## 7. D4: foreign currency and INR (BD-05)

### 7.1 Fields holding FC, INR and rates (VERIFIED)

| Object | FC field | INR field | Rate field |
|---|---|---|---|
| Licence export credit | `cif_fc` (`apps/license/models/core.py:860-`) | not checked | `fob_exchange_rate` (`:878`) |
| Licence item | `cif_fc` (`:916`) | `cif_inr` (`:917`) | none |
| Allotment | `cif_fc` (`apps/allotment/models/core.py:68`) | `cif_inr` (`:76`) | `exchange_rate` (`:84`, 6 dp) |
| Allotment item | `cif_fc` (`:235`) | `cif_inr` (`:229`) | none. `effective_unit_price` (`:279`). |
| BOE | none | none | `exchange_rate` (`apps/bill_of_entry/models.py:205`, 4 dp) |
| BOE row | `cif_fc` (`:401`, 3 dp) | `cif_inr` (`:395`, 3 dp) | none |
| Sale line | `cif_fc` (`apps/trade/models.py:540`) | `cif_inr` (`:542`) | `exc_rate` (`:541`, 4 dp) |
| Purchase | not checked | not checked | `exchange_rate` (`apps/license/models/core.py:2253`) |
| BOE to allotment allocation | `allocated_cif_fc` (`apps/reconciliation/models.py:387`) | `allocated_cif_inr` (`:391`) | none |
| BOE to invoice allocation | `allocated_cif_fc` (`:284`) | `allocated_cif_inr` (`:288`) | none |
| Daily rate table | none | none | `ExchangeRateModel.usd` (`apps/core/models.py:714-726`, date unique) |

### 7.2 Where a rate is used (VERIFIED)

- **U1.** `AllotmentModel.save` recalculates `cif_inr = cif_fc × exchange_rate` on every save when both are positive (`apps/allotment/models/core.py:155-158`).
- **U2.** The management command `update_exchange_rate` overwrites `exchange_rate` and `cif_inr` for every non-BOE allotment and their items, at one rate supplied on the command line. The default is `89.5` (`apps/allotment/management/commands/update_exchange_rate.py:19`). The write is at `:104-116`. This recalculates historical INR at a current rate.
- **U3.** `BillOfEntryModel.save` rewrites `exchange_rate` from row totals (`apps/bill_of_entry/models.py:257-270`) when the difference exceeds 1. This is a derivation from totals, not a market rate. It still overwrites a stored value.
- **U4.** `_recalculate_boe_exchange_rate` (`apps/bill_of_entry/models.py:501-530`) runs on row save and delete (`:533-556`). It has a `force` argument described as "ledger upload", but no caller passes `force=True`.
- **U5.** The BOE PDF parser derives `cif_fc = cif_inr ÷ usd_rate`, rounded to 2 dp (`apps/bill_of_entry/views/parse_pdf.py:172`). The rate is the BOE's own date rate, or the latest available rate if no date rate exists (`:74-95`). That is a current-rate fallback at import.
- **U6.** A new allotment takes the latest `ExchangeRateModel.usd` as its default rate (`apps/allotment/serializers.py:327-334`; `apps/allotment/views.py:17-26`).
- **U7.** `LicensePurchase.save` derives `exchange_rate = inr ÷ usd` when none is given (`apps/license/models/core.py:2309-2314`).
- **U8.** The balance engine and the allocation services do not use any rate. The only INR-related text in the balance module is a comment (`balance_calculator.py:1717`).

### 7.3 FC is the balance currency (VERIFIED)

- Credit is `LicenseExportItemModel.cif_fc` (`balance_calculator.py:92-110`).
- Raw BOE debit is `RowDetails.cif_fc` (`:512-527`).
- The item CIF uses `import_item.cif_fc` (`:1786-1858`).
- Allotment uses `AllotmentItems.cif_fc` (`:711-845`).
- Trade uses `LicenseTradeLine.cif_fc` (`:1063-1090`).
- No INR available balance is computed anywhere. Spec §4.1 requires one ("available CIF INR"). This is a gap.
- The owner has confirmed US dollars for the Null DFIA threshold (UD-004, recorded in `docs/v1/system-audit/execution/user-decisions.md`).
- No currency code was found in the balance or allocation modules (`apps/license/services/balance_calculator.py`, `apps/reconciliation/services/allocation_service.py`, `apps/reconciliation/services/boe_link_reconciler.py`, `apps/license/services/validation_service.py`). The engine therefore has no mechanism for adding two currencies, and none is needed while every figure is USD. Whether a licence can carry another currency is not established by this review.

### 7.4 Historical values recalculated at a current rate (VERIFIED)

Paths that overwrite a stored value with a value derived from a rate or total:

| Path | What it overwrites | Historical value changed? |
|---|---|---|
| `update_exchange_rate` command (U2) | Allotment and item `cif_inr`, allotment `exchange_rate` | Yes, when run |
| `AllotmentModel.save` (U1) | Allotment `cif_inr` | Yes, on any save |
| BOE save and row signals (U3, U4) | BOE `exchange_rate` | Yes, when the difference exceeds 1 |
| BOE PDF parse with fallback (U5) | Not an overwrite. A new row gets a current rate. | Only for a row imported without a date rate |

### 7.5 Options (BD-05)

| Option | Description | For | Against |
|---|---|---|---|
| **A. Store and never recalculate** | Each row stores its rate, rate source and date. INR is fixed at posting. FC is authoritative. | Satisfies the spec's no-recalculation principle. Simple to audit. | Requires new columns on the affected rows. Existing rows need a decision on their stored INR. |
| **B. Derive INR for display only** | INR is computed on read from the stored rate. FC is authoritative. Stored INR is not used for any balance. | Nothing stored changes. Display is consistent. | Two INR figures can differ on screen if a rate changes. Needs a clear label. |
| **C. Revaluation event** | A rate change creates a new event row (revaluation) rather than rewriting. | Full history. Matches the append pattern. | New event type. Needs an approval rule. |

**Recommendation (not a decision).** A for stored values, with B for displayed INR. The register recommends that historical FC values are never recalculated at a current rate, which this draft supports.

**Decision needed (the register's open question).** Which rate governs each conversion: the BOE's rate, the invoice's rate, or the licence's rate.

---

## 8. D5: item-level and aggregate limits (BD-06)

### 8.1 Where each limit is enforced today (VERIFIED)

| # | Limit | Dimension | Enforced where | Layer | Gap |
|---|---|---|---|---|---|
| L1 | Allotment requirement | qty, CIF | `apps/allotment/views_actions.py:1158-1182` and `:1296-1330`. Allowance of `$20` at `:1171` and `:1318-1320`. Under the allotment row lock (`:1098`). | Service (view) | The `$20` allowance is a commercial rule not in the spec (`apps/allotment/services/paired_allocation_max.py:7`, `:50-63`). |
| L2 | Item available quantity | qty | `views_actions.py:1341-1349` against the stored `available_quantity` | Service (view), on a stored projection | The stored figure differs from the live figure (§2, observation 2). Read under a lock, but the refresh runs after commit (`apps/allotment/models/core.py` the `_update_balance_sync` on-commit hook). A race window exists by reading. Not reproduced. |
| L3 | Item available CIF | CIF FC | `views_actions.py:1374-1384` via `effective_source_row_cif_available` (`apps/license/services/effective_cif_mode.py:114-128`) | Service (view) | Default licences use `available_value_calculated`, which for a zero-CIF item returns the licence's financial balance (`apps/license/models/core.py:1093-1110`). That is licence-wide, not item-level (spec B1). |
| L4 | Licence eligibility and balance | CIF | `apps/license/services/validation_service.py:23-60` (purchase status GE, not expired, balance at least 500, not AU). Called only from `validate_allocation` (`:228-281`). | Service, legacy path | The allotment draw does not call `validate_allocation`. The licence check is therefore not applied to draws. |
| L5 | Licence-level CIF for a legacy draw | CIF | `validation_service.py:119-165` | Service, legacy path | Only the legacy `AllocationService.allocate_item` uses it, and that has no production caller. |
| L6 | `%` pool | CIF | `apps/license/models/core.py:1085-1091` (live); `validation_service.py:197-226` (legacy) | Service | Spec silent. |
| L7 | Plan line remaining | qty, CIF | `views_actions.py:1262-1296` via `plan_enforcement.plan_line_status_for` | Service (view) | Spec silent. |
| L8 | Invoice allocation: line and row (invoice side) | qty, CIF FC, CIF INR | `apps/reconciliation/services/allocation_service.py:275-284` (create) and `:344-353` (edit). Locks at `:257-261`, `:331-340`. | Service | Writer is the backfill command only (lifecycle §3.4). |
| L9 | Allocation: row and allotment item (allotment side) | qty, CIF FC, CIF INR | `allocation_service.py:486-495` (create) and `:545-554` (edit) | Service | No production writer. Licence equality only (`:461-468`), not item equality. |
| L10 | External mark | qty, CIF | `allocation_service.py:685-689` | Service | No production caller. |
| L11 | BOE row CIF | CIF FC | `apps/bill_of_entry/serializers.py:82-111` | Serializer | Only for individual-item licences (`effective_cif_mode.py`). Other licences unchecked. |
| L12 | BOE row quantity | qty | None | None | Not checked. |
| L13 | Trade line CIF | CIF FC | `apps/trade/serializers.py:125-160` (ceiling at `:155`) | Serializer | Skipped under force-save or for a counterpart (`:129-137`). |
| L14 | Non-negative amounts | all | `CHECK` constraints on `InvoiceBOEAllocation` (`apps/reconciliation/models.py:314-320`), `BOEAllotmentAllocation` (`:417-423`), `ExternalInvoiceLink` (`:501-507`) | Database | Other tables carry `MinValueValidator` only, which is not a database rule: `RowDetails` (`bill_of_entry/models.py:395-410`), `AllotmentItems` (`allotment/models/core.py:229-245`), `LicenseTradeLine` (`trade/models.py:536-542`). |
| L15 | Uniqueness | keys | Allotment item `(item, allotment, allocation_basis)` and the planning variant (`apps/allotment/models/core.py:338-348`). BOE row `(BOE, item, transaction type)` (`bill_of_entry/models.py:429`). BOE `(number, date)` (`:235`). Licence number (`apps/license/models/core.py:125`). Licence item `(licence, serial)` (`:942`). | Database | None for allocation pairs. Pair uniqueness is service-only (`allocation_service.py:263-273`, `:474-484`). |

### 8.2 Over-allocation in the database (VERIFIED)

- No database constraint prevents over-allocation of `BOEAllotmentAllocation` or `InvoiceBOEAllocation`. The model docstrings say so (`apps/reconciliation/models.py:213-222`, `:226-262`, `:331-366`).
- The only check constraints on those tables are non-negativity (L14).
- No trigger or function exists in the migrations (search for `CREATE TRIGGER` and `CREATE OR REPLACE FUNCTION` returned no matches under `apps/*/migrations`). `RunSQL` appears in some licence migrations (for example `apps/license/migrations/0005_licensebalance_licenseflags_licensenotes_and_more.py`). Their content was not reviewed in full.

### 8.3 Options (BD-06)

| Option | Description | For | Against |
|---|---|---|---|
| **A. Item-level hard limits; aggregates for display** | Each licence item and dimension is a hard limit. Aggregates are shown but never used to permit a transaction. | Matches the register's proposed rule. An aggregate cannot hide one item's overrun. | Requires removing the licence-wide fallback for zero-CIF items (L3). Some licences may then block until items are attributed. |
| **B. Hard limits at both levels** | Item and aggregate limits both block. | Stronger control. | Aggregates can block a transaction that is fine item by item. More rejections. |
| **C. Quantity hard, CIF advisory** | Quantity blocks. CIF is shown as a warning. | Simpler where units are reliable. | CIF overrun is then permitted. Conflicts with spec §6 item 4. |

**Recommendation (not a decision).** A, as the register recommends, together with a fix to L3.

---

## 9. D6: editing and cancellation after downstream rows exist

The rules and the options are in the lifecycle file: §5 (the operation matrix, with the balance effect of each operation) and §8.1 (BD-07). Summary:

- Today, an allotment can be deleted only when no allocation row exists (`PROTECT`, HTTP 500 on the allotment and 400 on the item). A header BOE link does not block deletion.
- Today, a BOE row cannot be deleted when an allocation exists. Its amount can be edited with no check.
- Today, a trade line cannot be deleted when an allocation exists. Its amount can be edited with no check, and an allocation can then exceed the edited amount silently (`apps/reconciliation/services/allocation_service.py:88-94`, `:141-143`).

---

## 10. Part E: allocation record fields

Mapping for the allocation record. Columns: the requirement in the brief, the existing field, its status, and the gap.

| # | Required field | Existing field: `BOEAllotmentAllocation` / `InvoiceBOEAllocation` | Status | Gap |
|---|---|---|---|---|
| 1 | Source BOE item | `row_details` FK (`reconciliation/models.py:369` / `:268`) | Exists | `RowDetails` is one row per BOE, item and transaction type. |
| 2 | Target allotment item | `allotment_item` FK (`:374`) / n.a. (invoice side targets a sale line, `trade_line` at `:263`) | Exists (allotment side) | None |
| 3 | Licence item | Not stored. Derivable through `row_details.sr_number` and `allotment_item.item`. | **Gap** | The services check licence equality only (`allocation_service.py:461-468`, `:248-255`). An allocation to a different item of the same licence is therefore accepted. |
| 4 | Allocated quantity | `allocated_qty` (`:383` / `:280`), 4 dp | Exists | The unit is not stored (BD-10). |
| 5 | Allocated CIF INR | `allocated_cif_inr` (`:391` / `:288`), 3 dp | Exists | Not tied to FC and a rate. No rate stored (BD-05). |
| 6 | Allocated CIF FC | `allocated_cif_fc` (`:387` / `:284`), 3 dp | Exists | None |
| 7 | Allocation date | `created_on` from `AuditModel` (`apps/core/models.py:96-`) | **Partial** | This is the system timestamp. There is no business or effective date. |
| 8 | Status | `status` (`:396` / `:293`): ACTIVE or REVERSED | Exists | No draft or pending state (lifecycle §2). |
| 9 | Current version and chain | `is_current` (`:399` / `:296`), `superseded_by` (`:400` / `:297`) | Exists | None |
| 10 | Version number | `version` (`:407` / `:304`) | Exists | None |
| 11 | Creation history | `created_on`, `created_by` (AuditModel) | Exists | None |
| 12 | Modification history | `modified_on`, `modified_by` (AuditModel) | Partial | The row keeps only the last modifier. Earlier changes are in the chain and in the log. |
| 13 | Reason | `notes` (`:408` / `:305`). Reversal reason only in `ReconciliationLog.reason` (`:95-`). | Partial | No structured reason. Auto-matches are marked only by free text: `"Auto-reconciled from legacy trade.boes link"` (`apps/reconciliation/services/boe_link_reconciler.py:178`). |
| 14 | Actor of reversal | `modified_by` set by reverse (`allocation_service.py:403`, `:598`) | Exists | None |
| 15 | Link to audit record | None | **Gap** | No foreign key from an allocation row to its `ReconciliationLog` row. |
| 16 | Match basis (automatic or manual) | None | **Gap** | Only the note text distinguishes a backfill from a manual entry. |
| 17 | Tolerance applied | None | **Gap** | The tolerance is a setting (`lmanagement/settings.py:581-582`, `RECONCILIATION_CIF_TOLERANCE` and `RECONCILIATION_QTY_TOLERANCE`), used at match time only. |

**PROPOSED.** Add to the allocation tables: a licence item foreign key (or a check that the item matches), a business or effective date, a rate and rate source where a conversion is involved, a match basis, a structured reason code, and a link to the log row. Each addition is a schema change and needs approval under spec §8.

---

## 11. Enforcement (Part E, last paragraph)

**Over-allocation is enforced at the service level only (VERIFIED).**

- Invoice side: `create_invoice_boe_allocation` and `edit_invoice_boe_allocation`, under `transaction.atomic()` and `select_for_update` on both parents (`apps/reconciliation/services/allocation_service.py:224-308`, `:311-384`).
- Allotment side: `create_boe_allotment_allocation` and `edit_boe_allotment_allocation`, under the same pattern (`:437-519`, `:522-585`).
- Allotment draw: `_allocate_items_atomic`, under the allotment row lock and the licence item row lock (`apps/allotment/views_actions.py:1098`, `:1192`).
- Trade line: serializer validation, skipped under force-save or for a counterpart (`apps/trade/serializers.py:125-160`).
- BOE row: serializer validation, individual-item licences only (`apps/bill_of_entry/serializers.py:82-111`).

**The database enforces (VERIFIED):** non-negative amounts on the three ledger tables (L14), and key uniqueness (L15). It does not enforce any balance, any row-to-allocation sum, or any item or licence limit.

**Consequence for the spec's §6 item 4 ("prevent duplicate allocation, over-allocation and double debit").** This holds only while every writer goes through the service layer. The code does not guard against a second writer. The only production writer of invoice allocations is the backfill command, which uses the same service. Nothing guards against a direct ORM write, a future endpoint, or the parent edits in §6.1.

---

## 12. D8: negative balance (BD-08)

### 12.1 Current behaviour (VERIFIED)

**Blocked:**
- Allotment draw, on quantity and CIF (`views_actions.py:1341-1349`, `:1374-1384`).
- Allocation rows, per dimension, against the parent's remaining amount (`allocation_service.py:209-217`).
- BOE rows, CIF only, for individual-item licences (`apps/bill_of_entry/serializers.py:82-111`).

**Allowed:**
- BOE rows for every other licence. CIF is not checked, and quantity is never checked (`serializers.py:82-111`).
- BOE header M2M changes (`serializers.py:322-345`).
- Trade lines under force-save or for a counterpart (`apps/trade/serializers.py:129-137`).
- Previous-owner hide, with no check (`apps/bill_of_entry/services/boe_service.py:377-420`).

**Hidden by flooring at zero:** every balance figure (`balance_calculator.py:1403`, `:1431`, `:1651`, `:1760`, `:1858`, `:1998`; `apps/core/scripts/calculate_balance.py:98`; `apps/reconciliation/services/allocation_service.py:50-52`). The overrun is not shown anywhere.

### 12.2 Options (BD-08)

| Option | Description | For | Against |
|---|---|---|---|
| **A. Block** (brief's and register's recommendation) | Refuse the transaction. Name the licence item and the dimension. Allow only an authorised correction. | Protects the figure. Matches spec §6. | Blocks legitimate late debits until corrected. Needs the correction process defined. |
| **B. Allow with a flag and an approval record** | Permit the transaction, mark it, require approval. | Records the exception. | Balances can be negative until approved. Needs an approval role (PROPOSED). |
| **C. Allow silently** | Permit and do not show it. | Simplest. | Conflicts with spec §6. Not recommended. This is the current behaviour for legacy BOE rows. |

**Recommendation (not a decision).** A, as the brief and the register recommend.

**Note.** The `balance < 500` check in `validation_service.py:48` is a licence eligibility rule for the legacy path, not a negative-balance rule. It is listed in L4.

---

## 13. BD-10: quantity as an enforced dimension

### 13.1 Current behaviour (VERIFIED)

- Quantity is checked in the allotment draw, against the stored `available_quantity` (`views_actions.py:1341-1349`) and against the allotment requirement (`:1400-1412`).
- Quantity is checked on invoice-side allocations (`allocation_service.py:275-284`), but not on BOE rows (L12).
- Direct-sale quantity is subtracted from item quantity as a raw number (`balance_calculator.py:1861-1927`, `F('qty_kg') − F('allocated_qty')`). `LicenseTradeLine.qty_kg` is kilograms by field name (`apps/trade/models.py:536`). The item's `unit` (`apps/license/models/core.py:914`) can be a different unit. No conversion was found in the balance or allocation modules.
- The stored and live quantity figures round differently (§2, observation 2).

### 13.2 Options (BD-10)

| Option | Description | For | Against |
|---|---|---|---|
| **A. Hard limit, units matched** | Quantity blocks transactions. Units are normalised before comparison. | Quantity is a real physical limit. Matches spec §6 item 4. | Needs a unit conversion table. Mismatched units block until fixed. |
| **B. Advisory** | Quantity is shown, never blocks. | No conversion needed. | No physical control. |
| **C. Hard where units match, otherwise CIF only** | Quantity blocks only when units are equal. Otherwise CIF alone decides. | Works without a conversion table. | Some quantity overruns are then not caught. |

**Recommendation (not a decision).** A, once the unit conversion is defined. The register says "units must match before comparison", which this draft supports.

---

## 14. Summary of open points

Each is a decision for the owner. Nothing here is adopted.

| ID | Decision | Options | Register recommendation | Status |
|---|---|---|---|---|
| BD-01 | Does an unconsumed allotment reduce available balance? | A reservation, B utilisation only, C hybrid | Option A matches the brief; sign follow-up pending | **Open.** Register summary says "answered, provisional". Register body says "queued". This draft treats it as open. |
| BD-02 | Automatic allocation when a BOE exceeds an allotment | A automatic, B explicit, C hybrid | A, with the excess as direct utilisation | Open. Depends on BD-01. |
| BD-03 | Order and cap when one BOE covers several allotments | A owner-specified order, B explicit split | B | Open. Interacts with BD-02. |
| BD-04 | Partial-invoice replacement mechanism | A strict, B permitted excess as amendment | A | Open |
| BD-05 | Foreign currency and INR | A store and never recalculate, B derive for display, C revaluation event | Never recalculate historical FC at a current rate | Open |
| BD-06 | Item-level and aggregate limits | A item hard, aggregates display, B both hard, C quantity hard and CIF advisory | A | Open |
| BD-08 | Negative balance | A block, B flag and approval, C allow silently | A | Open |
| BD-10 | Quantity as an enforced dimension | A hard with units matched, B advisory, C hard where units match | A, once units are defined | Open |

BD-07, BD-09, BD-11 and BD-12 are in the lifecycle file.

---

## 15. Limits of this review

- Static reading only. Statements about the results of a request, such as HTTP 400 or 500, are reasoned from the code and were not executed.
- Scenario figures in §3 and §6.1 are computed by reading the formulas. They should be confirmed by the test matrix (`DFIA_BALANCE_TEST_MATRIX.md`, not reviewed here) before any figure is relied on.
- The race window described in L2 is a reading of the code. It was not reproduced.
- The brief is not in the repository, so the D-part mapping is taken from the spec and the register.
- Line numbers are for the working tree on 2026-11-01.
