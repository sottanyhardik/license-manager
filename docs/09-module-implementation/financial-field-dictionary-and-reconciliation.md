# Financial Field Dictionary and CIF Reconciliation

Status: investigation complete for the licence list, planning budget and incentive ownership. No calculation or stored value was changed by this work. Decisions still needed are listed in §5.

Business rules this document applies:
- Original CIF = the CIF entitlement granted or endorsed on the import licence. It is not adjusted by purchase credits or trade debits.
- Utilised CIF = BOE CIF + ALLOTMENT CIF + BILLED CIF WITHOUT BOE. Available CIF = Original CIF − Utilised CIF.
- Negative values are shown, never clamped to zero.
- The D-1 engine `services/financial_position.py` stays separate and is not consumed by production.

## 1. Field dictionary

| Field | Where | Formula | Business meaning | Authoritative source | Consumers |
|---|---|---|---|---|---|
| `available_cif` (list) | `serializers/license.py` `get_available_cif` ← `canonical_available_map` ← `licence_balance_report.available_cif_by_licence` | Σ item `Available` = Original − (BOE uncovered + over-linked) − Allotted − Invoiced. Licence- or item-level CIF control. | **Available CIF, canonical.** | Canonical item calculation (`build_item_balance` → `compute_utilisation`) | Licence list card "Available Balance CIF"; Licence accordion (`LicenseAccordionList`) |
| `balance_cif` / `get_balance_cif` (list and detail) | `serializers/license.py` `get_balance_cif`, `_clamp` ← `live_balance_map` ← `LicenseBalanceCalculator.calculate_financial_balance_for_licenses` | Opening + Purchase CIF − Sale CIF − Unallocated BOE − Outstanding allotments. **Clamped: any value ≤ 0 becomes 0.00.** | **Legacy Financial Available Balance.** It includes purchase credit and trade debit adjustments, which the business definition excludes from Original CIF. Not a canonical available figure. | Legacy engine (`balance_calculator.py`) | Licence balance modal (`LicenseBalanceModal`); Invoices tab company balance (`InvoicesTab`); Planning editor fallback (`PlanningEditor`, see §2.3); Planning budget (`sion_planning_execution`, see §2.4); `sion_rule_engine`; `condition_pool`; Overview tab (already labelled "Legacy balance engine … Review required") |
| `legacy_balance_cif` (detail) | Licence detail reconciliation | Same as legacy `balance_cif` | Legacy engine value kept for comparison | Legacy engine | Reconciliation tab; Overview tab warning |
| `actual_balance_cif`, `final_balance_cif` | Planning operational position | Canonical available CIF before new planning; final after planning | Canonical available, as the planning summary card describes it | Canonical | Planning editor summary cards |
| `effective_license_balance_cif`, `license_balance_cif` | Planning group rows | From planning execution | Budget used for planning groups | Mixed; see §2.4 | Planning editor groups |
| `available_cif` (dashboard) | Dashboard payload | Dashboard aggregation | Portfolio available CIF | Dashboard aggregation; not re-verified | KPI row, financial overview |
| `balance_cif` (dashboard portfolio row) | Dashboard payload `LicencePortfolio` | Dashboard aggregation | Per-licence balance in dashboard | Not re-verified | Dashboard licence portfolio table |
| `sold_value`, `balance_value`, `sold_status` (incentive) | `IncentiveLicense` cache written by `update_sold_status` | sold = Σ SALE trade lines not linked; balance = licence value − sold; status from `derive_sold_status` | Incentive sold and availability | SALE trade lines (`SALE_LINE_FILTERS`) | Incentive list, filter, status badges |

## 2. CIF reconciliation: every discrepancy found

### 2.1 Canonical vs legacy on the licence list (page 1, 48 licences, measured in browser)

- 9 licences have negative canonical `available_cif`. **All 9 have a positive legacy `balance_cif`.** Example 0811016774: canonical −461,464.94, legacy 323,386.15.
- 28 licences agree between the two.
- 11 licences show positive canonical values that differ from their legacy values.

Cause: the two engines use different scopes. The legacy engine adds purchase credit and subtracts trade debit at the licence level, while the canonical engine works per item from BOE, allotment and invoice records. Neither engine is mis-computed by itself. They answer different questions and must not be presented as the same figure.

### 2.2 `_clamp` in the list serializer (P1, rule breach)

`serializers/license.py` `_clamp` returns 0.00 for any `balance_cif` ≤ 0. Negative legacy values are therefore hidden as zero. This breaches the "never clamp a negative" rule. The current list data is unaffected because no legacy value is negative on page 1, but the rule is breached by design.

### 2.3 P0-A — Planning editor falls back to the legacy balance

`components/planning/PlanningEditor.tsx` sets the pool balance to the canonical value when the parent supplies it, and otherwise to `license.balance_cif` (legacy). A missing canonical value therefore presents a legacy number as the planning balance. This directly breaches the rule "never present a contradictory legacy value as available CIF".

