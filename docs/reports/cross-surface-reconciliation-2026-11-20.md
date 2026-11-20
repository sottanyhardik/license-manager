# Cross-surface financial & quantity reconciliation — 2026-11-20

Branch `feature/v5` · local dev DB `lmanagement@localhost` · read-only (every run inside a rolled-back transaction) ·
tool: `python manage.py audit_cross_surface_reconciliation --out <file>` (`apps/license/services/cross_surface_reconciliation.py`).
Raw output: `/tmp/recon_full2.json` (register + per-licence surface values), log `/tmp/recon_full2.log` (exit 0).

**Verdict: acceptance criterion NOT met.** Licence-level CIF already agrees across Licence Detail Overview, Item Pivot and Item
Report for every licence. The remaining differences sit in item-level stored columns, an uncapped item-attributed value
(an owner decision), and export formatting. **No correction has been applied.** Each one needs the owner decision or the
approval listed in §6.

## 1. Scope and method

Each surface is read through the exact backend function its screen calls. Each metric is then diffed against the
canonical engine, using Decimal and tolerances of CIF 0.01 and qty 0.001.

| Surface | Function (what the UI renders) |
|---|---|
| Canonical | `balance_snapshot.get_snapshot_bulk` + `LicenseBalanceCalculator.calculate_debit/allotment/trade/financial_balance_for_licenses` |
| Licence Detail → Overview | `license_overview_summary.get_overview_counts` (summary cards) |
| Licence Detail → Import Items | `compute_item_ledger_rows(include_canonical=True)` rows + `footer_totals.actual_effective_balance_cif` |
| Item Pivot (classic) | `select_pivot_licenses` → `ItemPivotService.build` licence rows + item cells |
| Item Report | `ItemReportView.generate_report` (Excel is built from the same `report_data`) |
| Customs Ledger PDF | `custom_ledger_pdf.get_custom_ledger_data` (sample of 200 licences) |

| Coverage | Count |
|---|---|
| Licences checked (all with import items; 3 of 2,185 have none) | **2,182** |
| Import-item records | **26,818** |
| Pivot product cells (licence × item × norm) | **14,314** |
| Discrepancy records | **4,831** across **2,071** licences |
| Units present | `kg` 26,784 · `KG` 22 · `Kg` 12 (no MT/MTS; no conversion is involved) |

## 2. Canonical formulas (Phase 1 — as implemented, unchanged)

**CIF (licence level):**
- ORIGINAL = Σ export-item `cif_fc` (`calculate_credit`).
- BOE = `calculate_debit` (allocation-aware). The raw BOE figure is `calculate_boe_debit_total`.
- ALLOTMENT = outstanding, net of BOE allocation and M2M.
- BILLED = `calculate_trade`.
- AVAILABLE = financial balance: opening + purchase − sale − debit − allotment. It is signed, with `is_over_utilised`.
- For a licence bought from a previous owner, the balance runs from the opening balance, and the previous owner's BOEs
  are hidden.

**Quantity (item level):**
- TOTAL = `quantity`.
- DEBITED = `calculate_debited_quantity_for_items` (BOE rows).
- OUTSTANDING ALLOTTED = `get_outstanding_allotment_totals_for_items`.
- DIRECT SALE = unpaired SALE quantity.
- AVAILABLE has four implementations today (see RC5/RC13):
  - **Live:** `ItemBalanceCalculator.calculate_available_quantity_for_items` = qty − debited − outstanding − direct
    sale. Used by Item Report.
  - **Snapshot inline:** the same, but omitting direct sale. Floored at 0.
  - **Legacy:** `core.scripts.calculate_balance.calculate_available_quantity`, floored to a **whole number**. Used by the
    Customs Ledger PDF and by the stored `available_quantity` column.
  - **Stored column:** what the Import Items tab shows.

**Planning:**
- A valid plan is `is_active`, not deleted and not cancelled.
- Licence planned CIF = Σ `planned_cif_fc`.
- Item attribution follows `plan.import_item_id` (Item Report), or `source_item_ids` with D1 proportional attribution
  (Pivot).

## 3. What reconciles (0 discrepancies on 2,182 licences)

- **Total, Debited, Allotted, Billed, Balance and Planned CIF:** Overview = Pivot licence row = Item Report `balance_cif` =
  canonical engine.
- Pivot licence row = Σ pivot item cells for debited, allotted, billed and planned CIF (RC9: 0).
- Planned qty and CIF: Item Report Σ = Overview = Pivot Σ cells (RC6: 0). There are no duplicate plan lines.
- Item Report available qty = live engine. Snapshot qty = live qty (RC5: 0; no direct-sale or over-debited items locally).
- Raw BOE = allocation-aware BOE on every licence (RC1: 0). This is latent: it diverges as soon as invoice-BOE allocations
  exist.
