# Licence Overview — Layman-Friendly UI Design

Status: **Design only. No UI code was changed in this stage.** The design is based on the current screen (`/licenses/2583/overview`), the reconciliation in `licence-2583-transaction-reconciliation.md`, and the open questions in `licence-2583-business-questions.md`. Implementation waits on the decisions that change the figures, but the layout, wording and status system below do not depend on them and can be built first.

Currency: every amount on this screen is shown in **USD** with the label "USD" (or "$" with a legend on first use), never "₹" unless the amount is actually INR. Indian digit grouping stays.

---

## 1. Principles

1. **Four answers first.** The first screen answers: what did the licence start with, how much is used, how much is reserved or invoiced, and how much is left.
2. **The top figures add up.** Every line in the summary is a line in the calculation below it. A user can check the arithmetic with a calculator.
3. **Say what is not known.** A figure whose basis is open is labelled, not hidden. Two systems agreeing on a number is not the same as the number being verified.
4. **No internal names on the main screen.** "Balance Engine", "Customs Ledger", "Financial Ledger", "Debited CIF" and similar terms move to Advanced Details.
5. **Every number leads to its records.** Each figure expands to the BOEs, invoices or items behind it.

---

## 2. The first screen

### 2.1 Header

- Licence number, importer, licence status (Active / Expired), expiry date.
- Status pill for the whole licence (section 5), with one line of explanation: for licence 2583, **"Balance under review: 3 open questions"**.
- Actions: Edit · Download PDF · Download Excel. Secondary: View copy, Recalculate (moved into Advanced Details).

### 2.2 Six summary cards

| Card | Figure (2583, current) | Source | Helper text |
|---|---:|---|---|
| Original licence value | 6,15,999.98 USD | Import items' authorised CIF | "What the licence was issued for." |
| Used through BOEs | 1,82,856.60 USD | BOEs for this holder's sales | "Goods cleared at customs against this licence." |
| Used before transfer | 21,669.77 USD | Hidden BOE 27622 | "Usage recorded before the licence was transferred to you. Pending confirmation." (shown only while Q-05 is open) |
| Reserved for customers | 0.00 USD | Allotments not yet cleared | "Promised to customers, not yet cleared." |
| Invoiced, BOE not linked | 4,09,560.00 USD | Sales with no BOE | "Sold, but no bill of entry is linked. Needs review." |
| Balance available | 1,913.61 USD | Original − all of the above | "What you can still use." |

Layout: six equal cards in a 3 × 2 grid at 1440 px and wider, two columns on tablet, one on mobile. The balance card carries the status pill. Over-utilised balance: the card turns to the over-utilisation style (section 4), shows the negative value, and states the amount over.

### 2.3 Plain-language summary

Generated from the same figures, so the words and the numbers cannot drift apart:

> Your licence was issued for **USD 6,15,999.98**.
> **USD 1,82,856.60** has been used through bills of entry.
> **USD 0.00** is reserved for customers.
> **USD 4,09,560.00** has been invoiced but has no linked bill of entry. This needs review.
> In total, **USD 5,92,416.60** is used or reserved, plus **USD 21,669.77** used before transfer (pending).
> **Balance available: USD 1,913.61.** This figure is under review.

Each sentence has an information icon that explains the term in one line.

### 2.4 The calculation, collapsed by default

```
Original licence value                    6,15,999.98
  Less: used through bills of entry      −1,82,856.60   [view 7 BOEs]
  Less: used before transfer               −21,669.77   [view BOE 27622]   (pending)
  Less: reserved for customers                   0.00   [view 0 allotments]
  Less: invoiced, no bill of entry        −4,09,560.00   [view 2 invoices]  (needs review)
  ─────────────────────────────────────────────────────
  Balance available                          1,913.61
```

Each bracketed link opens the supporting records in place. The sum is checked by the software and shown as "✓ adds up" only when it is true.

---

## 3. Terminology

