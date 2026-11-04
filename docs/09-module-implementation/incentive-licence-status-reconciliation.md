# Incentive Licence Sold / Available Status — Reconciliation (2026-11)

## 1. Summary

A licence shown as **Available** despite a completed sale (licence `2512026163`, RODTEP, ₹7,68,600) was caused by a stale denormalised cache, not by a wrong rule. The sale line was present and counted correctly by the rule; the cached `sold_value` / `balance_value` / `sold_status` on the licence were out of date. The cache was refreshed by three defective paths, all now fixed:

| Defect | Effect | Fix |
|---|---|---|
| Recalculation in `pre_delete` | The deleted line stayed in the total → over-counted sold value | `post_delete` (also covers cascades from a deleted trade) |
| Read-then-write with no lock | Concurrent sales lost updates (two 500s left 500 PARTIAL) | Row-locked canonical writer `update_sold_status()` |
| `save()` wrote in-memory sold fields | A stale instance overwrote the sale cache | `save()` recalculates from lines; never trusts the instance |
| `link_trades` used queryset `.update()` | Linking/unlinking/deleting a partner left the cache stale | Explicit recalculation of affected licences |
| Trade-line vs trade-header lock order differed | Deadlock risk between concurrent edits | Trade row locked first on both paths; licence rows locked in pk order |
| Admin could edit derived cache fields | Edits silently overwritten | `readonly_fields` for the three cache fields |

## 2. Source of truth

A **sale** is an `IncentiveTradeLine` on a trade with `direction = 'SALE'` and `linked_trade IS NULL` (`SALE_LINE_FILTERS`, `apps/license/services/license_profit.py`, the same rule the canonical ledger uses for DFIA).

- `sold_value` = Σ `license_value` of those lines.
- `balance_value` = `license_value − sold_value` (negative when over-sold, never clamped).
- `sold_status` = `NO` if sold = 0; `YES` if balance ≤ 0; otherwise `PARTIAL` (`derive_sold_status`).
- PURCHASE lines never change status.
- The three stored fields are a cache of that rule. The cache is written by one function, `IncentiveLicense.update_sold_status()`, and every write path calls it.

There is no draft or cancelled state on `LicenseTrade`. Cancelling a sale means deleting its trade, which the recalculation handles.

## 3. Verification of the confirmed example

Licence `2512026163` (id 1):
- PURCHASE trade 87 (`SUP/25-26/166DOM`, 867→766) carries a line of 768,600.00.
- SALE trade 89 (`LML/2025-26/0094`, 766→53) carries a line of 768,600.00, `linked_trade` null.
- Before repair: `sold_value` 0.00, `balance_value` 0.00, `sold_status` NO (Available).
- After: `sold_value` 768,600.00, `balance_value` 0.00, `sold_status` YES (Sold).

## 4. Scan results

Scanned **289** incentive licences (all, not one page). Independent SQL cross-check run before and after.

| Category | Count | Licences |
|---|---|---|
| Status wrong: stored NO, full SALE line exists (corrected) | 7 | 2512026163, 2512026162, 2512026161, 2512026158, 2512026160, 2510033793, 2511042684 |
| Cache wrong, status right: over-counted sold/balance (corrected) | 3 | 2512015763, 2601000178, 2601000174 |
| Status wrong: stored YES, no SALE evidence — **manual review** | 3 | 2606032604, 2601010350, 26041106287 |
| Over-sold: SALE line exceeds licence value — **manual review** | 1 | 2508027520 |
| Data quality: duplicate PURCHASE lines (no status effect) — report only | 5 groups | 2501001780, 2501005643, 2507058571, 2507035359, 2411073555 |

Ten records were corrected in total:
- **5 by the reconciliation command**, with a JSON before-state backup: `backend/reports/incentive_status_backup_20261103_155718.json` (ids 6, 7, 8, 15, 16).
- **5 by the live application**, during a trade edit at 21:10:44 IST (ids 1–5). That edit re-saved the lines, and the new post-save hook recalculated the licences. No backup was taken for these five; their before-state is the 15:39 dry-run snapshot (sold 0, balance 0, NO).

Post-repair independent SQL over all 289 licences: 286 match the rule exactly. The 3 remaining mismatches are the no-evidence rows, which are deliberately untouched. A second `--apply` run applied 0 corrections (idempotent).

## 5. Licence-wise reconciliation

