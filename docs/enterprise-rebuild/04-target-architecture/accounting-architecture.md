# Accounting architecture

Accounting is a new controlled domain, not a relabelled version of operational reconciliation. It starts after company scope and operational source-event contracts pass acceptance.

Required boundaries: company/financial period, chart of accounts, journal header/lines, source-posting key, customer/supplier subledgers, receipts/payments, commissions, bank statement/matches and statement read models.

Invariants: posted journal debits equal credits under approved precision/currency policy; source event posts at most once; a posted entry is corrected by reversal/replacement; no posting into a closed period; company books cannot mix; reports derive from posted entries; bank matching preserves imported source evidence. CA approval is required for chart, opening balances, tax, periods and cutover.

