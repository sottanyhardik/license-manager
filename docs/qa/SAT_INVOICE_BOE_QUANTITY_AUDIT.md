# SAT — Invoice ↔ BOE Quantity Audit (read-only)

Date: 2026-11-20 · Branch: `feature/v5` · Auditor: SAT sub-agent (invoice ↔ BOE quantity workstream)
Scope: audit only. No application code, formula, migration or data was changed. This file is the only repo file written.

## 1. Rule under audit (owner SAT requirement)

1. Invoice quantity present and valid → use it.
2. Otherwise use the quantity of the correctly matched BOE transaction(s) (strongest identifiers: invoice ref, licence, BOE number, item identity).
3. Neither exists → flag the quantity as missing. Never assume zero silently.
4. Invoice on several BOEs → aggregate only the relevant BOE quantities. Several invoices on one BOE → do not give the full BOE qty to every invoice. No fallback across unrelated invoices or import items.
5. CIF and quantity are reconciled separately; the quantity fallback must not determine CIF.

## 2. Methodology

- Used the code index (`.claude/index/`) plus `grep qty_kg` over `backend/apps` (excluding tests, migrations and seeds). That gave 25 files, and every non-admin consumer was read at the cited lines.
- **Real data:** SELECT-only queries against `lmanagement@localhost`, run through `manage.py shell`. Script: `~/lm_sat_evidence/cifrecon/qty/boe_qty_realdata.py` and `…2.py`. Logs: `boe_qty_realdata.log` and `boe_qty_realdata2.log`. Both runs exited 0.
  - Locally `trade_licensetrade`, `trade_licensetradeline`, `InvoiceBOEAllocation`, `BOEAllotmentAllocation`, `ExternalInvoiceLink` and `trade_licensetrade_boes` all have 0 rows (re-confirmed). Only the BOE side can be audited on real data.
- **Invoice scenarios:** 31 throwaway characterisation tests in `~/lm_sat_evidence/cifrecon/qty/test_sat_invoice_boe_qty.py`. They ran on their own DB `test_lmanagement_sat_qty`, from `backend/`, with `-c pytest.ini --rootdir=.`.
  - Command: `TEST_DB_NAME=test_lmanagement_sat_qty .venv/bin/python -m pytest -c pytest.ini --rootdir=. --import-mode=importlib -q --no-cov -p no:cacheprovider -rA <file>`
  - Result: **31 passed, exit 0**. Log: `pytest_run2.log`, exit code in `pytest_run2.exit`.
  - Each test pins *current* behaviour. "Passed" means the behaviour is as described, not that it meets the rule. The verdict per rule is in §4.
- Prior work cited, not redone: `docs/qa/SAT_FINANCIAL_AUDIT.md` (trade tables empty; SAT-FIN-005 double count, test `test_debit_double_counts_when_boe_not_linked_to_matching_trade`; D06). Decisions: `docs/decisions/2026-11-17-trade-line-pricing-and-m2m-consumption.md`, `2026-11-20-cross-surface-owner-decisions-da-df.md` (D-F: one available-qty formula, 3 dp, floored at 0), `docs/decisions/LEDGER_APPROVED_SEMANTICS.md` (no quantity clauses), and DEC-01…DEC-10.

### Field-level facts

| Field | Definition | Consequence |
|---|---|---|
| `LicenseTradeLine.qty_kg` | `trade/models.py:536`: Decimal(20,4), `default=0`, **no validators**, no null | "0" and "missing" cannot be told apart (confirmed). Negative values can be stored (Q05). |
| `LicenseTradeLine` unit | none: the field name assumes kg | No unit is captured on the invoice. |
| `RowDetails.qty` | `bill_of_entry/models.py:406`: Decimal(15,3), `default=0`, min 0, no null | A missing BOE qty is stored as 0. |
| `RowDetails` unit | none | The BOE unit is assumed to be the item's unit. |
| `LicenseImportItemsModel.unit` | `license/models/items.py:56`, choices `kg/pcs/nos/mts` (`core/constants.py:38`) | Not validated at DB level, so case variants exist (§5). |
| Trade cancel state | none (no status, cancelled or void field) | Deletion is the only way to cancel (Q16). |
| BOE cancel / reversal state | none. Only `is_dispute` (DEC-07) and the hidden/OTH marker | A reversed BOE cannot be represented. |
| Blank `qty_kg` via API | `trade/api/serializers.py:94-96` deletes `''`, so the model default 0 applies | Blank becomes 0 silently (Q03). |

