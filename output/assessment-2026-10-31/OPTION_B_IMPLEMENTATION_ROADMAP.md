# Option B implementation roadmap

Complete Option A phases 0-6 first. Then:

| Phase | Scope | Likely days | Exit |
|---|---|---:|---|
| B1 | Accounting discovery, CA decisions, CoA/period/entity design | 25 | signed accounting policy/data map |
| B2 | Journal/voucher, invariants, audit/reversal/period controls | 120 | balanced immutable postings |
| B3 | Source bridge, AR/AP, receipts/payments/opening balances | 75 | subledgers reconcile to controls |
| B4 | Bank statements/matching/reconciliation | 80 | audited close/reopen and difference control |
| B5 | Cutover, parallel reconcile, optional tax/Tally/advanced reports | 130 | signed opening/cutover evidence |

Never combine tenant/restriction and ledger schema changes in one deployment.
