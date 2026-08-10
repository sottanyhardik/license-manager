# License Ledger Detail — Display Dataset Migration Design (Phase 3)

**Status:** Design only. No code changes made. Do not implement until this
document is explicitly approved and every Category B item in §10 has a
recorded business decision.
**Prerequisite:** the Display Dataset Rule (`docs/02-architecture.md`,
"Report & Export Architecture") and the completed Item Pivot migration
(Phases 2A–2B.2B, `ITEM_PIVOT_DISPLAY_DATASET_DESIGN.md`,
`ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md`, `MODERNIZATION_RETROSPECTIVE.md`).
**Verification:** all file:line citations were read at current HEAD
(`b32b2f75`, `feature/V2`) during this session, including two independent
read-only investigations of the scope boundary and the test surface.
**Detail:** the full value-by-value table lives in
`LEDGER_DETAIL_CALCULATION_INVENTORY.md`; risk ratings in
`LEDGER_DETAIL_RISK_ANALYSIS.md`; sequencing in
`LEDGER_DETAIL_MIGRATION_PLAN.md`.

---

## 0. Executive Summary

License Ledger Detail is a **worse** Display Dataset violation than Item
Pivot Report was, in a specific and important way: Item Pivot's problem was
a *coverage gap* (the frontend computed something the backend never had).
Here, the backend **already computes** a per-transaction running `balance`
and returns it on every row — and the feature's own page, PDF, and Excel
**all ignore it and compute a different number instead.**

Five findings, in order of severity.