**Is there an invoice-qty → BOE-qty fallback? Partly.**

- No consumer reads the BOE qty as a substitute for a missing invoice qty at invoice level.
- The item-availability engine, however, is **BOE-first**. A SALE line whose trade is M2M-linked to a BOE row on the same item contributes 0 (`balance_calculator.py:1898-1902, 1926-1934`). The BOE row's qty is then the debit (`:1995-2003`).
- So for item availability the BOE qty is always used whenever a same-item BOE is linked, whether or not the invoice qty is valid. That is the reverse of rule priority 1 (Q06, Q07).

## 3. Consumer inventory

| # | Consumer | file:line | Qty source | Fallback to BOE? | Missing-qty handling | Unit handling |
|---|---|---|---|---|---|---|
| C1 | Item available qty (engine, D-F) | `license/services/balance_calculator.py:1872-1935, 1967-2009` | `RowDetails.qty` (all visible DEBIT) + SALE `qty_kg − allocated_qty` when no same-item M2M BOE | Implicit: a same-item M2M BOE replaces the invoice qty entirely | 0 → consumes 0, no flag; negative → floored 0 | none |
| C2 | Bulk item available (Item Report, snapshot, licence serializer `available_quantity`) | `balance_calculator.py:2011-2075+`; `license/api/views/item_report.py:315` | same as C1 | same | same | none |
| C3 | SALE create guard | `trade/api/serializers.py:450-466` | request `qty_kg or 0` vs C1 | n/a; only when the request has no `boes` | blank/None → 0 passes | none |
| C4 | SALE update path | `trade/api/serializers.py:525+` | none | n/a | **no qty check** (Q24) | none |
| C5 | Billed-no-BOE qty (Customs Ledger, licence serializer) | `license/api/serializers/license.py:418-452`; `license/services/item_usage.py:224-259` | `Sum(qty_kg)` where `trade__boes__isnull=True` | No | 0 counted as 0. Serializer `except Exception: return 0.0` (`license.py:451-452`), and `float()` | none |
| C6 | Billed-no-BOE lines (Pivot trace / D3 split) | `item_usage.py:199-221` | same filter as C5 | No | same | none |
| C7 | Item Pivot balance_qty | `license/services/item_pivot_service.py:496, 509-511, 807, 826-830` | BOE rows raw + C5 `billed_qty` | No | same as C5 | grouping key unit-suffixed (`plan_grouping.py:84-86`, case-normalised) |
| C8 | Item Pivot intelligence | `item_pivot_intelligence.py:174, 224` | C5 | No | same | none |
| C9 | Financial ledger invoice rows | `license/services/license_balance_ledger_builder.py:402, 632` | `qty_kg` if mode QTY, else `None` | No | CIF/FOB mode → blank; QTY-mode 0 → shown as 0 | none |
| C10 | Ledger invoice reconciliation block | `license_balance_ledger_builder.py:1078-1085` | `qty_kg`; `matched_qty = qty_kg − remaining` (formal allocations only) | No | status uses **CIF only**, so a qty mismatch never moves the status | none |
| C11 | Ledger timeline | `license_balance_ledger_builder.py:1369-1380` | `Sum(qty_kg)` per trade | No | 0 | none |
| C12 | Formal allocation service | `reconciliation/services/allocation_service.py:68-145, 209-221, 224-300` | `qty_kg − allocated`; row `qty − allocated − external` | No | qty 0 allowed; CIF-only allocation accepted (Q13) | none |
| C13 | Legacy auto-reconciler | `reconciliation/services/boe_link_reconciler.py:55-68, 135-145` | `qty_kg` vs `RowDetails.qty`, same item, tolerance 1.000 (`settings.py:606`) | No (`alloc_qty = min(…)`) | invoice qty 0 vs BOE qty > 1 → `mismatch` (Q23) | none |
| C14 | Qty comparison report | `reconciliation/selectors.py:326-384, 393-398` | trade-level `Sum(qty_kg)` vs `Sum(RowDetails.qty)` of all linked BOEs, **all items** | No | 0 | none. Not item-level (Q28); full BOE qty given to each invoice (Q27) |
| C15 | Reconciliation trade-line selector | `reconciliation/selectors.py:106` | `qty_kg` | No | raw | none |
| C16 | Purchase/Profit report | `license/services/purchase_profit_report.py:518-535` | `qty_kg or 0` | No | 0 | none |
| C17 | Accounting allocation by QUANTITY | `accounting/services/invoices.py:273-280`; `accounting/domain/money.py:26-34` | `Sum(qty_kg or 0)` | No | all-zero weights → `ValueError` (flagged); a mix of zero and non-zero → the zero-weight trade silently gets 0 | "weight in kg" |
| C18 | Accounting trade source | `accounting/selectors/trade_source.py:81` | `qty_kg or 0` | No | 0 | none |
| C19 | Sale invoice document payload | `trade/services/invoice_document_service.py:83` | `str(qty_kg)` | No | "0.0000" | none |
| C20 | Bill of Supply / Purchase invoice PDFs | `trade/bill_of_supply_pdf.py:423-424`; `trade/purchase_invoice_pdf.py:412-413` | `qty_kg` (QTY mode) | No | 0/None → "0.000 Kg" | **hard-coded "Kg"** regardless of item unit |
| C21 | Transfer letter | `core/utils/transfer_letter.py:822` | `qty_kg` | No | raw | none |
| C22 | Trade copy/pair service | `trade/services/trade_service.py:271, 427` | copies `qty_kg` | n/a | copies 0 | none |

