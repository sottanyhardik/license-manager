# Bank reconciliation scope

## Current state

`apps/reconciliation` is a BOE/invoice/allotment reconciliation domain (`reconciliation/models.py:1-359`, `views.py:1`) with notes/logs/partial allocations and locking. It documents no automatic matching. No bank statement, bank transaction or bank reconciliation route/model was discovered. Therefore bank reconciliation is **missing scope**, not a failed existing feature.

## Required connected workflow

1. Import CSV/XLSX first; add bank-specific adapters only after sample validation. Preview mappings, parsed dates/debit-credit, balances, duplicate fingerprints/errors and immutable import history.
2. Persist canonical statement and transaction records with company/bank account, source row, normalised description, reference, value date, amount/currency/balance and matching state.
3. Suggest deterministic matches using amount/date/reference/counterparty/invoice; show confidence/reason. Ambiguity requires manual review.
4. Support one-to-many, many-to-one, partial, charges, interest, transfers, unknowns, adjustments and linked accounting postings. Matching is distinct from posting.
5. Completion shows statement/book opening/closing, matched/unmatched debits/credits, outstanding items, adjustments and difference under a documented convention; completion/reopen/unmatch are auditable and concurrency-protected.

Acceptance tests: exact reconciliation, missing book/statement item, duplicate import/row, partial/split/combined payment, charges, bad date/amount/reference, reversal, currency/opening/closing mismatch, override/unmatch/reopen and concurrent reviewers.
