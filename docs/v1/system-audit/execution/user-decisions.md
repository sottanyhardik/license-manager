# User decisions

Answers from the product owner, recorded verbatim or in close paraphrase, with the interpretation and the decision ID. An answer is only a decision once it is recorded here. Nothing is inferred from silence.

Decision IDs use the form `UD-###`. Owner-approved items already recorded before this interview are listed first.

## Previously approved (as stated by the owner in the audit brief, 2026-11-01)

### UD-001 — Owner D1: company access

- **Owner's words (brief):** There is no company-only data-isolation policy. Appropriately authenticated users with authorised roles may access eligible records across companies. Preserve role-based permissions, authentication and object-level security. Do not impose company-only access restrictions.
- **Interpretation:** Multi-company visibility is governed by role. Object-level security stays. No company-scoping is added.
- **Source in repo:** Consistent with `execution/unresolved-decisions.md` DEC-05 and with the owner-packet recommendation A. The repo's own record calls the decision resolved by the owner. It does not contain the owner's wording about object-level security, so that wording is recorded here, not elsewhere.
- **Status:** CONFIRMED (approved by owner in brief). Repo record update required: `decisions-required.md` D1.

### UD-002 — Owner D2: available licence balance

- **Owner's words (brief):** Available balance = allotted entitlement − unbilled BOE utilisation − billed utilisation. When a BOE is billed, its utilisation moves from unbilled to billed without being deducted twice. Example: allotted ₹500,000; unbilled BOE ₹100,000; available ₹400,000. Bill the same BOE for ₹100,000; available remains ₹400,000.
- **Interpretation:** A BOE's utilisation is counted once, whether unbilled or billed. Billing it moves it between two buckets; it does not reduce the balance again.
- **Source in repo:** Not present in the repo. The repo's D2 is a different question (Customs vs Financial engines; `decisions-required.md`). Code verification is in progress (Agent 06). Whether the owner's rule covers both engines is open (Q-005).
- **Status:** CONFIRMED as owner-approved. Code conformance: the owner's worked example passes on all three engines when the BOE is billed at its full amount through the legacy tag or a formal allocation. The principle does NOT hold in the financial engine for three cases: a sale with no BOE link (ISS-019), a partial billing (ISS-020), and unbilled sibling rows (ISS-021). Per the audit rules, this is new evidence that conflicts with an approved decision. The owner must be asked whether to reconsider it. The rule has not been changed. Scope relative to the two engines OPEN (Q-005).

## Answers from this interview

### UD-003 — Null DFIA definition (answer to Q-001, 2026-11-01)

- **Owner's words:** "Null DFIA is if license balance_cif is less than $200 everywhere."
- **Interpretation:** A licence is Null DFIA when its `balance_cif` is below 200. The threshold applies to every place the term is used (list filter, stored flag, signal, validation, sync, maintenance script, reports and dashboard). This matches option A in Q-001. The "Missing DGFT — require data entry" meaning on the dashboard is not mentioned in the answer and is treated as the same Null DFIA concept until the owner says otherwise (see Q-012 queued below).
- **Taken to mean:** `balance_cif` is the "Balance CIF" value the licence list shows (`get_balance_cif` = `calculate_financial_balance`, `backend/apps/license/models/core.py:330–349`). This is the live figure, not the stored flag. Confirm this with the owner if the stored field is meant.
- **Currency:** CONFIRMED in UD-004 (US dollars).
- **Dependencies:** `balance_cif` is computed by the financial engine, which has open defects ISS-019 to ISS-021. Any Null DFIA count changes if Q-016 changes the engine.
- **Status:** ANSWERED. Currency confirmed (UD-004). Consumer changes not yet approved for implementation.

### UD-004 — Currency of the Null DFIA threshold (answer to Q-011, 2026-11-01)

- **Owner's words:** "its A" — in reply to the options "A. US dollars ($)" and "B. Indian rupees (₹)".
- **Interpretation:** The 200 threshold is in US dollars, the same unit as `balance_cif`. The brief's ₹ wording is superseded for this threshold.
- **Status:** CONFIRMED.

### UD-005 — Owner's stated available-balance formula (answer to BD-01, PROVISIONAL, 2026-11-01)

- **Owner's words:** "total qty − (allotted qty without BOE − BOE without bill − invoice)".
- **Interpretation:** Not final. As written, the minus signs inside the bracket add back BOE and invoice amounts, which gives results above the entitlement (for example 150 for a direct BOE of 50, against an expected 50). The intended rule is most likely: available = total − allotted-without-BOE − BOE-without-bill − invoice, with every term subtracted. Tested against all ten rows of `DFIA_BALANCE_FORMULAS_AND_EXAMPLES.md` §8.2, that reading matches every row. It is the reservation rule (BD-01 option A), and it does not match UD-002.
- **Status:** ANSWERED, PROVISIONAL. Follow-up question on the signs is open. Not CONFIRMED. UD-002 is not changed by this entry.

### UD-006 — Invoice quantity and CIF focus (answer to BD-04 and BD-10, 2026-11-01)

- **Owner's words:** "in invoice we focus on cif fc more then quantity if the quantity is 0 in invoice take that from linked boe".
- **Interpretation:** (a) For an invoice, the quantity is taken from the invoice. If the invoice quantity is 0, the quantity comes from the linked BOE. (b) CIF in foreign currency is the main value for invoices, with quantity secondary. The word "more" is not defined; how the CIF FC and quantity checks interact is still to be confirmed.
- **Status:** ANSWERED. Rule (a) is clear. Rule (b) is recorded but its meaning is open. No change until confirmed.