## 4. Scenario matrix

All evidence is in `~/lm_sat_evidence/cifrecon/qty/test_sat_invoice_boe_qty.py`, run 2, exit 0, 31 passed. Each test name is prefixed with the ID.

| ID | Scenario | Expected per rule | Actual (pinned) | Verdict |
|---|---|---|---|---|
| Q01 | Valid invoice qty 30, no BOE | consume 30 | available 70 | PASS |
| Q02 | QTY line qty 0 (CIF 500), no BOE | flag missing qty | consumes 0, no flag; CIF 500 still billed | **FAIL** |
| Q03 | CIF-mode line, qty `''` via API | flag missing | stored 0, consumes 0 | **FAIL** |
| Q04 | qty `null` via API | reject | serializer rejects | PASS |
| Q05 | qty −5 via API | reject | accepted and stored −5; consumption floored 0 | **FAIL** |
| Q06 | invoice qty 0 + same-item M2M BOE 40 | use BOE 40 | item available 60 (BOE used). Billed-no-BOE qty 0 | PASS (engine) |
| Q07 | invoice qty 100 + same-item M2M BOE 40 | use invoice 100 | BOE 40 used; 60 invoiced qty not consumed, no warning in the engine | **FAIL vs rule** (BOE-first by design) → DEC-20 |
| Q08 | one invoice 50 on 2 BOEs (30+20) | aggregate 50 | 50 | PASS |
| Q09 | M2M BOE row only on another item B | no cross-item fallback | engine PASS (A consumes its own 50, B debits 20). Billed-no-BOE qty for A = absent/0 while A is consumed 50 | **FAIL** (surface drift) |
| Q10a | 2 invoices × 30 on one BOE row 60 (legacy) | BOE counted once | 60 once | PASS |
| Q10b | 2 invoices × 30 on one BOE row 30, auto-reconciler | not full BOE qty to each | first `auto_migrated`, second `no_match` | PASS |
| Q10c | same as Q10b, item availability | the 30 of unmatched invoiced qty uses invoice qty or is flagged | only 30 consumed; 30 silently dropped | **FAIL** → DEC-20 |
| Q11 | formal split 30+20 of a 50 invoice | aggregate | direct 0, BOE 50 | PASS |
| Q12 | formal partial 60 of 100 | 60 BOE + 40 invoice | direct 40, available 0 | PASS |
| Q13 | formal allocation qty 0 / CIF 300 (row 30 kg / 300) | qty represented once | CIF excluded once (correct). Qty: invoice 30 + BOE 30 = **60 consumed** | **FAIL** (qty double count) |
| Q14 | 2nd invoice over-allocates a fully used BOE row | reject | `ValidationError` | PASS |
| Q15a | duplicate SALE, same buyer and invoice number | reject | `IntegrityError` (constraint `trade/models.py:314-318`) | PASS |
| Q15b | 2 SALEs with blank invoice number, same line | detect duplicate | both consume (60) | **FAIL** |
| Q16 | cancelled invoice | not consumed | no cancel state exists; delete restores qty | BLOCKED (feature absent) → DEC-24 |
| Q17 | reversed allocation | invoice qty back to direct | direct 30, available 40 | PASS |
| Q18 | hidden (OTH, via `hide_boe`) BOE M2M-tagged to SALE, same item | no visible BOE → use invoice qty | BOE row excluded **and** invoice line treated as represented → **0 consumed** (available 100) | **FAIL** → DEC-23 |
| Q19 | disputed BOE row (`is_dispute`) | per DEC-07 | still debited (cite DEC-07, 7 rows) | cited |
| Q20 | item unit `pcs`, invoice `qty_kg` 10 | convert or block | 10 pcs consumed, no warning; no unit on line or row | **FAIL** (latent: all real items are kg variants) |
| Q20b | item unit `KG` vs `kg` | same math | identical | PASS |
| Q21 | CIF independent of qty | CIF not derived from qty | SALE CIF 250 billed with qty 0 | PASS |
| Q22 | BOE rows on A and B, invoice on A via M2M | qty item-level | qty: A 70, B 80 (correct). CIF: both rows excluded (accepted BOE-level trade-off) | PASS (qty); CIF as documented |
| Q23 | CIF-mode invoice (qty 0) vs BOE qty 30, reconciler | match or flag | `mismatch`; qty never back-filled | PASS (flagged) |
| Q24 | SALE update qty 10 → 500 (item 100) | reject or flag | accepted; available floored 0 | **FAIL** |
| Q25 | formal allocation 30/30, no M2M | billed-no-BOE qty 0 | engine direct 0, but billed-no-BOE qty **30** → Pivot `balance_qty` double-subtracts | **FAIL** (surface drift) |
| Q26 | paired PURCHASE/SALE transfer 30 | net 0 | engine 0, billed-no-BOE qty **30** | **FAIL** (surface drift) |
| Q27 | `qty_comparison`: 2 invoices × 30 on one BOE 60 | reconcile | each invoice compared to the full 60 → 2 false mismatches (−30) | **FAIL** |
| Q28 | `qty_comparison`: invoice on A 30, BOE A 10 + B 20 | flag A (diff 20) | totals 30 = 30 → no flag | **FAIL** |