1. **The backend's `balance` field has exactly one reader in the entire
   application, and it is not this feature.** `LicensesTable.tsx:616`
   (the Licenses master table's Transactions tab) renders `txn.balance`
   verbatim. `LicenseLedgerDetail.tsx`, `buildPdfBody`, and `generateExcel`
   never read it — each runs its own `running +=/-=` loop
   (`LicenseLedgerDetail.tsx:339-348`, `ledgerExport.js:185-191`,
   `ledgerExport.js:730-740`). **The same license's Balance column shows
   different numbers on two screens of the same app today.** This is a live
   user-visible defect under the standard set by `docs/02-architecture.md`
   ("A number that differs between the screen, PDF, Excel, print preview, or
   API response for the same report and the same filters is a defect"), not
   a divergence risk.

2. **The divergence is semantic, not accidental — which makes it a business
   question, not a cleanup.** The backend's `balance` is a *license-wide*
   running balance in purchase-first-then-date order
   (`ledger_pdf.py:1067, 1127, 1188, 1212`) that treats `COMMISSION_SALE` as
   a debit. The three client copies compute a *per-company* running balance
   that restarts at zero for each company group, iterates in
   `OPENING→PURCHASE→SALE` type order with no date component
   (`LicenseLedgerDetail.tsx:331-337`, `ledgerExport.js:118-119`), and treats
   `COMMISSION` rows as contributing nothing. **These are two legitimate,
   different ledger conventions.** You cannot pick one by inspection; §10 B2
   is a gate, not a preference.

3. **The prior hypothesis that the inline loop exists because the backend's
   `balance` was wrong does not survive reading the code.** The
   *"fixes the '–' bug"* comment (`ledgerExport.js:164-168`, `:722-729`)
   documents a removed helper, `computeBalanceMap`, that keyed a `Map` by
   transaction **object reference** while `groupByCompany` re-normalised into
   fresh objects — so every lookup missed and the Balance column silently
   rendered `'-'`. A client-side object-identity bug, regression-tested at
   `ledgerExport.test.ts:122`. `computeBalanceMap` no longer exists anywhere
   in `frontend/src`. This is Category A: the comment is accurate and
   self-contained, and it does **not** implicate the backend. Finding 2
   stands on its own.

4. **Three unreconciled definitions of P/L ship in the same PDF.** The
   backend's per-`SALE` weighted-average-cost margin
   (`ledger_pdf.py:1216-1225`) is displayed per row but never totalled. The
   per-company ledger total row uses `totalCredit − totalDebit` over **all**
   rows including commissions (`ledgerExport.js:227`). The summary page uses
   `SALE credit − (PURCHASE|OPENING) debit`, **excluding** commissions
   (`ledgerExport.js:319`). Pages 1 and 2 of one downloaded file can disagree
   by exactly the commission amount.

5. **There is effectively zero test coverage to migrate against.**
   `build_dfia_ledger_detail` and `build_incentive_ledger_detail` (~425 lines
   of balance logic combined) have **no tests at all**. The one test that
   looks like endpoint coverage — `backend/tests/test_api_trade.py:91`
   `test_license_ledger_detail` — actually reverses DRF's router-generated
   `retrieve` route via a URL-name collision and asserts only `200` +
   `isinstance(dict)`. The golden-master script explicitly excludes this
   action (`scripts/golden_master_ledger_pdf.py:4-6`). On the frontend,
   exactly one test in the whole feature exercises a real calculation
   (`ledgerExport.test.ts:122`, the Excel running balance); the PDF path's
   identical code and the page's own totals are untested. **Phase 3D
   (characterization tests) is not optional here the way it was optional for
   Item Pivot Phase 2B.2A.**

Net: this migration's centre of gravity is a **business decision** (§10 B2:
which running-balance convention is correct) followed by mechanical
de-duplication of three identical client loops. That is the reverse of Item
Pivot, where the hard part was translating logic that had no backend
counterpart. Sizing and sequencing follow accordingly.

---

## 1. Scope

### In scope — confirmed by reading, not assumed

| Layer | File | Evidence |
|---|---|---|
| Backend action | `backend/apps/license/views/ledger.py:218-259` — `LicenseLedgerViewSet.ledger_detail` | Read in full. Calls only `_find_license_by_id_or_number` (`:114`) and the two builders (`:251-259`). |
| Backend logic | `backend/apps/license/services/exporters/ledger_pdf.py:1025-1273` (`build_dfia_ledger_detail`) and `:1276-1451` (`build_incentive_ledger_detail`) | Read in full. |
| Page | `frontend/src/pages/LicenseLedgerDetail.tsx` (509 lines) + `LicenseLedgerDetail.test.tsx` | Read in full. |
| Client-side exports | `frontend/src/utils/ledgerExport.js` (825 lines) + `ledgerExport.test.ts` | Read in full. **No backend PDF/Excel endpoint exists for this feature** — both formats are produced in the browser via `jspdf`/`exceljs`. |

### Confirmed out of scope (and why)

**`frontend/src/pages/LicenseLedger.tsx`** — the License Ledger *list* page
(route `/license-ledger`, `AppRoutes.tsx:226-230`). It reads
`license-ledger/summary/` (`:412`) and `license-ledger/license-wise/` (`:423`),
both backed by `ledger_service.py`, and renders server-supplied
`purchase_total`/`sale_total`/`profit_loss` (`:191`) without recomputation.
Its own display logic is genuinely compliant. **But see the boundary
correction below — it is not fully separable.**

**`frontend/src/pages/license-overview/*`** (`FinancialLedgerTable.tsx`,
`CustomsLedgerTable.tsx`, `InvoiceLedgerTab.tsx`, `CustomsLedgerSection.tsx`)
— tabs of the License Overview workspace at `/licenses/:id/overview`
(`AppRoutes.tsx:238-242`), fed by `licenses/<id>/balance-ledger/`
(`useLicenseBalanceLedger.ts:42`) and `licenses/<id>/overview-invoice-ledger/`
(`useLicenseOverviewInvoiceLedger.ts:15`). Different route, different
endpoints, different backend module; none of the four imports
`utils/ledgerExport`. Zero shared code path. Name collision on "ledger" only.

**`license_balance_ledger_builder.py` + `license_balance_pdf.py` /
`license_balance_excel.py`** — the Licence Balance & Financial Reconciliation
report (`licenses/<pk>/balance-ledger|balance-pdf|balance-excel/`, actions at
`views/license_balance_ledger.py:40-55` and `views/license.py:659-687`).
`LicenseBalanceLedgerBuilder` (`:186`) is already the single owner per
`CALCULATION_OWNERSHIP.md` and is the reference implementation the Display
Dataset Rule points at. No import relationship with `ledger_pdf.py` in either
direction.

**`backend/apps/license/views/ledger_upload.py`** — write-path bulk ingestion
of DGFT ledger files (`LedgerUploadView:20`, `LedgerTaskStatusView:238`,
routed at `urls.py:45,47`). Imports only `scripts.parse_ledger*`. Not a
display feature.

### Boundary corrections — the brief's scope statement is right about the
### backend and incomplete about the frontend

**The backend boundary holds, and holds more cleanly than expected.**
`ledger_detail` calls nothing from `ledger_service.py`, directly or
transitively — verified by reading the action body and both builders'
complete call sets. More strongly: `build_dfia_ledger_detail` and
`build_incentive_ledger_detail` call **no module-level helper in
`ledger_pdf.py` and none of the eleven `shared.pdf.builders` helpers imported
at `:25-37`**. The shared-helper overlap list the brief asked for is
**empty**. The file has only six module-level functions
(`:43, :237, :555, :937, :1025, :1276`) and no private helpers; the only
intra-file call is `generate_detailed_licenses_pdf → get_license_transactions`
(`:273, :443`), both out of scope.

The `ledger_pdf.py` overlap is therefore **duplication by copy, not coupling
by helper** — which is better for refactoring safety and worse for
correctness. `get_license_transactions` (`:43-235`, out of scope) is a
near-verbatim second implementation of the same rules: the identical
direction-aware company filter (`:78-81` vs `:1044-1047` vs `:1291-1294`, its
own docstring at `:48-50` says "same logic as ledger_detail"), its own
`running_balance` (`:100`), and its own dead `total_sales_amount`
(`:103, :194`). **A fix to the filtering or balance rule that lands only in
the in-scope builders will silently desynchronise the `export/all` PDF from
the detail view.** Treat this as a blast-radius note in every phase, not as
an invitation to expand primary scope.

**Two frontend boundary leaks, both real:**

1. **`ledgerExport.js` is shared with the out-of-scope list page.**
   `LicenseLedger.tsx:6` imports the same `generatePDF`/`generateExcel`.
   Worse, `fetchFullLedgerDetails` (`:455-484`) fans out `Promise.allSettled`
   over **every** license hitting `license-ledger/<id>/ledger_detail/`
   (`:470`) and passes the array to those exporters. So the list page's bulk
   export is a *second consumer of the in-scope endpoint* and the *primary*
   consumer of the multi-license Summary sheet — the detail page always calls
   with a single-element array (`LicenseLedgerDetail.tsx:212, 215`), making
   its own summary page degenerate. **Any change to the `ledger_detail`
   response shape or to `ledgerExport.js` must be regression-checked against
   the list page's bulk export.** This is the single largest blast-radius
   item in the migration.

2. **`LicensesTable.tsx` is a third, undeclared consumer of the endpoint.**
   `frontend/src/pages/masters/tables/LicensesTable.tsx:990` fetches
   `license-ledger/<id>/ledger_detail/` eagerly on row expand and renders a
   Transactions tab (`:518-629`) — including, at `:616`, the backend's
   `balance` field. This was not in the brief's scope statement and is where
   finding #1 above comes from. It must be in scope for *verification* even
   if it is not modified.

One dead-code note inside the in-scope action: `views/ledger.py:228-229`
imports `LicenseTrade` and `Q`, neither of which the body uses — leftovers
from the extraction refactor.

---

## 2. Dependency Graph

```
LicenseBalance.balance_cif  (materialised; owner LicenseBalanceCalculator)
        │
        ▼
LicenseLedgerViewSet.ledger_detail  (views/ledger.py:218-259)
        │  └─ _find_license_by_id_or_number (:114) ── shared with retrieve (:174)
        ▼
build_dfia_ledger_detail (ledger_pdf.py:1025)  /  build_incentive_ledger_detail (:1276)
        │   • per-txn cif/amount/rate/items/sion_norms   → single-sourced, read verbatim
        │   • per-txn `balance`  (license-wide replay)   → ONE reader, app-wide
        │   • per-txn `profit_loss` (wtd-avg-cost)       → read, rendered 4 ways
        │   • total_value / available_balance / db_balance
        │   • total_purchase_amount / total_sales_amount / company_purchase_*
        │        ↑ never returned; total_sales_amount never even read
        ▼
   JSON response
        │
   ┌────┼──────────────────┬──────────────────────┬─────────────────────┐
   ▼    ▼                  ▼                      ▼                     ▼
C1 LicenseLedgerDetail   C2 generatePDF        C3 generateExcel     C4 LicensesTable
   .tsx                    (ledgerExport.js)     (ledgerExport.js)     TransactionsTab
   │                       │                     │                     │
   ├ running bal :339-348  ├ running bal :185-191├ running bal :730-740├ reads txn.balance :616
   ├ debit/credit :350-351 ├ debit/credit :222-3 ├ debit/credit :771-2 └ reads profit_loss :619
   ├ companyPL   :352      ├ companyPL   :227    ├ companyPL   :774
   ├ SION union  :287-294  ├ summary P/L :312-319├ summary P/L :508-513
   └ warning     :190-195  ├ 1st purch   :134-140└ (same helpers)
                           └ SION union  :147-155
                                    ▲
                                    │ also called by the OUT-OF-SCOPE list page
                           LicenseLedger.tsx:6, :470  (N× ledger_detail → bulk export)

  ── separately, in the SAME FILE, for the out-of-scope export/all path ──
  get_license_transactions (ledger_pdf.py:43-235)
        └ its own copy of the company filter (:78-81) + running balance (:100)
```

The top half is clean: one builder, one authoritative balance source. The
bottom half is where four consumers each go their own way — and unlike Item
Pivot, one of them (C4) went the *right* way while the feature's own three
went another.

---

## 3. Duplication Map

| Logic | Copies | Locations |
|---|---|---|
| **Per-company running balance** | **3** (+1 differently-scoped backend implementation, +1 out-of-scope near-copy) | `LicenseLedgerDetail.tsx:339-348`; `ledgerExport.js:185-191`; `ledgerExport.js:730-740`. Backend's license-wide variant: `ledger_pdf.py:1056,1127,1188,1212`. Out-of-scope near-copy: `ledger_pdf.py:100,188-198`. |
| **Company total debit / credit (₹)** | **3** | `tsx:350-351`; `js:222-223`; `js:771-772`. Backend computes the same sums as `total_purchase_amount`/`total_sales_amount` (`:1058-1059`) and returns neither. |
| **Company P/L (ledger convention)** | **3** | `tsx:352`; `js:227`; `js:774` |
| **Summary Purchase / Sale / P-L (different convention)** | **2** | `js:312-319`; `js:508-513`, with rollups at `js:341,357` and `js:558,597-599` |
| **License SION-norms union** | **2**, on different delimiters | `tsx:287-294` (splits `', '`); `js:147-155` (splits `','` + trim) |
| **Direction-aware company filter** | **3** | `ledger_pdf.py:1044-1047`; `:1291-1294`; `:78-81` (out of scope) |
| **1st purchase date** | 1 (shared helper, exports only) | `js:134-140` |

Genuine "same number, computed more than once" duplication: rows 1–4 and 6.
Row 5 is a near-duplicate with a latent behavioural difference. Nothing in
this feature is a *coverage gap* in the Item Pivot sense except the purchase
warning (§4) — which is the one thing that exists only on screen.

---

## 4. Data Flow — Current vs. Target

**Current:**
```
backend builds per-txn cells + a license-wide `balance` nobody in this
feature reads, and internal totals it never returns
        │
        ├─▶ C1 page   — recomputes per-company balance + totals
        ├─▶ C2 PDF    — recomputes the same, plus a second P/L convention
        ├─▶ C3 Excel  — recomputes the same, plus the same second convention
        └─▶ C4 table  — reads the backend `balance` (different number)

on-screen-only: the "Action Required" purchase warning (tsx:190-195,244-259)
export-only:    1st Purchase Date, Summary Purchase/Sale/P-L
```

**Target:**
```
build_*_ledger_detail() also builds, once, server-side:
  - `company_groups`: the grouping C1/C2/C3 all recreate, with each
    transaction carrying BOTH balance conventions as distinct named
    fields (see §6) so no consumer has to choose or re-derive
  - per-group `totals`: debit, credit, closing balance, and each P/L
    convention as its own named field
  - `summary`: the license-level rollup the exports' Summary page needs
    (1st purchase date, SION union, per-company purchase/sale/P-L)
  - `warnings`: the purchase/negative-balance rule, so the download says
    what the screen says
        │
        ▼
   Display Dataset (one dict, `apps/core/reports/envelope.py` convention)
        ├─▶ JSON response (additive; nothing renamed or removed)
        ├─▶ C1 page   — renders verbatim, zero arithmetic beyond formatting
        ├─▶ C2 PDF    — same
        ├─▶ C3 Excel  — same
        └─▶ C4 table  — unchanged (already compliant), now provably
                        consistent with C1
```

**Deliberate non-goal:** collapsing the two balance conventions into one
before §10 B2 is answered. The target shape carries both so that the
migration can be *provably behaviour-preserving* first and the semantic
question settled second, in its own commit. This is the "Backend == Current
Frontend until sign-off" discipline from `MODERNIZATION_RETROSPECTIVE.md`
step 2, applied to a case where "current frontend" means three consumers
that already disagree.

---

## 5. Risk Report (summary — full version in `LEDGER_DETAIL_RISK_ANALYSIS.md`)

| Calculation | Risk | Why |
|---|---|---|
| `available_balance` / `db_balance` / per-txn cif, amount, rate, items | **Low** | Already single-sourced, read verbatim by all four consumers. Only cleanup (`db_balance` alias) is in play. |
| Company total debit / credit | **Low-Medium** | Pure sums of already-correct fields, triplicated identically. Mechanical, but touches three files and two untested render paths. |
| Company P/L + Summary P/L | **Medium-High** | Not the arithmetic — the fact that **two conventions ship in one PDF today**. Consolidating forces a choice that changes a number somebody has been reading. |
| Per-company running balance | **High** | Triplicated *and* semantically different from the backend field of the same name, *and* read by a fourth consumer that uses the other convention. Highest-value fix, gated on a business decision. |
| Purchase warning | **Medium** | New backend logic with no server-side equivalent (the Item Pivot Phase 2B.2B shape). Small and well-defined, but genuinely new. |
| Backend `balance` semantics (B2) | **Critical — blocked** | Cannot be risk-managed by engineering discipline. Requires a domain-owner decision before any code. |
| Everything under test | **Aggravating factor across the board** | ~425 lines of backend balance logic with zero tests; the PDF path with zero tests. Every rating above is one band worse than it would be with a normal test net. |

---

## 6. Display Dataset Specification

Additive to the existing return shape (`ledger_pdf.py:1261-1273`, `:1439-1451`).
Nothing existing is renamed or removed — `transactions`, `total_value`,
`available_balance`, and `db_balance` all stay, because C1/C2/C3/C4 and the
out-of-scope list page all read some subset of them today.

Follows `apps/core/reports/envelope.py`: `summary` (required dict), the
report's own existing plural row key (`transactions`, **not** renamed to
`rows`), and `meta`.

