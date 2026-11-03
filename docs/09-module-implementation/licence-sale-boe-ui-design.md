# Licence Sale ↔ BOE — UI Design

Status: **Design only. No UI code changed.** Built on the calculation breakdown the canonical service will return. Until that service is wired in, the screens can show the current engine figures only where they match the rule, and must label the rest "under review".

## 1. Licence summary

Example, showing the rule's components. Figures in USD.

**Original licence value:** $1,000

| Description | Amount |
|---|---:|
| Sold to customers | $500 |
| Reserved for other customers | $0 |
| BOEs not covered by any sale or allotment | $30 |
| **Total used** | **$530** |
| **Available licence value** | **$470** |

Explanation, in plain language:

> Your licence originally had $1,000. You sold $500 to a customer. The bills of entry linked to that sale are already included in the $500, so they are not deducted again. A further bill of entry of $30 is not covered by any sale, so it is deducted separately.

Rules for this block:
- Every line links to its records.
- The total equals the sum of the lines above it; the software checks the arithmetic and shows "✓ adds up" only when true.
- Quantity is shown in its own block with its own unit. It is never shown as a derivative of CIF.
- Until the quantity unit is confirmed (decision D-4), quantity shows as "Not yet reliable" rather than a number.

## 2. Customer sale detail

For each sale:

| Description | Amount |
|---|---:|
| Sold to customer | $500 |
| Used by customer through linked BOEs | $190 |
| Customer balance remaining | $310 |

Required label under the table:

> The customer balance is not the same as your licence balance. Your licence balance is $500 because the full $500 was transferred to the customer when the sale was recorded.

Actions: open the sale invoice; open each linked BOE; link a BOE; unlink a BOE (with a confirmation that states the effect on the available balance).

## 3. BOE status labels

| Label | Meaning | Shown when |
|---|---|---|
| Covered by sale | Entire BOE amount is within a sale's entitlement | Allocated = BOE amount |
| Partially covered | Part within a sale, part uncovered | 0 < allocated < BOE amount |
| Uncovered BOE | Not within any sale; reduces available | Allocated = 0 |
| Covered by allotment | Within an active allotment reservation | Allotment term (not yet in this rule) |
| Over-linked | Linked amount exceeds the sale; excess counted | Linked > sale |
| Unmapped item | Item cannot be identified confidently | HS code / item mapping missing |
| Requires review | An open decision affects this row | Any of D-1 to D-10 applies |

Each label has an icon and text. Colour is not the only cue.

## 4. Sale-level status

| Label | Meaning |
|---|---|
| Not linked | No BOE yet; full amount still reserved |
| Partly linked | Some BOE linked; remainder awaiting BOE |
| Fully linked | Linked equals sale |
| Over-linked | Linked exceeds sale; warning |

## 5. Over-utilisation

When available is below zero:
- Show the negative value in full, with the label "Over-utilised by $X".
- Do not show a progress bar that stops at 100%.
- The balance card has a red border and an icon. The text is the primary cue.

## 6. Drill-down

Every figure opens its source transactions: sale invoice numbers and dates, BOE numbers and dates, item (SR) and quantity, and the allocation records behind any covered amount.

## 7. Wording rules

- Use "used", "reserved", "available" and "customer balance". Avoid "debit", "CIF utilisation" and "reconciliation difference" on the main screen. Keep them in advanced details with short definitions.
- Use "USD" unless the amount is in INR.
- Do not present an open item as settled.

## 8. Permissions

Actions follow the existing permission classes. Link and unlink require the same role as the existing BOE and allotment actions. This design adds no new permission.

## 9. Not yet implemented

Everything in this document. The screens depend on:
- the canonical service (not wired in);
- the allocation API (not created);
- decisions D-1 to D-4 (for the over-link warning, cross-item handling, BOE display order, and quantity).