Totals: 15 PASS, 15 FAIL (one of them, Q07, is a FAIL against the rule but BOE-first by design), 1 BLOCKED, 1 cited (Q19).

## 5. Real-data BOE quantity findings (`lmanagement@localhost`, SELECT only)

| Check | Count | Detail / examples |
|---|---|---|
| RowDetails total / DEBIT | 168,629 / 22,075 | CREDIT 146,554 |
| DEBIT qty NULL / negative | 0 / 0 | the field does not allow either |
| DEBIT qty = 0 | 46 | 43 with CIF > 0 (**CIF 5,056,539.16**), 3 with qty and CIF both 0 |
| DEBIT qty > 0, CIF = 0 | 0 | — |
| qty 0 & CIF > 0, by BOE | 12 BOEs | **5128829** (2026-11-17, 23 rows / 23 licences, CIF 2,031,951.81, *not frozen*). **8741982** (2022-05-19, 7 rows, CIF 2,581,614.66, frozen). 9579282 (1 row, 218,641.50). 4426905, 5784121 (not frozen), 2587558, 2587371, 3526253, 9686988, 5953537, 9865292, 2643948 |
| Top examples | — | 3011001620 item 13270 BOE 8741982 qty 0.000 CIF 864,780.05. 0311055523 item 36894 BOE 5128829 qty 0 CIF 331,251.86. 3411007849 item 35672 BOE 9579282 qty 0 CIF 218,641.50 |
| qty 0 & CIF_FC 0 but CIF_INR > 0 | 2 | 0311010085 item 26456: BOE 7788510 (INR 1,844,068.22) and BOE 7896752 (INR 37,440.86). CIF FC is missing too, so these contribute 0 to the CIF debit |
| Item unit values | 26,818 items | `kg` 26,784 · `KG` 22 · `Kg` 12 (34 off-choice case variants). 0 pcs/nos/mts |
| DEBIT rows on case-variant items | 33 | KG 23 rows (qty 263,161.130), Kg 10 rows (122,448.100). Math unaffected (Q20b). Allotment PDF lowercases the unit (`allotment_pdf.py:54-56`); invoice PDFs hard-code "Kg" |
| Items with BOE qty > licensed qty | 35 items | total excess **3,613,764.872**. Top: 0910061491 item 3127 (722,264 vs 1,454,600). 0910061490 item 3142 (+661,976.97). 0910060696 item 10630 (+588,953.92). Hidden by the D-F floor at item level |
| Items with licensed qty 0 but BOE debits | 6 | 0310506768 item 6418 (BOE qty 30,742, CIF 35,353.30). 5011000781 item 32393 (2,130 / 13,354.56). 0310520657 item 31757 (652.41 / 44,791.85). 0310837138 item 7669 (0 / 15,353.17) |
| Suspicious tiny qty (qty < 1 & CIF > 1,000) | 12 rows | 3011006488 item 35111 BOE 9695859 qty 0.010 CIF 661,149.31. 0311042134 item 34816 same BOE, qty 0.010 CIF 32,391.65 (probably placeholder quantities) |
| Unit price > 1,000 USD/kg | 614 of 22,029 priced rows | indicator only (possible unit or qty entry issue); < 0.01 USD/kg: 1 |
| Duplicate (BOE, item, D) rows | 0 | blocked by `unique_together` |
| BOEs carrying `invoice_no` text | 14,352 of 14,425 | free text only; no FK to trade (0 trades locally) |
| Disputed DEBIT rows | 7 (qty 44,759, CIF 131,125.49) | = DEC-07 |
| Allotment items qty 0 | 15 of 11,610 (0 with CIF > 0) | — |

