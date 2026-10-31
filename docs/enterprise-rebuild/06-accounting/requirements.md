# Integrated accounting requirements - proposed scope

**Status:** New scope pending CA/business approval. Existing evidence found invoice/trade-payment concepts but not a complete general ledger, chart of accounts, trial balance, bank statement or bank transaction domain.

| Capability | Requirement | Precondition |
|---|---|---|
| Entity and periods | Company-specific chart, period/calendar, numbering and close controls | Company policy + CA decision |
| Journal | Balanced header/lines, immutable posting and linked reversal | Currency/tax/accounting policy |
| Sales/expenses/commission | Approved source event -> exactly-once posting rule | Operational invoice/trade lifecycle trusted |
| AR/AP | Party ledger, allocations, partial/unallocated receipts/payments | Party/opening-balance policy |
| Bank reconciliation | Statement import, duplicate detection, matching and audit | Bank formats/accounts agreed |
| Statements | Trial balance, P&L, balance sheet with period rules | CA-approved chart/mapping/close |

No accounting workflow is permitted to conceal a licence, BOE, invoice or migration discrepancy.

