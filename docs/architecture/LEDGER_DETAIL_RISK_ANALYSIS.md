# License Ledger Detail — Risk Analysis (Phase 3)

**Status:** Research output. No code changed.
**Companions:** `LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md`,
`LEDGER_DETAIL_CALCULATION_INVENTORY.md`,
`LEDGER_DETAIL_MIGRATION_PLAN.md`.

Ratings are for **migrating** each value to a single backend owner — not for
the value's current correctness. Following the Item Pivot risk report's
distinction between *"already single-sourced, trivial"* and *"new logic, no
backend equivalent, critical"*, with one rating class this feature needs and
Item Pivot did not: **"backend equivalent exists but computes a different
number."** That is the dangerous middle, because it looks compliant from the
API side and is not.

---

## 0. The systemic multiplier

Before the per-calculation table: **~425 lines of backend balance logic
(`build_dfia_ledger_detail`, `build_incentive_ledger_detail`) have zero
tests, and the one test that appears to cover the endpoint hits a different
route via a URL-name collision** (`backend/tests/test_api_trade.py:91`
reverses `license:license-ledger-detail`, DRF's router-generated `retrieve`,
not the action's `license-ledger-ledger-detail`; its assertions are `200` and
`isinstance(dict)` at `:96-98`). The golden-master script excludes the action
by design (`backend/scripts/golden_master_ledger_pdf.py:4-6`). On the
frontend, exactly one test in the feature exercises a calculation
(`frontend/src/utils/ledgerExport.test.ts:122`).

**Every rating below is one band worse than it would be with a normal test
net.** They are stated *with* that penalty applied, not before it. Phase 3C
exists to remove the penalty; if 3C is skipped or thinned, re-read this
document as if every "Medium" said "High."

Secondary multiplier: `frontend/src/utils/ledgerExport.js` is shared with
`frontend/src/pages/LicenseLedger.tsx` (`:6`), an out-of-scope page whose
bulk export also calls the in-scope endpoint N× (`:470`). Every frontend
rating below carries that shared-blast-radius weight.

---

## 1. Per-calculation risk

### Low

| Calculation | Rating | Reasoning |
|---|---|---|
| `available_balance` | **Low** | Already single-sourced — `float(license.balance_cif or 0)` (`ledger_pdf.py:1260`), which proxies the materialised `LicenseBalance.balance_cif` owned by `LicenseBalanceCalculator`. Read verbatim by all four consumers (`LicenseLedgerDetail.tsx:193,321`; `ledgerExport.js:248,276,642,677`; `LicensesTable.tsx:565`). Nothing to migrate. The comment at `:1249-1259` shows this was already fixed once, deliberately. |
| Per-transaction `cif_usd` / `debit_cif` / `credit_cif` | **Low** | Computed once (`:1101-1109`), read verbatim everywhere. The `exc_rate`/`cif_fc` fallback is guarded (`:1106`). |
| Per-transaction `amount` / `debit_amount` / `credit_amount` | **Low** | `:1110`, read verbatim. |
| Per-transaction `rate` | **Low to migrate**, see C7 for a labelling concern | `:1121-1124`, read verbatim by three consumers. No consumer re-derives it. |
| `items`, `sion_norms` (per-transaction) | **Low**, with one caveat | Read verbatim. Caveat: `:1166` joins a `set`, so ordering is non-deterministic across processes — harmless today, **fatal to characterization testing**, which is why the plan fixes it in Phase 3C.4 rather than treating it as a normal C item. |
| `db_balance` | **Low** | A redundant alias of `available_balance` (`:1271`, `:1449`) with zero readers repo-wide. Removing it is pure cleanup — the only risk is an unknown consumer outside this repository, which is why the plan defers it to 3I behind an explicit check rather than deleting it in 3D. |
| `total_sales_amount` | **Low** | Dead variable — written at `:1059,1213` (and `:1313,1405`), read nowhere. Deleting it cannot change any output. Listed only so nobody "preserves for parity" a value that is not observable. |

