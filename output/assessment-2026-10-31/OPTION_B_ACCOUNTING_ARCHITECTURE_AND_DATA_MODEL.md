# Option B accounting architecture and data model

Bounded context: Tenant -> LegalEntity -> Chart/Account -> AccountingPeriod -> Voucher -> immutable JournalLines -> Subledger Allocation -> BankAccount/Statement/Transaction/Match.

Invariant: every posted voucher has total debits equal total credits under a documented Decimal/currency policy. States are draft, approved, posted, reversed/cancelled; posted lines are immutable and corrections use reversal. Every source record has one idempotency reference; every journal/match is entity scoped and audited.

Bank flow: CSV/XLSX batch -> validate/map/preview -> normalized fingerprinted transaction -> deterministic suggestion -> manual split/combine/unmatch or controlled missing-book entry -> reconciliation close/reopen audit. GST/TDS/export tax and Tally mappings require CA-approved rules; they are not inferred from existing fields.
