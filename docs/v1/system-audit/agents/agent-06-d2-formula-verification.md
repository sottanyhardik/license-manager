# Agent 06 — Owner D2 available-balance rule versus code (static)

Date: 2026-11-01. Method: read-only. Code index consulted first. Source lines cited below were re-checked in the lead session for: `calculate_trade` (`balance_calculator.py:1063–1088`), the linked-BOE exclusion (`:339–352`), `calculate_balance` (`:1395–1404`), `calculate_financial_balance` formula (`:1643–1649`), and the snapshot's customs field (`backend/apps/license/services/balance_snapshot.py:150–158`). No test or runtime check was run. Recorded as static verification only.

## Owner rule (quoted, owner wording)

"Available balance = Allotted entitlement − Unbilled BOE utilisation − Billed utilisation. When a BOE is billed, its utilisation moves from unbilled to billed without deducting it twice. Example: allotted entitlement ₹500,000; unbilled BOE ₹100,000; available balance ₹400,000. Bill the same BOE for ₹100,000 → available balance remains ₹400,000."

This rule is different from the repo's D2 (Customs vs Financial engines, `docs/v1/00-executive-overview/decisions-required.md`). It is tested here as written.

## Current formulas

| Output | Formula | Evidence |
|---|---|---|
| `calculate_balance` | max(0, Credit − (raw non-hidden BOE debit + outstanding allotment)). Billing state and sales are not considered. | `balance_calculator.py:1397–1401` |
| `calculate_customs_balance` | max(0, Credit − (raw non-hidden BOE + hidden BOE + allotment)). Sales not included. | `:1406–1431` |
| `calculate_financial_balance` | max(0, Opening + Purchase − Sale − Debit − Allotment) | `:1582–1651`, formula `:1643–1649` |
| Sale (`calculate_trade`) | Sum of every SALE line `cif_fc` on the licence, "regardless of BOE status" | `:1063–1088` |
| Debit (`calculate_debit`) | Sum of `contributed` per DEBIT row. A row linked to a represented BOE with `allocated == 0` contributes 0. | `:459–509`, linked case `:339–352` |
| Snapshot `customs_balance` | = `calculate_balance_for_licenses` (hidden excluded) | `backend/apps/license/services/balance_snapshot.py:156, 229, 252` |
| Snapshot `customs_available_balance` | = `calculate_customs_balance_for_licenses` (hidden included) | `balance_snapshot.py:179, 233, 264` |
| `get_balance_cif` (user-visible "Balance CIF") | = `calculate_financial_balance` | `backend/apps/license/models/core.py:330–349` |

## Worked example trace (owner's figures)

| Step | Engine | Result |
|---|---|---|
| Allotted 500,000; unbilled BOE 100,000 | all three | 400,000 (reading A: licence credit is the entitlement) |
| BOE billed for 100,000 via legacy trade tag or formal allocation, equal amounts | `calculate_balance`, customs: billing ignored | 400,000 |
| Same, financial engine | sale 100,000 subtracted, BOE linked so debit 0 | 400,000 |
| Sale line for the goods, **no BOE link** | financial: debit 100,000 and sale 100,000 both subtracted | **300,000 — DIVERGES** |
| Billed 60,000 against BOE of 100,000 (legacy tag) | financial: whole row excluded, sale 60,000 subtracted | **440,000 — DIVERGES** |
| Two rows of one BOE, one billed 60,000 (formal allocation), sibling 50,000 unallocated | financial: 400,000; principle total 350,000 | **DIVERGES** |

The owner's example, read literally, passes on all three engines. The principle ("each BOE utilisation deducted once, whatever its billing state") is not implemented in the financial engine when the billed amount or the link differs from the BOE.

## Findings

