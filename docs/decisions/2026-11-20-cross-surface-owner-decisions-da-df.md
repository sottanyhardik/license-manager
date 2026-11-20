# Owner decisions D-A … D-F — cross-surface reconciliation (2026-11-20)

Context: `docs/reports/cross-surface-reconciliation-2026-11-20.md` §4, §6 and §8. The owner decided these interactively on 2026-11-20.
**BUSINESS-RULE CHANGE (approved, not yet implemented).** Each one needs a characterisation test first, then the
cif-balance-auditor (Opus) review.

| # | Decision |
|---|---|
| **D-A** (RC4a/RC4b) | Item available CIF = item-attributed value **only when `individual_item_cif_override` is on**, otherwise the licence balance; in both cases **capped at `max(licence balance, 0)`**. No item may show more than the licence has. Applies to the Item Report, `min_balance`, the PDF item balance, the allotment available-items list and `sion_rule_engine`. |
| **D-B** | In override mode, the per-item allotment, BOE and trade caps (`calculate_item_balance`) = `min(item cap, max(licence balance, 0))`. |
| **D-C** (RC16) | Enforce the %-condition pool at allotment allocation: cap = `min(item cap, remaining pool value, max(licence balance, 0))`. Over-pool allotments are rejected with a clear message. |
| **D-D** (RC3/RC4b) | Screens show **live** values. This covers the Import Items tab, Item Report, `min_balance` and the PDF, using bulk maps with no N+1. API field names stay the same; the values change to the live figures. Stored columns stay as a cache with **one writer** that uses the D-A formula, so the signal and `update_balance_values` are unified. |
| **D-E** (RC7) | The pivot includes licences with a NULL purchase status in an **"Unassigned"** group by default, and the status filter gains an "Unassigned" option. `min_balance`: Item Report filters on the live (D-A-capped) item available value; the pivot keeps the live licence balance. Each is labelled. |
| **D-F** (RC13/RC5) | One available-qty formula: `qty − debited − outstanding allotted − direct sale`, floored at 0, Decimal, shown to **3 dp** on every screen, in Excel and in the PDF. This removes the whole-unit floor and the snapshot variant without direct sale. |

**Approved, no rule change:** RC2/RC11 labels (Overview "Opening / prior-owner adjustment" and Billed line; Import Items
footer shows the licence-level CIF ceiling) · RC14 + N2 (PDF Total CIF = `calculate_credit`, real components, a real
check that can fail) · RC15 (Item Report Excel date cells, Decimal rows and sums) · N1/N4 (PDF item Balance CIF = D-A
value, item Debited CIF = canonical non-hidden Decimal, units normalised to `kg`). N3 (the dead guard) is resolved by D-A
and D-D.

**RC12:** produce a data-review list (Excel/CSV) for the owner. No automatic data change.

Unchanged: the licence-level canonical CIF rule (`business-rules.md`), the signed balance with `is_over_utilised`, and
the customs and financial engines staying separate.