```jsonc
{
  // ── Existing, unchanged ──────────────────────────────────────────────
  "license_id": 123,
  "license_type": "DFIA",
  "license_number": "...",
  "license_date": "2026-01-01",
  "expiry_date": "2027-01-01",
  "exporter": "...",
  "port": "...",
  "total_value": 0.0,          // see §10 B1 — meaning is data-dependent today
  "available_balance": 0.0,    // LicenseBalanceCalculator, authoritative
  "db_balance": 0.0,           // redundant alias, §10 C3 — keep until cleanup
  "transactions": [
    {
      // all existing per-txn keys unchanged, PLUS:
      "balance": 0.0,                    // EXISTING — license-wide replay,
                                         // now explicitly documented as such
      "company_running_balance": 0.0,    // NEW — the per-company convention
                                         // C1/C2/C3 compute today, computed
                                         // once here in their exact current
                                         // order and commission handling
      "display_order": 0                 // NEW — the index the consumers'
                                         // TXN_ORDER sort produces, so the
                                         // ordering rule has one owner too
    }
  ],

  // ── NEW: the grouping all three consumers recreate ───────────────────
  "company_groups": [
    {
      "company_id": 7,
      "company_name": "Acme",
      "transaction_indexes": [0, 1, 3],   // indexes into `transactions`,
                                          // in display order — avoids
                                          // duplicating row payloads
      "totals": {
        "total_debit_amount": 0.0,        // replaces tsx:350 / js:222 / js:771
        "total_credit_amount": 0.0,       // replaces tsx:351 / js:223 / js:772
        "closing_balance": 0.0,           // replaces tsx:489 / js:238 / js:775
        "net_amount_pl": 0.0,             // credit − debit, ALL rows
                                          // (the ledger convention:
                                          //  tsx:352 / js:227 / js:774)
        "trade_pl": 0.0,                  // SALE credit − (PURCHASE|OPENING)
                                          // debit (the summary convention:
                                          //  js:319 / js:513)
        "realised_pl": 0.0                // Σ per-txn profit_loss
                                          // (the weighted-avg-cost
                                          //  convention, never totalled today)
      }
    }
  ],

  // ── NEW: envelope-required summary (license level) ───────────────────
  "summary": {
    "total_value": 0.0,              // mirrors the top-level key
    "available_balance": 0.0,        // mirrors the top-level key
    "first_purchase_date": "2026-01-15",  // replaces js:134-140
    "sion_norms": "E1, E5",               // replaces tsx:287-294 / js:147-155
    "transaction_count": 0,
    "company_count": 0,
    "total_debit_amount": 0.0,       // Σ over company_groups
    "total_credit_amount": 0.0,
    "net_amount_pl": 0.0,
    "trade_pl": 0.0,
    "realised_pl": 0.0
  },

  // ── NEW: the on-screen-only rule, made available to the exports ──────
  "warnings": [
    {"code": "NO_PURCHASE_TRANSACTIONS", "severity": "warning",
     "message": "No purchase transactions found. Please add purchase entries for this license."},
    {"code": "NEGATIVE_BALANCE", "severity": "warning",
     "message": "Balance is negative ($-1,234.00). Please add purchase transactions to cover the deficit."}
  ],

  "meta": {
    "generated_at": "...",
    "report_name": "License Ledger Detail",
    "filters_applied": {"license_type": "DFIA", "company": null}
  }
}
```