## 6. Exception table

Invoice-side rows are synthetic: there is no local trade data, so they come from the test DB and show per-event impact. BOE rows are real.

| Licence | Import item | Invoice | BOE | Expected CIF | Actual CIF | CIF diff | Expected qty | Actual qty | Qty diff | Root cause | Severity | Financial impact |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| test (Q13) | item 1 | SALE 30 kg / 300 | row 30 kg / 300 | 300 once | 300 once | 0 | 30 consumed | 60 consumed | +30 | allocation accepts `allocated_qty=0` with CIF > 0. Qty and CIF netting are independent (`balance_calculator.py:1881-1934` vs `:417-456`) | High (latent) | item availability understated by the invoice qty per event |
| test (Q18) | item 1 | SALE 30 | hidden OTH BOE 30 | 30-CIF once via invoice | as expected | 0 | 30 | 0 | −30 | `has_linked_boe` (`:1898-1902`) ignores hidden-ness; the debit side excludes hidden (`:1996`) | Medium (latent) | availability overstated |
| test (Q07/Q10c) | item 1 | SALE 100 (or 2×30) | M2M row 40 (or 30) | n/a | n/a | 0 | 100 (60) per rule | 40 (30) | −60 (−30) | BOE-first legacy representation; no remainder logic for the M2M path | Medium | availability overstated; owner DEC-20 |
| test (Q02/Q03) | item 1 | SALE qty 0, CIF 500 | none | 500 | 500 | 0 | missing (flag) | 0, no flag | unknown | `qty_kg default=0`; blank dropped (`serializers.py:94-96`) | Medium | availability overstated by the unknown qty |
| test (Q25/Q26) | item 1 | SALE 30 formal-allocated / paired | row 30 | — | — | 0 | Pivot billed 0 | Pivot billed 30 | +30 | `trade__boes__isnull` filter (`item_usage.py:250-259`) differs from the engine predicate | Medium | Pivot / Customs-Ledger billed qty and Pivot `balance_qty` understated by 30 |
| test (Q24) | item 1 | SALE update 10→500 | none | — | — | 0 | reject > 100 | 500 stored | +400 over | update path lacks the create-path guard (`serializers.py:450-466` only in create) | Medium | over-consumption hidden by the floor |
| test (Q27) | item 1 | 2 × SALE 30 | one BOE 60 | — | — | — | diff 0 | diff −30 each | false flags | `selectors.py:370-374` compares each trade to the full BOE total, across items | Low | report noise / hidden item mismatch (Q28) |
| 3011001620 | 13270 | — | 8741982 | 864,780.05 | 864,780.05 | 0 | unknown (missing) | 0 | missing | BOE qty 0 stored as a valid zero | High (data) | item available qty not reduced for this import. Same for 43 rows / 12 BOEs, total CIF 5,056,539.16 |
| 0311055523 (+22 licences) | 36894 … | — | 5128829 (2026-11-17) | 2,031,951.81 | same | 0 | unknown | 0 | missing | recent un-frozen import with qty 0 | High (data) | as above |
| 0311010085 | 26456 | — | 7788510, 7896752 | INR 1,881,509.08 → FC unknown | 0 | −(FC of 1,881,509.08 INR) | unknown | 0 | missing | both qty and CIF FC are 0, only CIF INR populated | High (data) | CIF debit understated; licence balance overstated |
| 0910061491 (+34 items) | 3127 … | — | multiple | — | — | — | ≤ 722,264 | 1,454,600 | +732,336 (all 35: +3,613,764.872) | BOE qty > licensed qty (possible unit or qty entry issue) | Medium (data) | over-use invisible at item level (D-F floor) |