| Current label | New label | Helper text (shown as ⓘ) |
|---|---|---|
| Balance CIF / Balance Engine | Balance available | "What you can still use under this licence." |
| Total CIF | Original licence value | "The amount this licence was issued for." |
| Debited CIF | Used through bills of entry | "Goods cleared at customs against this licence." |
| Allotted CIF | Reserved for customers | "Promised to customers and not yet cleared." |
| Planned CIF | Planned usage | "Amount you have planned to use under this licence." |
| Customs Ledger | Import usage history | "Each bill of entry and how it reduced the balance." |
| Financial Ledger | Licence transaction history | "Every purchase, sale and bill of entry in date order." |
| Reconciliation Difference | Difference requiring review | "Two sources disagree. Open the details to see why." |
| Previous Owner Utilisation | Previous owner's usage | "Usage recorded before this licence was transferred to you." |
| Hidden BOE | Usage before transfer | as above |
| Total BOEs | Bills of entry | |
| Individual Item CIF toggle | Show by item | "Break the balance down by product line (SR)." |
| Recalculate | Refresh figures | Advanced Details only |

Technical terms (CIF FC, SR, running balance, computed balance, engine balance) stay in Advanced Details, where a short definition sits beside each.

---

## 4. Status system

Five statuses, each shown as a pill with an icon **and** text (never colour alone).

| Status | Meaning | Rule | Shown as |
|---|---|---|---|
| **VERIFIED** | Every component matches its supporting records and no open question touches the figure | Recomputed D-1 equals the displayed balance, every source row reconciles, no open question | Green, ✓ |
| **REVIEW REQUIRED** | Figures reconcile arithmetically but one or more inputs are unconfirmed | At least one open question (Q-02, Q-03, Q-04, Q-05) affects a component | Amber, ⚠ |
| **MISMATCH** | A displayed balance differs from the recomputed calculation | Displayed ≠ recomputed D-1 by more than 0.01 | Red, ✕, with the difference |
| **OVER-UTILISED** | Available is below zero | Available < 0 | Red, with the excess amount |
| **UNMAPPED ITEM** | A transaction exists but its product line cannot be identified | BOE or invoice row with no HS code or item mapping | Grey, ? |

Rules:

- Two services returning the same stored figure is **not** VERIFIED. VERIFIED requires recomputation from the source rows.
- A licence can show REVIEW REQUIRED and MISMATCH together. The mismatch is the more urgent.
- Licence 2583 today: **REVIEW REQUIRED** (Q-02, Q-03, Q-04, Q-05). The Financial Ledger's 4,01,583.40 is a **MISMATCH** against the recomputed 1,913.61 until Q-07 is settled.

---

## 5. Financial Ledger (layman view)

Shown as a tab, not the first screen. The default columns:

| Date | What happened | Reference | Amount | Balance after | Status |

- "What happened" uses the terms in section 3: "Licence purchased", "Sold — matched to bill of entry", "Sold — no bill of entry", "Bill of entry (used before transfer)".
- Currency columns (CIF USD, CIF INR) are removed from the default view. They appear in Advanced Details, and each blank cell says why: "No INR basis recorded" (Q-04).
- Multi-BOE invoices: one row per invoice, with the BOEs listed. The per-line "Requires manual review" text is replaced by a single note: "Matched to 3 bills of entry in total; per-line split not recorded."
- The closing row states the figure and its status. It must equal the last row's balance; if it does not, the row is shown as MISMATCH (RC-2).

Column count at 1440 px: six. Horizontal scrolling is not required for the default view.

---

## 6. Other tabs

Each tab keeps its existing API. Consistent structure: a one-line summary, the table, empty state, error state, and "Show all" where paging applies.