### Design notes on the shape

**Why three named P/L fields instead of one `profit_loss`.** Because three
conventions genuinely ship today (§0.4), and collapsing them silently would
change a number in a financial report with no audit trail. Naming each one
makes the disagreement visible in the API itself, which is the point of the
registry discipline in `CALCULATION_OWNERSHIP.md`. §10 B3 decides which one
the UI leads with; the other two stay available and documented.

**Why both `balance` and `company_running_balance`.** Same reasoning. `balance`
already has a reader (`LicensesTable.tsx:616`) and must not change meaning
under it. `company_running_balance` gives C1/C2/C3 something to read that is
*exactly* what they compute today, making the cutover provably
behaviour-preserving. If §10 B2 later rules that only one convention is
correct, retiring the other is a separate, deliberate commit.

**Why `transaction_indexes` rather than nested transaction objects.** Keeps
`transactions` the single row array (envelope convention), avoids doubling
the payload, and preserves the existing top-level `transactions` key that all
four consumers read today.

**`warnings` is not speculative here.** Unlike Item Pivot §9.1, where an
exhaustive grep found no warnings feature at all, this one is implemented and
rendered: `LicenseLedgerDetail.tsx:190-195` and `:244-259`. Moving it to the
backend closes a real gap — today the on-screen "Action Required" banner is
absent from the file the user downloads.

