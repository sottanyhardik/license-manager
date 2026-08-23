# License Ledger Detail — Migration Plan (Phase 3)

**Status:** Plan only. No code changes made. Do not begin Phase 3C until
this plan and `LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md` are approved and
every Category B item in that document's §10 has a recorded decision.
**Companions:** `LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md`,
`LEDGER_DETAIL_CALCULATION_INVENTORY.md`, `LEDGER_DETAIL_RISK_ANALYSIS.md`.

---

## 0. Why this plan does not copy Item Pivot's phase shape

Item Pivot's shape was: *consolidate duplicated logic (2B.2A) → build new
logic that had no backend equivalent (2B.2B) → cut over*. This feature
inverts both halves.

| | Item Pivot | License Ledger Detail |
|---|---|---|
| Backend equivalent exists? | No, for the hard part | **Yes** — `balance` is already computed and returned (`ledger_pdf.py:1086…1242`) |
| Why isn't it used? | N/A | Because it computes a **semantically different** number (design doc §0.2) |
| Existing test net | `test_item_pivot_*`, 63 tests | **Zero** for both builders; one calculation test on the whole frontend feature |
| Excel export | Backend-streamed | **Client-side JS**, in the same file the page imports |
| Consumers of the endpoint | 1 page + 1 exporter | **4** (design doc §1), one of them an out-of-scope page |

Consequences that shape the phases below:

1. **Tests come before implementation, not after.** With no coverage,
   "additive-only" is not self-verifying. Phase 3C exists solely to make
   later phases falsifiable.
2. **A business decision is a hard gate, not a parallel track.** The core
   duplication cannot be resolved without answering §10 B2. Item Pivot
   could sequence its Category B decision alongside implementation because
   the frontend was the only ground truth; here two ground truths already
   ship.
3. **There is no separate "Excel cutover phase" in the Item Pivot sense** —
   but there *are* two export cutovers, because `ledgerExport.js`'s PDF path
   and Excel path are independently written, independently quirky
   (inventory §5 C5/C6), and only one of them has any test coverage.
4. **A cross-consumer phase (3H) is mandatory.** Item Pivot had no
   equivalent. Here, `LicenseLedger.tsx` (out of scope) calls the in-scope
   endpoint N× and the in-scope exporters, and `LicensesTable.tsx` renders
   the field this migration is about.

---

## 1. Phases

### Phase 3A — Research & design **(this phase — complete)**

**Deliverables:** this plan plus the three companion documents.
**Blast radius:** zero (documents only).
**Owner:** `solutions-architect`.
**Exit gate:** user approves the design doc.

---

### Phase 3B — Business-rule decisions **(no code)**

Get an explicit, dated answer on every Category B item in the design doc's
§10 — B1 (`total_value` dual meaning), **B2 (which running-balance
convention is authoritative)**, B3 (which P/L convention leads), B4
(commissions in the balance) — plus a yes/no on the two scoping questions
(warnings in exports; backend export endpoint deferred).

Record as a dated addendum section appended to
`LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md`, committed on its own, exactly as
`ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md:503-548` did.

**Prep material for the conversation** (build these, they are cheap and make
the decision concrete):
- A one-page worked example on a real multi-company license showing the
  license-wide `balance` column beside the per-company one, and the same
  license as rendered by `LicensesTable.tsx` vs `LicenseLedgerDetail.tsx`.
  Screenshot both.
- The same license's PDF, with page 1's Summary P/L and page 2's Total row
  P/L circled where they disagree.

**Blast radius:** zero.
**Owner:** `product-manager` prepares, domain owner decides.
**Exit gate:** every B row has a written decision. **Do not proceed on
"probably fine."**

---

### Phase 3C — Characterization tests **(behaviour-preserving, no logic change)**

Pin the current behaviour of everything Phase 3D–3G will touch, *before*
touching it. This phase is pure test-writing plus one determinism fix.

**3C.1 — Backend fixtures.** New `backend/apps/license/tests/test_ledger_detail_builders.py`
covering `build_dfia_ledger_detail` and `build_incentive_ledger_detail`
directly (not through the view). Minimum cases, each hand-computed:
- single purchase, single sale, one company — the happy path
- **two companies** — pins the license-wide vs per-company distinction
- `COMMISSION_PURCHASE` and `COMMISSION_SALE` present — pins `:1127` and
  `:1188` balance behaviour and the `total_purchase_amount` side effect