- **Bills of entry**: Number · Date · Product line · USD · INR · Linked invoice · Status (matched / hidden / unlinked).
- **Allotments**: Customer · Reserved · Cleared by BOE · Still reserved · Status.
- **Invoices**: Invoice · Date · Customer · USD · Linked BOE · Status (matched / not linked / needs review).
- **Items**: SR · Product · Authorised CIF · Used through BOEs · Invoiced without BOE · Balance · Status. Item balances are shown only once Q-06 is settled; until then the tab says so.
- **Planning**: unchanged in this stage.
- **Documents and history**: unchanged in this stage.

---

## 7. Advanced Details (collapsed, authorised roles)

- Import and BOE details (SR, HS code, FC, INR, exchange rate).
- Customer reservations.
- Invoices without BOE.
- Item-wise usage.
- Transaction history with canonical and engine values side by side.
- Previous-owner history.
- Reconciliation: each component with its source rows and status.
- Audit history.
- Definitions of technical terms.
- "Refresh figures" (formerly Recalculate).

Visibility follows the existing permission classes (`LicensePermission`, `LicenseBalanceLedgerPermission`). This design adds no new permission.

---

## 8. Over-utilisation presentation

- Card: red border, negative value shown in full (e.g. −15,000.00 USD), label "Over-utilised by 15,000.00 USD".
- Breakdown: the balance line is red and the arithmetic still adds up.
- Never a progress bar that stops at 100%. Use a split bar with a marker at 100% and an overflow segment, or no bar at all. The text figure is always present.
- Tooltip and text: "More CIF has been used than the licence was issued for. Review the bills of entry and invoices listed below."

---

## 9. Layout defects to fix (from the 1440 px capture)

| # | Defect | Fix |
|---|---|---|
| L1 | Tab strip partly hidden under the header card | Put the tabs in their own row below the header with a clear margin |
| L2 | Financial Ledger table wider than its card; "CIF INR" clipped | Default six columns; detail columns in Advanced Details; `overflow-x: auto` inside the card only if still needed |
| L3 | Ledger row 2 renders as an oversized empty block | Remove the fixed height on the opening rows; let rows size to content |
| L4 | Floating action bar covers table content | Add bottom padding equal to the bar's height on the overview page |
| L5 | Internal labels on KPI cards | Use section 3 labels |
| L6 | Card padding leaves large empty areas in the financial cards | Equal-height cards, label top-left, figure, helper text, status |

Responsive plan: 1920 and 1440 px, six cards in three columns (two rows). 1280 px, three columns. 1024 px, two columns; ledger shows six columns. 390 px, one column; the ledger becomes a list of cards (date, what happened, amount, balance, status), not a horizontally scrolling table.

---

## 10. Accessibility

- Status pills carry text and an icon, not colour alone.
- Amounts right-aligned with tabular numerals.
- Every information icon is a button with an accessible name and a visible tooltip on focus.
- The breakdown is a real table (or definition list) so screen readers announce the components in order.
- Keyboard: the calculation's "view records" links are reachable in tab order, and each opens in place with focus returned on close.

---

## 11. What can ship now, and what waits

**Can ship now, independent of the open questions:**
- Terminology (section 3) and helper texts.
- Layout defects L1–L6.
- Card structure, status pill component, breakdown component (values filled from the current engine, with the REVIEW REQUIRED status set by the open-question list).
- Currency labels.

**Waits for decisions:**
- Any value that changes: the balance (Q-02, Q-03, Q-04, Q-05), the Financial Ledger total (Q-07), item balances (Q-06), previous-owner classification (Q-01).
- Removing the "Used before transfer" line (depends on Q-05).

---

## 12. Acceptance criteria for this screen

- A non-technical user can state the balance available and what is used, reserved and invoiced, without opening Advanced Details.
- Every figure on the first screen links to its records.
- The summary arithmetic is correct to the paisa and shown as checked.
- No internal term appears on the first screen.
- Licence 2583 shows REVIEW REQUIRED, not VERIFIED, until its open questions are answered.
- The page has no horizontal overflow at 1440 px or 1024 px in the default view.
- Status is communicated by text and icon, not colour only.