- Pivot: no licence appears in two groups.

## 4. Root-cause register (ranked by financial impact)

| # | Root cause | Records / licences | Impact | Class | Proposed correction |
|---|---|---|---|---|---|
| **RC4a** | Live item-attributed `available_value` is **not capped at the licence balance**. `condition_pool._resolve_available_value` returns `cif_fc − item debit − outstanding` for any item with `cif_fc > 0`. It ignores `individual_item_cif_override` (contrast `effective_cif_mode.py`), while the %-condition branch *is* capped. | 1,343 items / 1,208 licences | Σ excess over the licence balance **502,991,936.21** | **Canonical-rule conflict** | Owner decision **D-A** |
| RC4b | Item Report "Available Balance" and the `min_balance` filter read the stored `available_value`. There are two writers with different formulas: `update_balance_values` writes the item-attributed value as `float`, while the signal writes the licence balance. | 1,712 items / 320 licences | Σ abs Δ 1,066,131,622.15 | Staleness / display | Read live `available_value_bulk_map` in Item Report (after D-A) |
| RC11 | Original CIF lives on export items. On these licences the import items carry `cif_fc = 0` (a shared ceiling), so the Import Items "Total CIF" footer shows 0. | 632 licences | 707,104,614.62 | Legitimate, unlabelled | Footer shows the licence CIF ceiling with a "licence-level" label |
| RC12 | Σ import `cif_fc` ≠ Σ export `cif_fc`. Example: 0811013826 has export 78,655,056.19 vs import items 908,257.00. | 80 licences | 126,525,181.39 | Data question | Data review list for the owner. Do not auto-repair |
| RC3 | Import Items tab reads stored `debited_*`, `allotted_*` and `available_quantity`. Stored allotted qty keeps allotments already covered by BOEs, so Balance Qty is understated. | 973 checks / 727 licences. Balance qty: 641 genuine (Σ 44,055,815.273 kg) + 85 sub-1 kg rounding | CIF Σ 9,778,969.29 | Staleness | Use live item maps (`calculate_debited_*`, outstanding, live qty) — needs approval (API values change) |
| RC2/RC8 | Overview cards show Total, Debited and Allotted, but not the opening-balance or hidden-BOE adjustment, so Total − Debited − Allotted ≠ Balance on screen. Billed is 0 on all 11. | 11 licences | 4,412,937.86 | Legitimate, unlabelled | Add an "Opening / prior-owner adjustment" (and Billed) line to the cards |
| RC7 | The pivot drops licences whose `purchase_status` is NULL (`purchase_status__code__in`). Licence Detail and Item Report show them. The `min_balance` filter also differs: the pivot filters on the live licence balance, Item Report on the stored item value. | 69 licences | presence | Scope | Owner: include NULL status as "Unassigned"? Align `min_balance` semantics |
| RC13 | The Customs Ledger PDF item "Available" uses the legacy whole-number floor. | 2,222 of 2,491 sampled items (200 licences), all < 1 kg | qty < 1 per item | Rounding | Use the live qty in the PDF (decision: keep the whole-unit floor?) |
| RC14 | The Customs Ledger PDF "CIF reconciliation PASS" is a tautology. `actual_debited = total − balance`, so it can never show CHECK. "Actual debited" also absorbs allotments and billed CIF. | every DFIA PDF | false assurance | Defect | Show real components and a real check (no rule change) |
| RC15 | Item Report Excel writes dates as ISO **text** (`_safe(isoformat)`), not DD-MM-YYYY date cells. It also sums group totals in `float` (`item_report.py:71-73`). | every export | presentation | Defect | Date cells + Decimal sums |
| RC16 | %-condition pools are **not enforced at allotment allocation**. The `project_effective_item_cif` cap replaces the pool cap (domain auditor, `allotment/api/views_actions.py:1361-1376`). | not measured | latent | **Rule conflict** | Owner decision **D-C** |

Top 10 CIF discrepancies (licence · item · metric · source → report): see `/tmp/recon_full2.json`. The largest are:
- 0811013826 RC12 (−77,746,799.19).
- 0811013826 item 28563 WHEAT GLUTEN RC4 (+76,838,632.07).
- 0310636996 RC11 (−21,251,787.50).
- 0310705160 RC11 (−19,563,358.47).
- 0310653755 item 32156 RC4 (+16,421,642.82).
- 0310776854 RC11.
- 0310653755 RC12 (−16,223,222.82).
- 0310664188 items 32041 and 32042 RC4 (+15,129,911.93 each).
- 0310835522 item 7214 SUGAR RC4 (stored 0 vs live 14,339,508.30, on a licence at −52.30).