### Low-Medium

| Calculation | Rating | Reasoning |
|---|---|---|
| Company total debit (₹) | **Low-Medium** | Arithmetic is trivial: `reduce` over `debit_amount`, identical in all three copies (`LicenseLedgerDetail.tsx:350`, `ledgerExport.js:222`, `:771`). The backend already computes the same sum internally as `total_purchase_amount` (`:1058,1129,1189`) and simply doesn't return it. Risk is *breadth*, not depth — three call sites in two files, two of which (the page's total row and the PDF's) have no test asserting the rendered number today. |
| Company total credit (₹) | **Low-Medium** | Same, mirroring `total_sales_amount`. |
| `1st Purchase Date` | **Low-Medium** | `ledgerExport.js:134-140` — a `min` over `type === 'PURCHASE'` dates using **lexicographic** comparison. Correct only because DRF serialises dates as ISO `YYYY-MM-DD`; a format change silently breaks it. Frontend-only (no backend equivalent), export-only (never on screen). Small, well-specified, one test already pins it (`ledgerExport.test.ts:178-225`). Translation risk is low; the *hidden coupling to serialisation format* is the thing to note. |

### Medium

| Calculation | Rating | Reasoning |
|---|---|---|
| SION-norms license union | **Medium** | Duplicated twice on **different delimiters**: `LicenseLedgerDetail.tsx:291` splits on `', '`; `ledgerExport.js:152` splits on `','` then trims. Equivalent for the backend's own `', '.join(...)` output (`:1167`), divergent for any value containing a bare comma. Consolidating is easy; the risk is that the two copies are *not* actually identical today and someone assumes they are, picks one, and silently changes the other's output. Rated Medium purely on that trap. |
| Purchase warning (`hasPurchases`, `isNegativeBalance`, `showPurchaseWarning`) | **Medium** | **New backend logic** — the Item Pivot Phase 2B.2B shape, but far smaller. `LicenseLedgerDetail.tsx:190-195` plus the three message variants at `:250-255`. The rule itself is three lines and unambiguous. Two real risks: (a) the negative-balance message embeds a formatted currency amount whose symbol depends on license type — get that wrong server-side and you reproduce the `$`-on-Incentive bug catalogued as C6; (b) it is on-screen-only today, so putting it in downloads is a **product change**, not a migration, and needs the scoping answer in the design doc §10 before it ships. |
| Zero-trade `OPENING` row grouping | **Medium** | `:1074-1088` omits `company_id`/`company_name`, so `groupTransactionsByCompany` (`LicenseLedgerDetail.tsx:107-109`) buckets it as `unknown-0` and labels it "N/A". Backend-side grouping must reproduce this exactly — including the `unknown-${index}` key format (`ledgerExport.js:109`), which is the cross-language representation trap from `MODERNIZATION_RETROSPECTIVE.md` lesson 3 in its most likely local form. Value-level parity will pass while the group key differs. |

### Medium-High

| Calculation | Rating | Reasoning |
|---|---|---|
| Company P/L — ledger convention (`totalCredit − totalDebit`, all rows) | **Medium-High** | Triplicated (`LicenseLedgerDetail.tsx:352`, `ledgerExport.js:227`, `:774`), arithmetically trivial. Elevated because it is one of **three live, unreconciled P/L definitions** (below), and because consolidating forces a decision about which one the UI leads with. Changing a P/L figure in a financial report is not a refactor, whatever the diff looks like. |
| Summary P/L — trade convention (`SALE credit − (PURCHASE\|OPENING) debit`) | **Medium-High** | Duplicated (`ledgerExport.js:319`, `:513`). Same reasoning, plus: it **excludes commissions** where the ledger convention includes them, so the two disagree by exactly the commission amount **inside the same downloaded PDF** — page 1's Summary vs page 2's Total row. Anyone who has reconciled those two numbers by hand and concluded one is "the real one" will notice immediately when the migration picks the other. |
| Backend per-`SALE` `profit_loss` (weighted-average cost) | **Medium-High** | Already single-sourced (`:1216-1225`) and read verbatim — so the *value* is Low risk. Rated Medium-High for two reasons: (a) it is rendered **four different ways** from one field (`Math.abs` at `LicenseLedgerDetail.tsx:470`, `(P)`/`(L)` at `ledgerExport.js:207`, `Math.abs` at `:753`, signed at `LicensesTable.tsx:621`) — the on-screen view actively hides whether a number is a profit or a loss; (b) the three-way `avg_rate` fallback (per-company → license-wide → raw amount, `:1218-1225`) is genuinely order-dependent business logic that no test covers, so any refactor near it is unguarded. |