## 7. Verdicts

- **Rule 1 (use invoice qty when valid): FAIL.** The item engine is BOE-first whenever a same-item legacy BOE is linked (Q07, Q10c). On the formal path the remainder logic follows the rule (Q12).
- **Rule 2 (fallback to the matched BOE qty): PASS** for item availability (Q06, Q08, Q11), **not applied** on invoice-level surfaces (C5–C11, C16–C21 show 0 or blank). The match uses the same item and the trade's own `boes` (`boe_link_reconciler.py:55-63`), which is correct. The reconciliation report C14 is not item-level (Q28).
- **Rule 3 (flag missing, never zero): FAIL.** There is no missing-qty state anywhere (Q02, Q03, Q05). Real data has 46 zero-qty BOE debit rows.
- **Rule 4 (multi-BOE / multi-invoice / no cross-item): mostly PASS in the engine** (Q08, Q10a, Q10b, Q11, Q14, Q22). **FAIL** in `qty_comparison` (Q27, Q28), billed-no-BOE qty (Q09), the hidden-BOE case (Q18) and CIF-only allocation (Q13).
- **Rule 5 (CIF and qty separate): PASS structurally** (Q21, Q22): CIF uses BOE-level representation, qty uses item-level representation. **But** the separation lets CIF-only allocations double count qty (Q13).
- The quantity side of SAT-FIN-005 (SALE and BOE not linked): the qty is counted twice (invoice direct + BOE), the same as CIF. That is covered by the cited test, not re-tested.

## 8. Proposed register entries (not written to the registers)

Existing entries cited, not duplicated: DEC-01/SAT-DEF-001 (ARO qty), DEC-02/DEF-002 (`is_boe` without M2M), DEC-03 (rowless/duplicate BOE), DEC-05 (cross-licence M2M), DEC-07 (disputed rows, Q19).

### New owner questions