**`warnings[].message` carries a pre-formatted currency string.** That is
deliberate: the negative-balance message embeds the amount
(`LicenseLedgerDetail.tsx:255`), and the currency symbol depends on license
type. Formatting it once server-side prevents PDF/Excel repeating the
symbol bug catalogued as C6 in the inventory. Consumers that want to restyle
it can read `code` and the numeric fields instead.

---

## 7. Migration Plan (summary)

Full version, with per-step files, tests, rollback, blast radius, and owning
agent, in `LEDGER_DETAIL_MIGRATION_PLAN.md`.

| Phase | What | Gate |
|---|---|---|
| **3A** | This research + design (done) | Approval of this document |
| **3B** | Business decisions on every §10 Category B item, recorded as a dated addendum | Domain-owner sign-off |
| **3C** | Characterization tests **first** — backend fixtures for both builders, frontend tests pinning C1's and C2's current numbers | Green suite; no behaviour change |
| **3D** | Backend Display Dataset, additive only | Fixture tests + real-data parity canary |
| **3E** | C1 page cutover | Parity clean |
| **3F** | C2 PDF cutover | Its own commit — zero test coverage today |
| **3G** | C3 Excel cutover | Its own commit |
| **3H** | Cross-consumer reconciliation: C4 + the out-of-scope list page's bulk export | Explicit regression pass on `LicenseLedger.tsx` |
| **3I** | Cleanup audit + `CALCULATION_OWNERSHIP.md` update | Every new field has a proven reader |
| **3J** | Retrospective | — |