### High

| Calculation | Rating | Reasoning |
|---|---|---|
| **Per-company running balance** | **High** | The centrepiece. Triplicated identically (`LicenseLedgerDetail.tsx:339-348`, `ledgerExport.js:185-191`, `:730-740`) — that part is mechanical. What makes it High: the backend already returns a field called `balance` (`:1086…:1242`) that computes a **different number** (license-wide, date-ordered, commissions included) and **a fourth consumer renders it** (`LicensesTable.tsx:616`). So this is not "three copies of one rule" — it is *two rules wearing one name across four consumers*, with the split running along a line nobody documented. Consequences: (a) the migration cannot proceed on engineering judgement alone (see Critical, below); (b) whichever convention wins, a number changes on at least one screen; (c) the three client copies must be reproduced *exactly*, including commissions-contribute-nothing and the date-free `TXN_ORDER` sort, or the "behaviour-preserving" claim is false. |
| Company closing balance (total row) | **High** | Not a separate calculation — the terminal value of the above (`LicenseLedgerDetail.tsx:489`, `ledgerExport.js:238`, `:775`). Called out separately because it is the most-read number in the feature and it **never equals** the `available_balance` shown in the page header (`:321`), by design (`:1249-1259`), with nothing in the UI explaining the gap. Any change here will be read as "the balance is wrong." |

### Critical — blocked, not risk-managed

| Item | Rating | Reasoning |
|---|---|---|
| **Which running-balance convention is authoritative** (design doc §10 B2) | **Critical — blocking** | This is not an engineering risk that discipline can reduce; it is an unanswered business question with a live wrong answer shipping today. Two screens of the same application show different Balance columns for the same license. Both are internally consistent. Both are plausible ledger conventions (per-counterparty account vs. license-wide instrument). Choosing by inspection would be guessing at a financial rule, which is exactly what `MODERNIZATION_RETROSPECTIVE.md` lesson 1 warns against for new-logic work — and it is worse here, because a plausible-looking wrong choice will *reduce* the visible inconsistency while entrenching the wrong number. **No code in Phase 3D onward should be written until this is answered in writing.** |
| **`total_value`'s dual meaning** (design doc §10 B1) | **Critical to *decide*, Low to *implement*** | `:1073` sets it to `license.opening_balance` — documented at `models/core.py:280` as *"Total export CIF (credit)"*, i.e. the license's face value — when there are no trades, and to accumulated purchase CIF (`:1128`) when there are. Incentive never switches (`:1330`). One label, three behaviours. Preserving it is a two-line job; deciding what it should mean is a domain question, and until it is answered the field cannot be given a single honest name in the Display Dataset. |

### Explicitly downgraded

