# Accounting scope and gap analysis

## Current capability

Commercial invoice models (`license/models/invoice.py:53-253`), trade payments (`trade/models.py:650`) and trade invoice documents exist. Searches found no `JournalEntry`, chart of accounts, trial balance, bank statement/transaction, double-entry posting or accounting-period model/service. Existing reports describing purchase/sale profit are historical evidence, not proof of a general ledger.

## Required foundation (P1)

Build company/tenant-scoped chart/accounts, accounting periods, draft/approved/posted vouchers, immutable balanced journal and lines, references/idempotency keys, reversals, locks, opening balances, ledger/trial balance and source-event bridges for invoice/payment/trade/bank events. Invariant: every posted entry has sum(debits)=sum(credits) under a documented currency/rounding policy; corrections are reversals, not overwrites.

| Capability | Current | Required acceptance |
|---|---|---|
| Sales/purchase documents | Partial commercial documents | Post exactly once to AR/AP and GL; amendments/reversals preserve history. |
| Receivables/payables | Trade payments only | allocations, partials/advances/unallocated cash, ageing and statements reconcile to GL. |
| Tax | Fields exist; policy unverified | GST/TDS rules approved by qualified Indian tax adviser and tested by period. |
| Statements | No GL evidence | trial balance, P&L, balance sheet derive from posted journals only. |
| Tally migration | Not evidenced | approved mapping, opening reconciliation, exception report and rollback. |

Tax statutory treatment and export treatment are domain/tax decisions, not conclusions of this audit.