The largest quantity discrepancies are stale stored allotted qty (RC3):
- 0310705160: 4,949,800 kg.
- 0310825235: 3,838,597 kg.
- 0310831630: 2,513,171 kg.

The affected licence register (2,071 licence numbers) is in `/tmp/affected.json`. The register with every licence, item,
HSN, metric, source, report and difference is in `/tmp/recon_full2.json` under `discrepancies`.

## 5. Excel / PDF

- **Item Report Excel:** built from the same `report_data` as the screen, so values match it. Numeric cells are numeric.
  Dates are text, and group sums are float (RC15).
- **Item Pivot Excel:** = screen with 0 diffs (verified 2026-11-20, E1 active scope). Not re-run here.
- **Customs Ledger PDF:**
  - Licence balance = `get_balance_cif` on 200/200 sampled licences.
  - Item debited qty: 0 diffs.
  - Item available qty: RC13.
  - Reconciliation flag: RC14.
  - Unit totals are keyed by raw unit text. No split occurred in the sample, but `KG`/`Kg` items would print separate
    totals.

## 6. Decisions needed before any correction

- **D-A.** Should item-attributed `available_value` apply only when `individual_item_cif_override` is True, and be capped
  at the licence balance? This affects RC4a and RC4b, the Item Report, `min_balance`, `sion_rule_engine`, and the
  allotment available-items list. Planning and the override-off allotment cap are already safe; the auditor verified this.
- **D-B.** In override mode, may allotment, BOE and trade caps (`calculate_item_balance`) exceed the licence balance?
- **D-C.** Restore %-pool enforcement at allotment allocation (RC16)?
- **D-D.** Which writer is canonical for the stored `available_value`: the signal or `update_balance_values`? Or should
  stored columns stop being displayed (RC3 and RC4b)?
- **D-E.** Should licences with a NULL purchase status appear in the pivot (RC7)?
- **D-F.** Quantity display precision: keep the legacy whole-unit floor, or use exact live qty everywhere (RC13 and RC3
  rounding)?
- **Approval only, no rule change:** RC11 and RC2 labels, RC14 real PDF check, RC15 Excel dates and Decimal sums.

## 7. Quality gates and reviews

See the session report (tracker checkpoint `cross-surface-reconciliation`).

## 8. Phase 8 — final reconciliation, independent review, gates (2026-11-20)

### 8.1 Audit completion (re-verified)
- `/tmp/recon_full2.json` + log: exit 0. Totals: 2,182 licences (2,185 minus 3 with no import items), 26,818 items,
  14,314 pivot cells, 4,831 discrepancies on 2,071 licences. Matches §1/§4. The JSON breakdown by metric is RC4 3,055 ·
  RC3 973 (balance_qty 726, allotted_qty 185, allotted_cif 35, debited_qty 15, debited_cif 11, balance_cif 1) ·
  RC11 632 · RC12 80 · RC7 69 · RC8 11 · RC2 11.
- The first run (`/tmp/recon_full.json`) labelled the 69 licences missing from the pivot as RC10. The second run
  correctly reclassifies them as RC7 (NULL `purchase_status`). Use `recon_full2.json` only.
- Read-only: `atomic()` + `set_rollback(True)`, with no cache, Celery or on_commit writes found (default DB only).

### 8.2 Independent financial-integrity review (Opus cif-balance-auditor, read-only) — verdict ESCALATE-TO-OWNER