| Item | Prior suspicion | Actual rating | Reasoning |
|---|---|---|---|
| The *"fixes the '–' bug"* history | Suspected evidence that the backend's `balance` is wrong or incomplete — a Category B correctness issue | **Low — Category A** | Reading the comments in full (`ledgerExport.js:164-168`, `:722-729`) shows the bug was a removed helper, `computeBalanceMap`, keying a `Map` by transaction **object reference** while `groupByCompany` (`:103-116`) re-normalised into fresh objects — so every lookup missed and the Balance column rendered `fmtNum(0)` → `'-'`. A pure client-side object-identity defect, fixed by inlining, regression-tested at `ledgerExport.test.ts:122-176`. `computeBalanceMap` no longer exists anywhere in `frontend/src`. **The backend is not implicated.** The High/Critical ratings above stand on their own evidence and do not depend on this history. <br><br>Residual note: the same object-identity pattern survives at `LicenseLedgerDetail.tsx:340` (`Map<LedgerTransaction, number>`). It is **correct** there — `groupTransactionsByCompany` (`:111`) pushes original references — but it is untested and one refactor away from reproducing the bug. Deleting it in Phase 3E removes the hazard permanently. |

---

## 2. Risk by phase

| Phase | Risk | Dominant factor |
|---|---|---|
| 3A Research | None | — |
| 3B Business decisions | None to the codebase; **highest schedule risk** | The whole migration is blocked on it. If the domain owner is unavailable, 3C can still proceed — it is the only phase that can. |
| 3C Characterization tests | **Low** | Only behaviour change is the `items` sort (C9). Highest *value* per unit of risk in the plan. |
| 3D Backend dataset | **Medium** | Additive, one file. Watch payload growth on the list page's N-parallel bulk fetch (`LicenseLedger.tsx:466-472`). |
| 3D.parity canary | None | Skipping it is the risk, not running it. |
| 3E Page cutover | **Medium** | First user-visible commit. Guarded by 3C.3 if 3C was done properly. |
| 3F PDF cutover | **Medium-High** | Zero prior test coverage on `buildPdfBody`; shared file with an out-of-scope page. |
| 3G Excel cutover | **Medium** | Same shared file, but one real test exists (`ledgerExport.test.ts:122`) and must pass **unmodified**. |
| 3H.1 `LicensesTable` | **Medium**, or **High** if B2 rules for per-company | Changes a number on a screen outside the stated scope. Flag before shipping. |
| 3H.2 Bulk-export regression | **High** | Verification-only, but the failure mode is a broken bulk export on a page this migration never intended to touch. Must gate 3F/3G. |
| 3I Cleanup audit | **Low** | Skipping it is the risk — see `MODERNIZATION_RETROSPECTIVE.md` lesson 2, where an additive migration reintroduced the duplication it existed to remove. |

---

## 3. Failure modes worth pre-writing tests for

Ordered by how quietly they fail.

1. **Backend `company_running_balance` differs from the client's by the
   commission amount.** Silent; only visible on licenses that have
   commissions. → Fixture with `COMMISSION_PURCHASE` *and* `COMMISSION_SALE`,
   asserting the backend value equals the *client's* (commission-free)
   figure, not the arithmetically "correct" one.
2. **Group keys diverge without values diverging.** `unknown-${index}`
   (`ledgerExport.js:109`) vs whatever Python produces; `String(company_id)`
   vs `str(company_id)`. → Compare by numeric value in the parity canary,
   assert key format separately.
3. **The Summary sheet rolls up across licenses instead of per license** once
   its inputs move server-side. Invisible on the detail page (always one
   license) and wrong on the list page's bulk export. → 3H.2's multi-license
   fixture with overlapping companies.
4. **Ordering drifts.** The client's `TXN_ORDER` sort has no date component;
   the visible chronology comes from the backend's own `order_by` surviving a
   stable sort (`ledger_pdf.py:1053,1067`). A backend reorder that looks
   harmless changes every displayed running balance. → Assert row order
   explicitly, not just per-row values.
5. **A new backend field ships with no reader.** Exactly the Item Pivot
   `effective_planned_quantity` failure. → 3I's grep-every-new-field audit
   plus a loud regression test.
6. **A zero-balance row starts rendering `0.00` in exports** where it used to
   render `-` (`ledgerExport.js:122`). Cosmetic, but it *looks* like the
   original '–' bug returning, in reverse, and will be reported as one. →
   Pin `fmtNum(0) === '-'` explicitly in 3C.3.

---

**No source files were modified in producing this document.**