### 2.4 P0-B — Planning budget is the legacy balance

`sion_planning_execution.py` (around lines 383–420 and 1600–1640):

- `live_balances` is the legacy financial balance. It is the planning budget (`effective_planning_balance_cif`).
- The new-plan ceiling is `min(effective legacy balance, reconciled ceiling)`. The reconciled ceiling is built from BOE and unlinked-allotment usage only. **It does not subtract billed-without-BOE sales.**
- The over-utilisation block fires only when the legacy raw balance is negative, or when the reconciled ceiling is negative.

Consequence: a licence that is over-utilised by sales, where the canonical available is negative, can still receive a positive planning budget if its legacy balance is positive. The 9 page-1 licences in §2.1 are the affected population. I have not counted how many would be blocked by a canonical cap, because doing so requires running the planning engine.

This file has uncommitted changes from you (`git diff --stat`: 38 insertions, 1 deletion). I have not edited it.

### 2.5 Dashboard fields not re-verified

`dashboard_summary.py`, `KpiRow`, `LicencePortfolio` and `payloadContract.ts` use `available_cif` and `balance_cif` from the dashboard payload. I did not trace their source to the canonical or legacy engine in this session. This is an open item.

## 3. Incentive ownership and availability (P0, confirmed)

Read-only reconciliation (`reconcile_incentive_license_status` dry run, report at `/tmp/lm-incentive-recon/…csv`, not in the repository):

| Category | Count | Licences | Meaning | Proposed action |
|---|---:|---|---|---|
| CORRECTABLE, sold shown as Available | 7 | 1, 2, 3, 4, 5, 7, 8 | Live SALE lines sum to the full licence value, but the cache says unsold (`NO` → **Available**) | `--apply` (needs authorisation) |
| CORRECTABLE, double-counted cache | 3 | 6, 15, 16 | Cache sold is roughly double the live sum, balance negative | `--apply` (needs authorisation) |
| OVERSOLD | 1 | 135 | SALE lines (237,549) exceed licence value (67,267). Status YES, balance −170,282 | Manual review: verify sale amount or licence value |
| NO_SALE_EVIDENCE | 3 | 198, 256, 269 | Cache says fully sold (`YES`), but no SALE line supports it | Manual review: may be a sale now excluded as a linked trade |
| DATA_QUALITY | 5 | 124–128 | Duplicate identical purchase lines on one trade | Report only; does not change sold status |

Verified facts:
- `derive_sold_status` and the cache writer agree with each other and with the serializer. The gap is staleness, not a rule conflict.
- Sold-but-Available is a backend cache problem, and the frontend fallback fix cannot correct it. The label shows whatever `sold_status` the API returns.
- The reconcile command is dry-run by default and writes only derived fields. It writes a backup JSON when applied. It is still a database write, so it needs your authorisation.

Unresolved: the root cause of the stale caches. The current signals do not fire on every write path (see the comment in `trade/models.py`). I have not identified which path wrote licences 1–8 without updating the cache.

## 4. Other module evidence

- **Licence ledger:** all three endpoints return 200. `summary` takes about 940 ms, `companies` about 26 ms, `license-wise` about 1,090 ms with a **495 KB** payload. The "pending" state seen earlier was a capture-timing artefact, not a backend fault. Performance item: the license-wise payload is large.
- **Ledger upload:** still accepts CSV and HTM/HTML only. Excel (`.xlsx`/`.xls`) is not implemented.
- **Planning:** dashboard and SION classes return 200 without console errors. The planning rule engine and item mappings have not been audited in this session.

## 5. Decisions needed from you

1. **Authorise `reconcile_incentive_license_status --apply`** for the 10 CORRECTABLE licences. The database is local, but I have not confirmed it is non-production. This changes sold and status cache values only, and it fixes the 7 sold-shown-as-Available licences.
2. **Planning budget cap (P0-B):** should planning cap every licence's budget at the canonical available CIF, and block when canonical is negative? This makes planning more conservative and changes plan outcomes for the affected licences. I can implement it once you confirm.
3. **Planning fallback (P0-A):** when the canonical value is missing, should the planning editor show "Not computed" and block, rather than use the legacy value?
4. **Legacy `balance_cif`:** relabel it as "Legacy adjusted balance (purchase/trade)" everywhere it is shown, and remove the `_clamp`? Removing the clamp changes displayed values for negative legacy results.
5. **Manual review items:** licence 135 (oversold) and licences 198, 256, 269 (sold with no sale evidence). Who decides these?

## 6. Not yet started in this session

- Ledger Upload Excel support.
- Planning Workbench action simplification.
- Shared UI/UX components and filter architecture.
- Performance work on the license-wise ledger payload.

Repository state: nothing committed. No existing uncommitted change was modified. The only file written is this document.