Phase 3C before 3D is the deliberate deviation from Item Pivot's ordering.
Item Pivot could implement first and test after because
`test_item_pivot_*` already existed to catch regressions. Here there is
nothing. Writing characterization tests against the *current* (possibly
quirky) output is the only way to make the subsequent phases falsifiable.

---

## 8. Reverse-engineered spec of the client-side running balance

The exact rule all three copies implement, stated once so the backend
translation has an unambiguous target. Verified identical in
`LicenseLedgerDetail.tsx:331-348`, `ledgerExport.js:118-119,185-191`, and
`ledgerExport.js:708,730-740`.

```
For each company group (in Object.values insertion order of first
appearance — tsx:113, js:115):

  txns := stable-sort(group.transactions) by
             TXN_ORDER[type] where {OPENING:0, PURCHASE:1, SALE:2}
             and any other type (i.e. COMMISSION, UNKNOWN) → 1
          # no date component; ties keep backend response order

  running := 0
  for txn in txns:
      if txn.type in {PURCHASE, OPENING}:
          running += isDFIA ? txn.debit_cif : txn.debit_license_value
      elif txn.type == SALE:
          running -= isDFIA ? txn.credit_cif : txn.credit_license_value
      # COMMISSION: running unchanged, but the row still displays `running`
      row.balance := running

  group.closing_balance := running        # tsx:489, js:238, js:775
```