| RC | Verdict | Class | Rule change? | Correction to §4 |
|---|---|---|---|---|
| RC4a | CONFIRMED | Canonical conflict (double counting vs licence ceiling) | **Yes, D-A** | `condition_pool.py:288`: no override check and no licence cap. Arrived in commit 7614a4ad, with no decision doc. |
| RC4b | PARTIAL | Staleness plus two-writer conflict | Depends on D-A/D-D | The "live" reference is itself the RC4a value, so the 1,712 rows mix defect and staleness. |
| RC3 | PARTIAL | Staleness plus definitional difference | API values change | Stored allotted *does* net BOE coverage (`calculate_balance.py:79`); rows are stale because nothing re-runs the writer on link changes. Stored debited includes hidden BOE + ARO (+ direct sale for qty), in float. All 11 debited_cif and 11/15 debited_qty hits are the RC8 hidden-BOE licences, so they are definitional. |
| RC2/RC8 | CONFIRMED | Legitimate, unlabelled | No | — |
| RC5 | CONFIRMED (0 locally) | Latent formula divergence | D-F | `balance_snapshot.py:196-205`: the docstring says "same formula", but the code floors and omits direct sale. |
| RC6, RC9, RC10 | CONFIRMED (0) | — | No | — |
| RC7 | CONFIRMED | Scope | D-E | `item_pivot_selection.py:31-39` always filters status; Item Report filters only when a status is given. |
| RC11 | CONFIRMED | Legitimate, unlabelled | Label only | `license_overview_items.py:102` |
| RC12 | CONFIRMED | Data issue | No; no auto-repair | Also feeds RC4a: any positive import `cif_fc` turns on attribution. |
| RC13 | CONFIRMED | Rounding | D-F | `calculate_balance.py:127` uses `round_down(…,0)` |
| RC14 | CONFIRMED (re-verified by hand) | Defect | No | `custom_ledger_pdf.py:93-99`: `total − (total − balance) − balance ≡ 0`, so it always shows PASS. |
| RC15 | CONFIRMED, wider than stated | Decimal-invariant defect | No | Floats run through the Item Report rows (`item_report.py:144,378-379,412,419-421,452`), not only the group sums. Dates are ISO text (`:439-441`). |
| RC16 | CONFIRMED | Canonical conflict | **Yes, D-C** | `views_actions.py:1364-1368` → `effective_cif_mode.py:94-98`: the %-pool value is computed and then ignored. |

**Audit-method defects (they change how the numbers should be read; they don't invalidate the register):**
1. **RC4a is undercounted.** It is only measured where live ≠ stored. Items where both exceed the licence balance are missed.
2. **The RC4a excess (502,991,936.21) is added up per item.** Each item's excess over the same licence ceiling is summed
   separately. This is not the combined overstatement per licence, so treat it as indicative.
3. **Mixed debited bases.** The Import Items tab debited is compared with raw BOE (`:303`), the Overview with
   allocation-aware debit (`:293`). They are equal locally (RC1 = 0).
4. **One RC3 hit is mislabelled.** The Import Items tab `balance_cif` is live `get_balance_cif` or the override sum, not a stored column.
5. **Item-level checks are compared as licence totals** (`:197-215`). ± item differences can cancel. The 641/85 split
   (genuine vs sub-1 kg) is per licence.

**New findings (not in §4):**
- **N1 (HIGH):** The Customs Ledger PDF item "Balance CIF" prints the RC4a value (`custom_ledger_pdf.py:90`). Its item
  "Debited CIF" includes hidden prior-owner BOEs and ARO, computed in float (`:77`).
- **N2 (MEDIUM):** The PDF "Total CIF" = `licence.opening_balance`, not `calculate_credit` (`:93`).
- **N3 (MEDIUM):** The "available_value never exceeds balance" guard never fires (`calculate_balance.py:217-221`).
  `balance_cif_fc` returns `available_value_calculated` (`models/items.py:212`), so it compares the value with itself.
  Re-verified by hand.
- **N4 (LOW):** PDF unit totals are keyed on raw unit text (`KG`/`Kg`/`kg` → separate totals).

### 8.3 Final acceptance (identical scope and filters)
- **Licence level (Total, Debited, Allotted, Billed, Balance, Planned CIF):** Licence Detail = Item Pivot = Item Report
  = Excel (built from the same data) = canonical. PDF licence balance = `get_balance_cif` on 200/200 sampled licences.
  **Met.**
- **Item level:** **not met.** The open items are RC3, RC4a/b, RC13, RC14, RC15 and N1–N4. Each is explained above.
  None was corrected, because RC4a, RC16, D-A … D-F need owner decisions and RC3/RC4b change API values.

### 8.4 Quality gates
- Targeted (this session, `TEST_DB_NAME=test_lmanagement_p8_targeted`): 16 files (canonical balance, ledger views,
  balance Excel, cross-surface recon, Excel cell types/formats, allotment xlsx, BOE export golden, date utils,
  Customs/financial ledger PDF, PDF live balance/callsites/endpoint/colours, CIF single source): **305 passed, exit 0**
  (`/tmp/smart-test/backend-20261120-140358.log`).
- Full `quality-gate.sh backend|frontend` and Playwright: **NOT RUN by this session.** Peer session `license-manager-d3`
  owns the in-flux pivot/Item Report files (an agent was editing `item_pivot_service.py`) and will run each gate once
  when that lands. See the tracker for the results.

### 8.5 Remaining risks / deferred
Owner decisions D-A … D-F (§6). RC4a and RC16 are BUSINESS-RULE matters. Approval is needed for RC3/RC4b (API
values change), the labels for RC2/RC11, the RC14 real check, the RC15 date cells and Decimal handling, and N1–N4.
RC12 (80 licences) goes to an owner data review. Migration 0067 is not applied (owner approval pending; not this
workstream).