- zero trades with `opening_balance > 0` — pins the synthetic `OPENING` row
  (`:1070-1088`), its missing `company_id` (C8), and `total_value` taking the
  export-CIF meaning (B1)
- sale with no prior purchase from that company — pins the three-way
  `profit_loss` fallback (`:1218-1225`)
- `exc_rate` zero / null / `cif_inr` null — pins the CIF derivation at
  `:1101-1109`
- `company_id` filter set — pins the direction-aware filter (`:1044-1047`)
- Incentive: `rate_pct` 3dp rounding (`:1347`), no synthetic OPENING row,
  `first_transaction` consumed by a leading `COMMISSION_PURCHASE` (`:1376`)

**3C.2 — Endpoint test that actually hits the endpoint.** Fix
`backend/tests/test_api_trade.py:91` — it reverses
`license:license-ledger-detail` (DRF's `retrieve`) and asserts nothing
meaningful. Either rename it honestly or add a real
`license:license-ledger-ledger-detail` test. **Flag, don't silently
repurpose** — a test named for one route and hitting another is worth a line
in the commit message.

**3C.3 — Frontend characterization.** Extend
`frontend/src/pages/LicenseLedgerDetail.test.tsx` to render a two-company,
one-commission fixture and assert the *actual rendered* Balance, Total Debit,
Total Credit, and P/L cells (today: zero numeric assertions). Extend
`frontend/src/utils/ledgerExport.test.ts` to cover **`generatePDF`** — never
executed by any test today — asserting `buildPdfBody`'s returned rows rather
than the rendered PDF.

**3C.4 — Determinism fix (design doc §10 C9).** `ledger_pdf.py:1166`
`', '.join(set(items_desc))` → sort before joining. Order-insensitive by
intent; non-deterministic in fact; makes every test above flaky if left.
Do this in 3C, not later, and call it out explicitly in the commit.

**Files:** 2 new/modified backend test files, 2 modified frontend test files,
1 line in `ledger_pdf.py`.
**Blast radius:** **Low.** Tests plus one sort. The sort *can* change a
displayed `items` string ordering — acceptable and disclosed.
**Owner:** `qa-test-engineer`, with `backend-engineer` on 3C.4.
**Rollback:** trivial; tests are additive.
**Exit gate:** full suite green, run explicitly as
`pytest apps/license/tests/` **and** `pytest tests/` (`pytest.ini:6` sets
`testpaths = tests`, so a bare `pytest` skips all 868 license tests — see §4).

---

### Phase 3D — Backend Display Dataset **(additive only)**

Implement design doc §6 inside `build_dfia_ledger_detail` and
`build_incentive_ledger_detail`: `company_groups` with per-group `totals`,
`summary`, `warnings`, `meta`, and the per-transaction
`company_running_balance` / `display_order`.

**Non-negotiable constraints:**
- Additive only. `transactions`, `total_value`, `available_balance`,
  `db_balance`, and every existing per-txn key keep their current names and
  values. Four consumers plus the out-of-scope list page read them.
- `company_running_balance` must reproduce design doc §8 *exactly*, including
  the commission-contributes-nothing rule and the `TXN_ORDER` sort — it is a
  translation of current client behaviour, not an improvement of it.
- No consumer changes in this phase. The new keys ship unread.
- Extract the shared parts of the two builders only if it is genuinely
  behaviour-preserving; they are 80% parallel but differ in the OPENING
  branch, the `rate` semantic, and the profit fallback. **Prefer duplication
  over a premature shared helper here** — a wrong abstraction across a
  DFIA/Incentive seam is harder to unwind than a copy.
- Delete `total_sales_amount` (C2) in this phase, since the value it held is
  now properly returned. Leave the out-of-scope copy at `:103,194` alone.

**Validate with `apps/core/reports/envelope.py:validate_envelope` in the
tests** (`row_key="transactions"`), per the Phase 2A convention.

**Files:** `ledger_pdf.py` (two functions), new tests.
**Blast radius:** **Medium.** One backend file, but the response grows for
five consumers. Payload size: `company_groups` uses `transaction_indexes`
rather than nested rows precisely to keep this bounded — verify the
`LicenseLedger.tsx` bulk path (which fetches N licenses in parallel,
`:466-472`) does not regress on payload or latency.
**Owner:** `backend-engineer`; `performance-engineer` reviews the bulk-fetch
payload impact.
**Rollback:** revert one commit; every key is additive.
**Exit gate:** 3C tests still green + new fixture tests + the parity canary
below.

**3D.parity — real-data canary (do not skip).** Per
`MODERNIZATION_RETROSPECTIVE.md` step 4 and lesson 4: port the literal JS
from `ledgerExport.js:185-191` and `:730-740` into a throwaway Node script,
run it against the real `ledger_detail` JSON for a sample of real licenses
(include: multi-company, commission-bearing, zero-trade, and Incentive),
and diff field-by-field against the new `company_running_balance` and
`totals`. **Record the numbers in the design doc; delete the script.** Do not
add it to `scripts/`.

Compare **by numeric value, not by string**, and watch for the cross-language
representation trap from `MODERNIZATION_RETROSPECTIVE.md` lesson 3 — here the
likely instance is company keys: JS uses `String(txn.company_id)`
(`ledgerExport.js:109`) and unknowns become `` `unknown-${index}` ``, while
Python will produce different placeholder keys unless matched deliberately.

---

### Phase 3E — Page cutover (C1)

`LicenseLedgerDetail.tsx` reads `company_groups`, per-group `totals`, and
`summary.sion_norms` instead of computing them. Delete:
`companyBalMap`/`companyRunning` (`:339-348`), the `totalDebit`/`totalCredit`
reduces (`:350-351`), `companyPL` (`:352`), the SION `Set` union
(`:287-294`), and — if 3B approved backend warnings — `hasPurchases`/
`showPurchaseWarning` (`:190-195`).

`groupTransactionsByCompany` (`:104-114`) becomes dead and should go with
them; its test (`LicenseLedgerDetail.test.tsx:67`) is replaced by a backend
grouping test.

**Preserve every display quirk**: `Math.abs` on P/L (`:470`, C4), `0.00`
rather than `-` for zero (`:463`, C5). Those are display-layer, and per
`MODERNIZATION_RETROSPECTIVE.md` lesson 3, representation differences get
fixed at the display layer — not by bending the DTO.

**Files:** `LicenseLedgerDetail.tsx`, `LicenseLedgerDetail.test.tsx`.
**Blast radius:** **Medium.** One page, but it is the feature's whole
surface, and this is the first user-visible commit.
**Owner:** `frontend-engineer`; `code-reviewer` before merge.
**Rollback:** one commit; backend keys stay, so reverting the page is safe
and independent.
**Exit gate:** 3C.3's characterization assertions pass **unchanged** — that
is the whole point of writing them first.

---

### Phase 3F — PDF cutover (C2)

`buildPdfBody` (`ledgerExport.js:159-244`) and `writeSummaryPageToPdf`
(`:303-400`) read the backend objects. Delete the inline `running` loop
(`:185-191`), the `totalDebit`/`totalCredit`/`companyPL` reduces
(`:222-227`), and the summary-page `_tPurchase`/`_tSale`/`pl` block
(`:312-319`) plus its rollups (`:341,357`).

**Preserve the removed code's *documentation***: the comment at `:164-168`
records a real past bug (design doc §9 A1). Carry its substance into the new
code's docstring so a future engineer does not reintroduce a
reference-keyed Map.

`getFirstPurchaseDate` (`:134-140`) and `getLicenseSionNorms` (`:147-155`)
are replaced by `summary.first_purchase_date` / `summary.sion_norms` — but
**only if the list page's multi-license case is covered**, since those
helpers run per-license inside a loop over many licenses there. See 3H.

**Separate commit from 3G, deliberately:** the PDF path has **zero** test
coverage today. 3C.3 adds some; even so, do not batch it with Excel.

**Files:** `ledgerExport.js`, `ledgerExport.test.ts`.
**Blast radius:** **Medium-High** — the file is shared with the out-of-scope
list page (design doc §1). Every change here ships to both.
**Owner:** `frontend-engineer`.
**Rollback:** one commit.
**Exit gate:** new PDF tests from 3C.3 pass unchanged; manual diff of a
before/after PDF for one DFIA and one Incentive license.

---

### Phase 3G — Excel cutover (C3)

Same treatment for `generateExcel`'s inline loop (`:730-740`), totals
(`:771-774`), and `buildSummarySheet`'s `totalPurchase`/`totalSale`/`pl`
(`:508-513`) plus rollups (`:558,597-599`).

`ledgerExport.test.ts:122-176` — the feature's only genuine calculation test
— must pass **without modification**. If it needs editing to accommodate the
cutover, the cutover changed behaviour and is wrong.

**Files:** `ledgerExport.js`, `ledgerExport.test.ts`.
**Blast radius:** **Medium-High**, same shared-file reason.
**Owner:** `frontend-engineer`.
**Exit gate:** `ledgerExport.test.ts:122` green unmodified; manual workbook
diff for DFIA and Incentive.

---

### Phase 3H — Cross-consumer reconciliation

The phase Item Pivot never needed.

**3H.1 — `LicensesTable.tsx` (C4).** It renders `txn.balance` at `:616`.
Depending on the 3B/B2 decision:
- *license-wide wins* → C1/C2/C3 now agree with it; add a test asserting the
  two screens show the same figure for the same license.
- *per-company wins* → `LicensesTable.tsx` must switch to
  `company_running_balance`, which changes a number on a screen nobody in
  this migration set out to touch. **Flag this explicitly to the user before
  shipping** — it is the most surprising user-visible consequence of the
  whole migration.

**3H.2 — `LicenseLedger.tsx` bulk export (out-of-scope page, in-scope
impact).** Its `fetchFullLedgerDetails` (`:455-484`) fans out over every
license and feeds the array to the now-rewritten exporters — the *primary*
consumer of the Summary sheet, since the detail page always passes a
single-element array (`LicenseLedgerDetail.tsx:212,215`). Regression-test the
multi-license path explicitly: multiple licenses, overlapping companies,
per-license rows and per-company rollups. This is where a subtle
`summary`-object-per-license vs rollup-across-licenses mistake will land.

**3H.3 — the `ledger_pdf.py` semantic twin.** Record in
`CALCULATION_OWNERSHIP.md` that `get_license_transactions` (`:43-235`) is a
copy of these rules serving `export/all`, and that changes to the filter
(`:78-81`) or balance (`:100`) must be mirrored. Do **not** refactor it in
this phase — it is out of scope and guarded only by
`scripts/golden_master_ledger_pdf.py`, which is a manual script, not CI.

**Blast radius:** **Medium** for 3H.1 (one file, possibly one changed
number), **High** for 3H.2 (verification only, but the failure mode is a
broken bulk export for the list page).
**Owner:** `frontend-engineer` + `qa-test-engineer`; `code-reviewer` on 3H.2.

---

### Phase 3I — Cleanup audit

Per `MODERNIZATION_RETROSPECTIVE.md` lesson 2 — an additive migration can
reintroduce the exact duplication it exists to remove. Do not assume.

- [ ] Grep every field added in 3D and confirm each has a **real reader**.
      Specifically check that the backend's `company_groups[].totals` are
      read rather than re-derived from `transactions` by any consumer.
- [ ] Confirm zero remaining `running +=` / `reduce((s, t) =>` over ledger
      transactions in `frontend/src`.
- [ ] Add regression tests that fail **loudly** if a client-side copy
      returns: set the raw inputs to values that would produce a *different*
      wrong answer if recomputed inline, exactly as
      `test_notification_summary_reads_effective_fields_not_raw_inputs` does
      for Item Pivot.
- [ ] Decide `db_balance` (C3) — zero readers repo-wide; remove only after
      confirming no consumer outside this repo.
- [ ] Remove the dead imports at `views/ledger.py:228-229`.
- [ ] Consider deleting the orphaned `frontend/jest.config.js` (jest not
      installed; `testMatch` matches none of the 49 test files).
- [ ] Update `docs/architecture/CALCULATION_OWNERSHIP.md` with a **License
      Ledger Detail** section, scoped honestly (verified vs. owner-confirmed),
      and correct the existing "License Ledger running balance" row — it
      currently attributes the owner to `LicenseBalanceLedgerBuilder` and
      lists `ledger_pdf.py` as a consumer, which this audit shows is not the
      relationship for `ledger_detail`.

**Blast radius:** Low. **Owner:** `refactor-specialist` + `technical-writer`.

---

### Phase 3J — Retrospective

Append to `MODERNIZATION_RETROSPECTIVE.md` or write a sibling document.
Specifically capture the two lessons this migration adds that Item Pivot
could not:

1. *"The backend already computes it" is not the same as "the backend owns
   it."* A field with one reader on a different screen is a divergence
   waiting to be discovered, and looks like compliance from the API side.
2. *Count the consumers before scoping.* The brief named two; there are four,
   and one of them is a page explicitly declared out of scope. The
   dependents index found the shared *module*; only reading the callers found
   the shared *endpoint*.

---

## 2. Implementation checklist — blast radius per phase

| Phase | Blast radius | Files touched | User-visible? | Ships independently? | Owner |
|---|---|---|---|---|---|
| 3A Research | None | 4 new docs | No | Yes | `solutions-architect` |
| 3B Decisions | None | 1 doc addendum | No | Yes | `product-manager` + domain owner |
| 3C Characterization tests | **Low** | 2 backend tests, 2 frontend tests, 1 line in `ledger_pdf.py` | Only the `items` sort (C9) | Yes | `qa-test-engineer` |
| 3D Backend dataset | **Medium** | `ledger_pdf.py` + tests | No (additive) | Yes | `backend-engineer` |
| 3D.parity Canary | None | throwaway script, deleted | No | N/A | `data-scientist` or `backend-engineer` |
| 3E Page cutover | **Medium** | `LicenseLedgerDetail.tsx` + test | **Yes — first visible commit** | Yes | `frontend-engineer` |
| 3F PDF cutover | **Medium-High** (shared file, zero prior coverage) | `ledgerExport.js` + test | Yes (downloads) | Yes | `frontend-engineer` |
| 3G Excel cutover | **Medium-High** (shared file) | `ledgerExport.js` + test | Yes (downloads) | Yes, after 3F | `frontend-engineer` |
| 3H.1 `LicensesTable` | **Medium** | `LicensesTable.tsx` | **Possibly — depends on B2** | Yes | `frontend-engineer` |
| 3H.2 Bulk-export regression | **High** (verification) | tests only | No, if it passes | Must gate 3F/3G | `qa-test-engineer` |
| 3H.3 Twin documented | None | `CALCULATION_OWNERSHIP.md` | No | Yes | `technical-writer` |
| 3I Cleanup audit | **Low** | several small | No | Yes | `refactor-specialist` |
| 3J Retrospective | None | 1 doc | No | Yes | `technical-writer` |

**Recommended order:** 3A → **3B (hard gate)** → 3C → 3D → 3D.parity → 3E →
3F → 3G → 3H → 3I → 3J.

3C and 3D can overlap only if 3C.1's fixtures are written first; do not write
the new backend logic and its tests in the same commit, or the tests will be
written to match the implementation rather than the current behaviour.

---

## 3. Rollback posture

Every phase from 3D on is a single revertable commit, and the backend work is
additive, so:

- Reverting **3E/3F/3G/3H.1** restores the old client-side calculations with
  the new backend fields still present and simply unread — no coordinated
  rollback needed.
- Reverting **3D** requires 3E–3H.1 to be reverted first (they read its
  fields). Sequence rollbacks in reverse order.
- **3C** should never need reverting; if a characterization test is wrong,
  the test is wrong, and finding that out is the phase working as intended.

---

## 4. Environment notes that will bite

- **`pytest.ini:6` sets `testpaths = tests`.** A bare `pytest` in `backend/`
  collects 210 tests and **skips all 868** under `apps/license/tests/` —
  including `test_ledger_service.py` and everything 3C.1 will add. Always run
  both paths explicitly. Worth raising as a separate CI issue; do not fix it
  inside this migration.
- **`pytest.ini` declares `env = TESTING=true` but `pytest-env` is not
  installed**, so the variable is silently never set and the warning is
  swallowed by `-p no:warnings`. Do not write a test that depends on it.
- **Stale `__pycache__`-only directories** exist under `backend/tests/`
  (`license/`, `reports/`, `integration/`, `accounts/`, `allotment/`,
  `balance/`, `bill_of_entry/`, `core/`, `dashboard/`, `tasks/`). The `.py`
  sources were deleted. Do not mistake a `.pyc` for coverage.
- **Frontend runs Vitest** (`frontend/vitest.config.ts`, `npm test` →
  `vitest run`). `frontend/jest.config.js` is orphaned.
- **Concurrent-session risk is real in this working tree** — per
  `MODERNIZATION_RETROSPECTIVE.md` lesson 6, verify `git status` /
  `git diff --stat` before *and* after every commit, and stage by explicit
  file path. Never `git add -A`.

---

**No source files were modified in producing this document.**