Three consequences worth stating explicitly because they will surface as
"the backend changed my numbers" if not anticipated:

- **`COMMISSION` rows sort as `PURCHASE`** (`?? 1`) but contribute **zero** to
  the balance. They appear interleaved among purchases showing an unchanged
  running figure.
- **Ordering ignores dates entirely.** A January sale sorts after a December
  purchase not because of the dates but because `SALE > PURCHASE` in
  `TXN_ORDER`. Within a bucket, order is whatever the backend returned —
  which *is* date-ordered (`ledger_pdf.py:1053,1067`), so the visible result
  is usually chronological by accident, not by rule.
- **The closing balance never equals `available_balance`**, and is not meant
  to: `available_balance` includes BOE debits and allotments, which never
  appear as ledger transactions at all (`ledger_pdf.py:1249-1259` documents
  exactly this). The page shows both — CURRENT BALANCE in the header
  (`tsx:321`) and a different closing figure in every company total row
  (`tsx:489`) — with nothing explaining the gap.

Incentive differs only in reading `debit_license_value`/`credit_license_value`
and in the backend never emitting a synthetic zero-trade `OPENING` row
(no analogue of `ledger_pdf.py:1070-1088`).

---

## 9. Quirks found during reverse-engineering — preserve, don't silently fix

Full catalogue with citations in `LEDGER_DETAIL_CALCULATION_INVENTORY.md` §5.
Summarised here with classifications:

- **[B1]** `total_value` means "purchased CIF" with trades, "total export CIF"
  without (`ledger_pdf.py:1073` vs `:1128`); Incentive has no such branch.
- **[B2]** Backend `balance` (license-wide) vs client running balance
  (per-company) — two conventions, one label, both live.
- **[B3]** Three unreconciled P/L definitions, two of them in the same PDF.
- **[C1]** Commissions counted in the ledger total row, excluded from the
  summary row.
- **[C2]** `total_sales_amount` written and never read (`:1059,1213`;
  `:1313,1405`; `:103,194`).
- **[C3]** `db_balance` — zero readers repo-wide.
- **[C4]** `profit_loss` rendered four different ways; the page hides the
  sign of a loss (`tsx:470`).
- **[C5]** Zero renders `0.00` on screen, `-` in both exports (`js:122`).
- **[C6]** PDF labels Incentive money in `$` (`js:276,331,352,423,531,570`);
  Excel's detail sheet does not (`js:677`).
- **[C7]** `rate` is an INR/CIF-$ ratio for DFIA (2dp) and a percentage for
  Incentive (3dp), under one "Rate" column header.
- **[C8]** The zero-trade `OPENING` row has no `company_id` and renders under
  a company header reading "N/A".
- **[C9]** `', '.join(set(items_desc))[:100]` (`:1166`) is non-deterministic
  across processes.
- **[A1]** The *"fixes the '–' bug"* comment is accurate and self-contained —
  a removed client-side object-identity bug, not backend evidence. Preserve
  the comment's substance in the new code's docstring so the history is not
  lost when the inline loops are deleted.

---

## 10. Open questions — classified

