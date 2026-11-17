# 09 - Licence register and expanded workspace: backend performance audit

Read-only measurement. No source edits. Scripts live outside the repo in `/tmp/perf09/`.

## Method

- DB: clone `lmanagement_restore_verify_live_20261116` (settings NAME asserted equal before any request; `SET TRANSACTION READ ONLY`, rolled back). 222 licences, 102 live (not expired).
- Client: DRF `APIClient` + `force_authenticate(superuser)`, in-process (no network, no gunicorn, no Redis round trip beyond what the code does). Django `CaptureQueriesContext`. 1 warm-up request, then median of 3.
- `ms` = wall time of the in-process request. `db ms` = sum of per-query driver time. EXPLAIN ANALYZE was run on the clone only (SELECTs, inside a read-only transaction).
- Caveat: local numbers exclude network, JSON transfer and browser time. Relative ranking is reliable; absolute numbers will differ on the server.

## Which endpoints the UI calls (verified in frontend)

| UI moment | Request |
|---|---|
| Register page | `GET licenses/?flags__is_null=False&is_expired=False&page=1&purchase_status=...` (`api/licenseApi.ts`) |
| Card expand (default Overview tab) | `GET licenses/:id/balance-ledger/` only (`features/licenses/useLicenceLedger.ts`; shared by financial summary, Overview ledger section, Reconciliation tab, and the workspace's `has_trading_activity` gate) |
| Import Items tab | `overview-items/` |
| BOE and Allotment tab | `overview-boes/`, `overview-allotments/` |
| Invoices tab | `overview-invoice-ledger/` |
| History tab (first visit) | `license-actions/:id/ownership-data/` |
| Planning tab | `plan-utilization/` (not in the brief list; not measured), `replan-status/` (via `ReplanStatus.tsx`) |
| Standalone `/licenses/:id/overview` page (not the register) | `overview-summary/` + `balance-ledger/` |

`licenses/:id/` (detail) is not called by the register or workspace. I measured it anyway because it was requested.

## Representative licences (clone)

| Role | id / number | import items | BOEs | trade lines | balance CIF |
|---|---|---|---|---|---|
| small | 2453 / 0811016786 | 1 | 1 | 4 | 43,756.91 |
| large (most items) | 2532 / 0311051387 | 35 | 3 | 2 | 0.00 |
| many BOEs | 2586 / 0311054431 | 5 | 21 | 12 | 79,964.69 |
| traded (most trade lines) | 2537 / 0311049077 | 4 | 14 | 18 | 144,728.24 |
| negative | NONE | - | - | - | The clone has no licence with `license_licensebalance.balance_cif < 0`. Not measurable; do not infer. |

## 1. The list

`GET licenses/?flags__is_null=False&is_expired=False&page=1` (+ `purchase_status`), 25 rows per page.

| Variant | queries | ms | bytes |
|---|---|---|---|
| no purchase_status | 34 | 153 | 184,486 |
| purchase_status=1..8 | 34 | 141 | 218,859 |
| purchase_status=1 | 34 | 129 | 241,586 |

- Query count is constant (34): page balances already go through the batch `LicenseBalanceCalculator.calculate_balance_for_licenses` (`paginate_queryset` stashes the page ids). No N+1 here.
- Top queries: main list query 38.6 ms (`license.py:302`; EXPLAIN: Planning 37.4 ms, Execution 0.92 ms, 503 buffer hits, 25 rows). `balance_calculator.py:708` 3.9 ms (Execution 1.4 ms, 1008 buffer hits); `:613` 2.5 ms (Execution 0.9 ms).
- Finding: the list's biggest cost is query PLANNING (37 ms) for a SELECT DISTINCT with many joins and filters, not execution (under 1 ms). Indexes will not help; reducing join and filter complexity or using prepared plans would.
- Payload note: 7.4-9.7 KB per row. The page is paginated, so this is acceptable, but it is the largest payload on the register.

## 2. Expand default: balance-ledger vs overview-items (median of 3)

| Licence | balance-ledger q / ms / bytes | overview-items q / ms / bytes | ratio (ms) |
|---|---|---|---|
| small 2453 | 157 / 129 / 8,421 | 3 / 12 / 241 | 10.8x |
| large 2532 | 85 / 109 / 5,748 | 3 / 13 / 7,579 | 8.4x |
| many BOEs 2586 | 460 / 367 / 45,640 | 3 / 13 / 1,317 | 28x |
| traded 2537 | 451 / 394 / 45,714 | 3 / 12 / 1,042 | 33x |

Verdict: the switch is a latency regression on the first paint of every expanded card (109-394 ms and 85-460 queries, against 12-13 ms and 3 queries), and it scales with BOE and trade count. It is not a like-for-like swap, though: balance-ledger returns the financial summary, financial ledger and reconciliation that overview-items never carried. The items rows are still fetched separately when the Import Items tab opens.

Cost grows with BOEs and trades, not with items: licence 2532 has 35 items and is the cheapest.

### N+1 signatures in balance-ledger (many-BOEs licence 2586: 460 queries, 221 ms DB)

| Calls | Time | Call site | Template |
|---|---|---|---|
| x48 | 48.6 ms | `reconciliation/services/boe_link_reconciler.py:68` | per-trade-line `RowDetails` candidate query (`annotate_and_exclude_hidden(...).select_related`), then `remaining_for_row_details_invoice_side` per row |
| x120 | 20.1 ms | `reconciliation/services/allocation_service.py:56` | `SUM(InvoiceBOEAllocation.allocated_*)` per row_details |
| x78 | 12.7 ms | `allocation_service.py:134` | `SUM(ExternalInvoiceLink.qty/cif_*)` per row_details |
| x20 | 10.3 ms | `license_balance_ledger_builder.py:1183` | `BOEAllotmentAllocation.filter(row_details=row)` per BOE row (plus a per-row `remaining_for_row_details_allotment_side`) |
| x7 | 11.2 ms | `balance_calculator.py:184` | `SELECT DISTINCT trade ...` (repeated trade lookups) |

On small licence 2453 the same pattern appears: 12 x `RowDetails` select, 11 x `InvoiceBOEAllocation` SUM, 9 x `ImportItems` select, 7 x `DISTINCT license_id, bill_of_entry_id`.

Top 3 slow single queries in balance-ledger (2586), with EXPLAIN ANALYZE:
1. `LicenseDetailsViewSet.get_object()` (`license.py:526`) 22 ms in this run. EXPLAIN: Planning 22.7 ms, Execution 0.33 ms. Cost is planning.
2. `SELECT DISTINCT trade_licensetrade ...` (`balance_calculator.py:184`) 7.2 ms. Planning 2.1 ms, Execution 0.23 ms, 147 buffer hits.
3. Second `DISTINCT trade_licensetrade` 3.9 ms. Planning 1.6 ms, Execution 0.15 ms.

Conclusion: no individual query is slow on the server side (all execute in under 1 ms). The cost is round trips: about 0.4-0.5 ms per query across 460 queries, plus ORM and Python overhead (221 ms of 367 ms is DB driver time, the remaining 146 ms is Python assembly). The fix is batching, not indexing.

## 3. Per-tab endpoints (median of 3; queries / ms / bytes)

| Endpoint | small 2453 | large 2532 | many BOEs 2586 | traded 2537 |
|---|---|---|---|---|
| overview-items | 3 / 12 / 241 | 3 / 13 / 7,579 | 3 / 13 / 1,317 | 3 / 12 / 1,042 |
| overview-boes | 4 / 14 / 223 | 3 / 13 / 2 | 4 / 16 / 4,607 | 4 / 15 / 3,080 |
| overview-allotments | 5 / 13 / 153 | 3 / 11 / 2 | 5 / 14 / 167 | 5 / 14 / 179 |
| overview-invoice-ledger | 13 / 19 / 795 | 9 / 15 / 472 | 29 / 24 / 2,161 | 41 / 27 / 3,202 |
| overview-summary | 55 / 50 / 601 | 47 / 47 / 608 | 55 / 58 / 627 | 55 / 53 / 621 |
| replan-status | 3 / 2 / 397 | 3 / 2 / 386 | 3 / 3 / 391 | 3 / 3 / 391 |
| ownership-data | 2 / 2 / 333 | 2 / 3 / 228 | 2 / 3 / 285 | 2 / 3 / 333 |
| licenses/:id/ (detail) | 132 / 106 / 6,128 | 209 / 143 / 78,071 | 144 / 142 / 28,409 | 141 / 140 / 13,384 |

Notes per endpoint:
- overview-items, overview-boes, overview-allotments, replan-status, ownership-data: already O(1) queries. Nothing to fix. About 8 ms of each 12-16 ms is the shared `get_object()` (see below).
- overview-invoice-ledger: N+1. 1 `SUM(LicenseTradePayment.amount)` per trade (`trade/models.py:353`): x8, x24, x24+ for 2453/2586/2537 (41 queries for 2537). Each is 0.1 ms; the whole endpoint stays under 30 ms.
- overview-summary: 47-55 queries, 50-58 ms. Already a batch design (`balance_snapshot` → `*_for_licenses` methods called with a single id), but each batch method runs 2-5 times (`balance_calculator.py:613` x5, `:1262` x5, `:1312` x3, `:708` x2, `:184` x2). Execution per query is about 0.6-1.6 ms.
- licenses/:id/ (detail): 132-209 queries, 106-143 ms, 78 KB for licence 2532. Not called by the register or workspace, so it is not on the page's critical path.

### Shared per-request tax: `LicenseDetailsViewSet.get_object()`

Every per-licence request pays it. `license.py:526` runs a `SELECT DISTINCT` with many joins: Planning 7.6-22.7 ms, Execution 0.17-0.33 ms (EXPLAIN ANALYZE on 2586: 8.2 ms measured, 0.17 ms execution). That is about 65% of the wall time of overview-items (8 of 12 ms), overview-boes and the other light endpoints.

## 4. Overview tab: could it load a lighter source than balance-ledger?

`overview-summary` exists and is much lighter (47-58 ms / 47-55 queries vs 109-394 ms / 85-460 queries). But field parity does NOT hold:

- The register's financial summary (`financialSummaryFields.ts`) reads `customs_ledger.summary`: `opening_balance`, `total_boe_cif`, `remaining_after_boe`, `total_pending_allotment_cif`, `computed_balance`, `difference`.
- `overview-summary` returns `summary.{total_boes, total_allotments, total_planned_cif, total_cif, total_debited_cif, total_allotted_cif, total_balance_cif}` plus header fields (status, importer, purchase status, port).
- There is no field in the response for `remaining_after_boe` or `difference`. `total_cif`, `total_debited_cif` and `total_balance_cif` are conceptually close to `opening_balance`, `total_boe_cif` and `computed_balance`, but they come from a different engine (`balance_snapshot`, quantized differently, with its own virtual `trade.boes` netting). Mapping one to the other would change displayed numbers.
- The Overview tab also needs `financial_ledger.rows` and `summary.has_trading_activity` / `missing_purchase_warning`, which only balance-ledger provides. The Reconciliation tab gate needs `has_trading_activity` at the workspace level.

Recommendation: do NOT swap the Overview tab to `overview-summary` (BUSINESS-RULE: figure parity would need cif-balance-auditor sign-off). Instead make balance-ledger itself cheaper (section 5, A1-A3). If a lighter source is wanted for the collapsed card header alone, that needs a new endpoint or a new `?sections=` option on balance-ledger (API CONTRACT CHANGE, needs owner approval). Not proposed as safe.

## 5. Safe optimisations (ranked by evidence and gain)

Gains are estimates from the measured per-query round-trip cost (about 0.4-0.5 ms) and call counts. None has been implemented or re-measured.

| # | Change | Evidence | Expected gain | Flags |
|---|---|---|---|---|
| A1 | Batch `remaining_for_row_details_invoice_side/allotment_side` for a set of row ids: one grouped `SUM` for `InvoiceBOEAllocation` and one for `ExternalInvoiceLink`, keyed by `row_details_id`; use it in `boe_link_reconciler.py:68` candidates and `license_balance_ledger_builder.py:1183`. There is already a precedent for batching in this module (`boe_invoice_allocation_map`, `boe_external_invoice_map`). | 120 + 78 + 20 per-row queries on 2586 (about 43 ms DB, more in Python overhead) | 2586 / 2537: roughly 200 of 460 queries removed; 367 → about 200-230 ms estimated. | BUSINESS-RULE: touches remaining-balance math (`_floor0`, tolerance). `cif-balance-auditor` required. Output must be byte-identical (Decimal). |
| A2 | `boe_link_reconciler` candidate query: fetch candidate `RowDetails` for all sale trade lines of the licence in one query (`trade_line__in`), group in Python, instead of one query per trade line (x48 for 2586). | 48.6 ms, 48 calls | about 40 ms off; 48 → 1-2 queries | BUSINESS-RULE (invoice to BOE matching eligibility). `cif-balance-auditor` required. |
| A3 | Per-BOE `BOEAllotmentAllocation.filter(row_details=row)` (builder:1183): replace with one `row_details__in` query plus `select_related`, grouped by row id (x20) | 10.3 ms, 20 calls | about 8 ms; 20 → 1 | Not balance math by itself (grouping only), but sits next to `remaining_for_row_details_allotment_side`. Reviewer should check; auditor if combined with A1. |
| A4 | `overview-invoice-ledger`: replace per-trade `SUM(LicenseTradePayment.amount)` (`trade/models.py:353`) with an annotated `Sum` or `prefetch_related('payments')` summed in Python | x8 / x24 / x24+ calls (13-41 queries; 2537: 41) | 41 → about 12 queries on the worst licence; saves 5-10 ms | Display-only totals; verify Decimal equality. Does the trade model's property get used elsewhere? Yes: keep the property and add a prefetch-aware path. |
| A5 | `get_object()` for the read-only overview actions: swap `SELECT DISTINCT ... many joins` for a lean permission-scoped lookup (`pk` + company filter, no joins/DISTINCT), keeping the same visibility rule | Planning 7.6-22.7 ms vs Execution under 0.4 ms per request; every tab, every expand pays it | About 7-20 ms per request (about 60% of the 12 ms light endpoints; 2 x 8 ms on the expand path) | PERMISSIONS: must keep identical queryset scoping (company/role); flagged for `code-reviewer`/`security-auditor`. Not balance math. |
| A6 | `overview-summary`: its batch methods are called 2-5 times each (`:613` x5, `:1262` x5, `:1312` x3). Share one snapshot per request | 55 queries, 50-58 ms | 55 → about 25 queries; about 20 ms | BUSINESS-RULE (snapshot). `cif-balance-auditor` required. Low priority: the register no longer calls this endpoint. |
| A7 | List: reduce planning cost of the main list query (38 ms planning vs 1 ms execution), for example by dropping unneeded joins/`DISTINCT` where the filter does not fan out | Planning Time 37.4 ms vs Execution 0.92 ms | up to about 30 ms of 129-153 ms | API CONTRACT/semantics risk: DISTINCT guards against fan-out from `flags`/M2M filters. Needs a count-parity test before and after. |

Frontend note (no change proposed, outside the brief): the expanded card issues the heavy balance-ledger request even if the user only wants to look at the header, and the workspace adds a second consumer of the same cache key (no duplicate request, confirmed by shared `licenseBalanceKeys.ledger(id)`).

## 6. Indexes

NEEDS APPROVAL (migration) - none proposed. EXPLAIN ANALYZE shows execution under 1.4 ms on every query examined, with at most about 1000 buffer hits; the cost is planning and round trips. No index would measurably help, so none is recommended.

## 7. Risks and what was not measured

- No negative-balance licence exists in the clone; negative-path behaviour (e.g. `max(balance, 0)` clamps) was not exercised.
- Some licences' balance-ledger output may be Redis- or snapshot-cached in production; local run did not use a warm production cache. If `balance_snapshot` is cached in prod, overview-summary will look cheaper there.
- `plan-utilization/` (Planning tab) and `licenses/:id/import-items` were not in the brief and are unmeasured.
- Timings are in-process on a local clone. Server numbers will include gunicorn, network and DB latency; per-query round trip cost on a remote DB makes A1-A3 worth MORE than shown (460 queries x network RTT).
- All A1/A2/A6 items touch CIF/balance/BOE reconciliation math. Do not implement without `cif-balance-auditor` review and before/after byte-equality checks of the balance-ledger response for these 4 licences on the clone.