- **DEC-20:** A legacy M2M-linked same-item BOE qty differs from the invoice qty (Q07, Q10c). Which should item consumption use?
  - (a) BOE qty only (current behaviour).
  - (b) Invoice qty (the SAT rule).
  - (c) BOE qty plus the unmatched invoice remainder as direct consumption, which is what the formal path does (Q12).
- **DEC-21:** CIF- or FOB-mode SALE lines and blank qty are stored as 0. Options:
  - (a) Require qty on every SALE line.
  - (b) Keep 0 but mark it "qty missing" everywhere.
  - (c) Derive it from the matched BOE when one exists.
- **DEC-22:** Should a formal invoice↔BOE allocation with `allocated_qty=0` but CIF > 0 be allowed (Q13)? Options:
  - (a) Reject it.
  - (b) Treat CIF-matched rows as representing the qty in proportion.
- **DEC-23:** Should a hidden (OTH, previous-owner) BOE tagged to a SALE still suppress the invoice's own qty (Q18)? The CIF path already ignores hidden BOEs.
- **DEC-24:** Is a "cancelled invoice" state needed (Q16), or is deletion the approved cancellation?
- **DEC-25:** Unit policy.
  - Does `mts` mean metres or metric tonnes?
  - Should the 34 `KG`/`Kg` items be normalised to `kg`?
  - Should SALE `qty_kg` be blocked on non-kg items?
  - Should the invoice PDFs stop hard-coding "Kg"?
- **DEC-26:** For the 43 BOE debit rows with qty 0 and CIF > 0 (5,056,539.16 CIF; BOE 5128829 dated 2026-11-17), should the qty be re-imported from the DGFT ledger, or flagged "qty missing" in item availability?

### New defects

| ID | Defect | Severity | Evidence |
|---|---|---|---|
| SAT-DEF-120 | Missing invoice qty silently 0 (no flag) | Medium | Q02, Q03 |
| SAT-DEF-121 | Negative `qty_kg` accepted (no validator) | Low-Med | Q05; `trade/models.py:536` |
| SAT-DEF-122 | SALE update path skips the qty availability guard | Medium | Q24 |
| SAT-DEF-123 | CIF-only formal allocation double counts qty | High (latent) | Q13 |
| SAT-DEF-124 | Hidden BOE tagged to SALE zeroes the invoice qty | Medium (latent) | Q18 |
| SAT-DEF-125 | `billed_no_boe_qty` predicate differs from the engine (trade-level, ignores formal allocation and paired transfers); feeds Customs Ledger and Item Pivot `balance_qty` | Medium | Q09, Q25, Q26 |
| SAT-DEF-126 | `qty_comparison` not item-level and gives the full BOE qty to each invoice | Low | Q27, Q28 |
| SAT-DEF-127 | 43 BOE debit rows qty 0 with CIF > 0 (5,056,539.16), 12 BOEs | High (data) | §5 |
| SAT-DEF-128 | 2 BOE rows with CIF FC 0 and qty 0 but CIF INR 1,881,509.08 (0311010085 item 26456) | High (data) | §5 |
| SAT-DEF-129 | 35 items BOE qty > licensed qty (+3,613,764.872); 6 items with licensed qty 0 but BOE debits | Medium (data) | §5 |
| SAT-DEF-130 | No unit on trade line or BOE row; 34 off-choice unit case variants; PDFs hard-code "Kg" | Low (latent) | Q20, §5, C20 |
| SAT-DEF-131 | Ledger invoice status ignores qty; `get_billed_no_boe_qty` swallows exceptions → 0.0 | Low | C10; `license.py:451-452` |
| SAT-DEF-132 | Blank invoice number lets duplicate SALE records both consume | Low | Q15b |

## 9. Evidence paths

`~/lm_sat_evidence/cifrecon/qty/`:
- `test_sat_invoice_boe_qty.py`
- `pytest_run1.log` (29 passed, exit 0)
- `pytest_run2.log` and `pytest_run2.exit` (31 passed, exit 0)
- `boe_qty_realdata.py` / `.log` (exit 0)
- `boe_qty_realdata2.py` / `.log` (exit 0)

No business-rule, API contract or schema change was made.