Do not schedule Phase 3D until every **B** row has a recorded decision.

| # | Question | Category | Migration goal until resolved |
|---|---|---|---|
| **B1** | Should "Total Value" mean total purchased CIF, or the license's face/export CIF? Today it silently switches based on whether trades exist (`ledger_pdf.py:1073` vs `:1128`), and Incentive never switches. | **B** | Preserve both branches exactly. Expose them as two named fields internally so the eventual decision is a display change, not a recalculation. |
| **B2** | **Which running-balance convention is correct — license-wide (backend `balance`) or per-company (the three client copies)?** Two screens show different numbers for the same license today (`LicensesTable.tsx:616` vs `LicenseLedgerDetail.tsx:463`). | **B — blocking, highest priority** | Ship both as separately named fields (§6). Change no displayed number until answered. Then retire the loser in its own commit. |
| **B3** | Which P/L convention leads: weighted-average-cost margin, credit−debit over all rows, or SALE−PURCHASE excluding commissions? | **B** | Expose all three as named fields; leave each consumer reading the one it reads today. |
| **B4** | Should `COMMISSION` rows affect the running balance? Backend says yes for `COMMISSION_SALE` (`:1188`) and yes for `COMMISSION_PURCHASE` (`:1127`); all three client copies say no. Downstream of B2 but separable. | **B** | Preserve per convention. |
| **C1** | Commission counted in the ledger total, excluded from the summary total — carry forward or fix? | **C** | Preserve; pin with a regression test; file a follow-up. |
| **C2** | `total_sales_amount` dead variable — delete? | **C** | Safe to delete during 3D since the Display Dataset will return the value properly. Note the out-of-scope third copy at `:103,194` stays. |
| **C3** | `db_balance` redundant alias — remove? | **C** | Keep through 3I (an external consumer may exist outside this repo); remove only after an explicit check. |
| **C4** | P/L sign hidden on screen (`tsx:470`) — intentional or defect? | **C** | Preserve; the fix is a one-line display change once someone confirms. |
| **C5** | Zero → `'-'` in exports but `0.00` on screen (`js:122`) | **C** | Preserve; pin with a test. |
| **C6** | Incentive money labelled `$` in the PDF | **C** | Preserve for parity in 3F, then fix in its own commit — this one is a genuine mislabel with real user-confusion cost, worth prioritising among the C items. |
| **C7** | `rate` means two different things under one header | **C** | Preserve; consider a type-aware column label later. |
| **C8** | Zero-trade `OPENING` row grouped under "N/A" | **C** | Preserve; pin with a test. |
| **C9** | Non-deterministic `items` ordering (`set` at `:1166`) | **C** | Preserve the *set* semantics but sort before joining, as part of 3C — otherwise characterization tests will flake. **This is the one C item that must be addressed early**, because it makes golden-master/parity comparison unreliable. Sorting a set that is already order-insensitive by intent is not a business-logic change. |
| — | Should the purchase warning appear in the PDF/Excel downloads? Today it is on-screen only. | scoping | Confirm before building `warnings` into the exports; the DTO field is cheap either way. |
| — | Should `ledger_detail` gain a backend export endpoint, replacing the client-side PDF/Excel entirely? | scoping | **Out of scope for Phase 3.** Recorded because it is the obvious end state and someone will ask. See §11. |

---

## 11. Explicitly not proposed

**Moving PDF/Excel generation to the backend.** It is the architecturally
"correct" end state — it would align this feature with every other report in
the app and let the Display Dataset be consumed by a ReportLab/openpyxl
exporter the way `license_balance_pdf.py` already does. It is **not** part of
this migration: it would be a rewrite of 825 lines of working client-side
code, it would change PDF/Excel output byte-for-byte (jspdf/exceljs vs
reportlab/openpyxl render nothing alike), and it would couple a
behaviour-preserving de-duplication to a visual redesign. Do the Display
Dataset work first; the rendering-location question is then a cheap,
independent decision on a codebase where the numbers already have one owner.

**Fixing anything.** Per the brief and per `MODERNIZATION_RETROSPECTIVE.md`
lesson 1, every quirk in §9 is preserved for parity. The single exception
proposed is C9 (sort before joining a set), justified above as a
determinism fix to an order-insensitive value, needed to make the phase's
own verification possible. Even that is called out for approval rather than
assumed.

---

**No source files were modified in producing this document.**