| ID | Finding | Severity | Confidence | Evidence |
|---|---|---|---|---|
| F1 | A sale line with no BOE link double-deducts in the financial engine (BOE as debit and as sale). | High | High on code path; UI reachability not verified | `balance_calculator.py:1063–1088`, `:339–352`, `:1643–1649`. `LicenseTradeLine` has no BOE foreign key (`apps/trade/models.py`); the only link is `LicenseTrade.boes`. The ledger self-check (`license_balance_ledger_builder.py:663–685`) uses the same engine and cannot detect it. |
| F2 | When the billed amount is below BOE CIF, the unbilled remainder is dropped (financial). | High | High on code | `:341–352`, `:447–455`; comment at `:160–162` says discrepancies are "never a second debit". |
| F3 | Unbilled sibling rows of a partly billed BOE are dropped (financial). Documented as a "KNOWN, ACCEPTED TRADE-OFF". | High | High on code | `:294–352`; docstring `:231–241`. Conflicts with the owner's rule as stated. |
| F4 | Allotment is fully zeroed for the whole item when any BOE is linked to its parent allotment. | Medium | High on code | `:798–800`, `:825–826`, `:834–840`; docstring `:732–738` says intended. Remainder of a partly realised allotment disappears. Pre-link double count acknowledged at `:745–756`. |
| F5 | Two SALE trades tagged to the same BOE both subtract their amounts (financial). | Medium | Medium (write-path validation not read) | `:1083–1088`; represented set dedupes BOE ids only (`:199–207`, `:288–289`). |
| F6 | AR-type allotments included at licence level, excluded at item level. | Medium (inconsistency) | High on code | `balance_calculator.py:865` (no type filter), `:919`, `:957` (AT only), `:906–909` comment vs `core/scripts/calculate_balance.py:55–56`; `constants.py:22–23`. |

Not a double deduction: the Customs engine and `calculate_balance` never count sales. Billing therefore cannot double-deduct there, but it also cannot change those figures.

## Hidden (OTH / previous-owner) BOEs

The owner's rule is silent. This is an open question, not a divergence.

- `calculate_balance` excludes them (`balance_calculator.py:433–434`).
- `calculate_customs_balance` includes them (`:1426`, `:562–588`).
- The financial engine subtracts them from opening balance together with purchase (`:1527–1528`).
- The Customs ledger includes them as flagged rows (`license_balance_ledger_builder.py:849–882`).

## Why snapshot customs (93,000) and Customs ledger (63,000) disagree

Code-only explanation, on the characterization fixture (credit 100,000; visible BOE 5,000; hidden BOE 30,000; outstanding allotment 2,000):

- Snapshot `customs_balance` = 100,000 − (5,000 + 2,000) = 93,000, because hidden rows are excluded (`balance_snapshot.py:156, 229`).
- Ledger final figure = 100,000 − (35,000 + 2,000) = 63,000, because all DEBIT rows including hidden are subtracted (`license_balance_ledger_builder.py:817–822, 849–851`), checked against `calculate_customs_balance` (`:951–956`).
- The 30,000 gap is exactly the hidden BOE. The same snapshot also carries `customs_available_balance` = 63,000.

## Documentation inconsistency (non-blocking)

`docs/v1/04-domain-and-business-rules/financial-rules.md` line 9 describes the customs balance as "visible BOE debit − allotment", which matches `calculate_balance`. Line 19 describes the customs formula correctly. The same file cites a "6 passed, exit 0" run from 2026-10-31 that was not re-verified.

## Owner questions (neutral; no answer chosen)

1. What does "allotted entitlement" mean: the licence's total export CIF, the sum of allotment items, or something else? Should an outstanding (not yet imported) allotment reduce available balance?
2. What makes a BOE "billed": a sale linked to it, or any sale of the same goods? What happens when the billed amount differs from the BOE CIF?
3. When one row of a multi-row BOE is billed, should its unbilled siblings still reduce available balance? The code currently says no, as a documented decision.
4. Should a sale of BOE goods that is not linked to the BOE count as billed utilisation? Today it is a separate debit, which produces F1.
5. Do hidden BOEs reduce available balance? If so, as unbilled, billed, or an opening-balance reduction?
6. Are AR-type allotments outstanding commitments (licence-level code) or already debited (item-level comment)?
7. When a BOE is linked to an allotment, should it consume the allotment only up to its own CIF?

## Verification status

- Static only. Tests were not run. No database or runtime check.
- Not read: `exclude_hidden` internals, `InvoiceBOEAllocation` and `LicenseTrade` write-path validation, the BOE allotment picker, `apps/license/tests/test_balance_calculator.py` (may pin the accepted behaviour above).
- The owner's rule is not written in the repo; it is recorded as owner-approved in `execution/user-decisions.md` (UD-002). F1–F3 are new evidence that conflicts with the principle of that rule. Per the audit rules, the owner must be asked whether to reconsider it. This is not a change to the rule.