| # | Licence | Licence value | Stored before (sold / balance / status) | Linked SALE evidence | Expected | Action |
|---|---|---|---|---|---|---|
| 1 | 2512026163 | 768,600.00 | 0 / 0 / NO | trade 89 line 768,600 | Sold | Corrected (live hook) |
| 2 | 2512026162 | 26,399.00 | 0 / 0 / NO | trade 89 line 26,399 | Sold | Corrected (live hook) |
| 3 | 2512026161 | 109,204.00 | 0 / 0 / NO | trade 89 line 109,204 | Sold | Corrected (live hook) |
| 4 | 2512026158 | 5,024.00 | 0 / 0 / NO | trade 89 line 5,024 | Sold | Corrected (live hook) |
| 5 | 2512026160 | 50,585.00 | 0 / 0 / NO | trade 89 line 50,585 | Sold | Corrected (live hook) |
| 6 | 2512015763 | 1,012,518.00 | 2,025,036 / −1,012,518 / YES | trade 81 line 1,012,518 | Sold, sold = 1,012,518 | Corrected (command) |
| 7 | 2510033793 | 77,263.00 | 77,263 / 0 / NO | trade 81 line 77,263 | Sold | Corrected (command) |
| 8 | 2511042684 | 72,110.00 | 72,110 / 0 / NO | trade 81 line 72,110 | Sold | Corrected (command) |
| 15 | 2601000178 | 1,742,139.00 | 3,372,319 / −1,630,180 / YES | trade 135 line 1,742,139 | Sold, sold = 1,742,139 | Corrected (command) |
| 16 | 2601000174 | 1,046,901.00 | 2,093,802 / −1,046,901 / YES | trade 135 line 1,046,901 | Sold, sold = 1,046,901 | Corrected (command) |
| 135 | 2508027520 | 67,267.00 | 237,549 / −170,282 / YES | trade 289 line 237,549 | YES, but over-sold | **Manual review** — sale amount or licence value wrong |
| 198 | 2606032604 | 2,460,307.01 | 2,460,307.01 / 0 / YES | none | Unsupported; rule gives Available | **Manual review** — not zeroed without evidence |
| 256 | 2601010350 | 909,129.00 | 909,129 / 0 / YES | none | Unsupported; rule gives Available | **Manual review** |
| 269 | 26041106287 | 11,688.00 | 11,688 / 0 / YES | none | Unsupported; rule gives Available | **Manual review** |

Duplicate PURCHASE lines on trade 335 (invoice `20252026/1142`) affect purchase totals, not sold status. Report only.

## 6. Open business decisions (not changed)

1. **Counterpart pairs (M3).** The rule excludes `linked_trade` but not `counterpart`. The DFIA balance excludes both (`balance_calculator.py`). The incentive copy path creates a same-licence PURCHASE leg. No incentive trade has a counterpart today, so this has no current effect. Decide whether counterpart pairs should net out.
2. **Two balance definitions (M4).** The list cache is `license_value − Σ SALE`. The canonical ledger's incentive summary uses `total_purchase − total_sale` as the INR balance. They diverge for licences that have purchase lines. The ledger's figure is not used for status. Decide which balance is the business balance, or label the other metric.
3. **Linking changes the status (H1).** Under the current rule, linking a sale to a partner removes it from sold status. That is how the rule is written, but it may not be the intended behaviour. It is the same decision as item 1.
4. **Over-sold licence 2508027520.** Confirm whether the SALE line should be 67,267 or whether the licence value is understated.
5. **No-evidence rows 198, 256, 269.** Confirm whether these sales happened outside the trade model. If so, record the trade evidence. If not, the cached YES is wrong and should be corrected deliberately.

## 7. Tests

Run with `TEST_DB_NAME=test_lmanagement_incentive_audit`, `--no-cov`:

- Incentive status, list filter, serializer, export, command, link/delete/admin suites: **51 passed**.
- Trade suite and related ledger suites: **129 passed**.

Not verified:
- Lock-order and concurrency fixes are exercised by one barrier-synchronised test. They are not proven free of deadlock under production load.
- Frontend typecheck, lint and build were not run; no frontend source changed.
- The `reports/` output files are not in git.

## 8. Files changed

- `backend/apps/license/models/core.py`: `derive_sold_status`, canonical locked `update_sold_status`, `save()` recalculates, `admin_readonly_fields`.
- `backend/apps/trade/models.py`: signal receivers (pre_save / post_save / post_delete on lines, post_save on trade, pre/post_delete on trade for partner propagation), trade-row lock ordering, `recalculate_incentive_licences_for_trades`.
- `backend/apps/trade/services/trade_service.py`: `link_trades` recalculates affected licences in one transaction.
- `backend/apps/license/serializers/incentive.py`: `get_sold_status` delegates to `derive_sold_status`.
- `backend/apps/license/admin.py`: reads `admin_readonly_fields`.
- `backend/apps/license/management/commands/reconcile_incentive_license_status.py` (new).
- Tests (new): `test_incentive_sold_status_reconciliation.py`, `test_incentive_status_reconciliation_command.py`, `test_incentive_status_export_consistency.py`, `test_incentive_status_link_delete_admin.py`.
- Test fixture changed: `test_incentive_license_list_filters.py` (sold status now comes from SALE lines).

No migrations. No trade lines, amounts or licence values were modified. Nothing committed or pushed.
