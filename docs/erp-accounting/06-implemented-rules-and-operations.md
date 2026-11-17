# 06 — Implemented accounting rules, reconciliation, migration and testing

This is the canonical reference for what the code in `backend/apps/accounting` does today. Decisions and their
status are in `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md`.

## 1. Architecture as built

- **One engine.** `services/posting.py:post_voucher` is the only function that writes ledger lines. Trade invoices,
  expenses, payments, bank suspense, reclassification, loans, migration and manual journals all call it.
- **Entities.** `EntityBooks.pk` is the existing `core.CompanyModel` id. Books are activated for companies discovered
  from Trade (`selectors/entities.py`). There is no second company or party master; parties are `CompanyModel` rows.
- **Dependency direction.** accounting → core, trade and accounts. Trade never imports accounting; the architecture
  ratchet enforces this. Trade is read only through `selectors/trade_source.py`.
- **Integrity in three layers.**
  1. Services: validation, `select_for_update`, `transaction.atomic`.
  2. DB constraints: one-sided non-negative lines; unique idempotency key, voucher number, statement fingerprint and
     invoice number.
  3. Postgres triggers (migration 0002): posted vouchers and their lines are immutable, only POSTED → REVERSED is
     allowed, and posted vouchers must balance at commit.
- **Balances.** Every balance is a query over posted voucher lines (`selectors/ledger.py`). None is stored on trades,
  parties or bank accounts.
- **Licence CIF** utilisation is never read or written by accounting.

## 2. Voucher lifecycle

DRAFT → POSTED → (REVERSED + a REVERSAL voucher).

- Drafts never affect balances.
- Posting assigns a gap-free number `PREFIX/FY/00001` per entity, FY and type, under a row lock.
- A correction is always a reversal plus a new posting. Nothing is edited in place.
- The idempotency key is `{entity}:{source_type}:{source_id}:{event}:{version}`. Re-delivery returns the existing
  voucher.
- Period locks (`AccountingPeriod.status = LOCKED`) and closed FYs reject posting. Dates before `books_start_date`
  are rejected.

## 3. Posting rules (`services/invoices.py:voucher_lines_for`)

| Document | Debit | Credit |
|---|---|---|
| PURCHASE / EXPENSE / COMMISSION_PAYABLE | line accounts (taxable); Input CGST/SGST/IGST; round-off if positive | Party gross |
| … with TDS | Party (TDS) | TDS Payable |
| SALES / COMMISSION_RECEIVABLE | Party gross | line accounts; Output GST; round-off |
| … with TDS deducted by the customer on the bill | TDS Receivable | Party |
| DEBIT_NOTE (to a supplier) | Party | Purchase-return lines; Input GST reversal |
| CREDIT_NOTE (to a customer) | Sales-return lines; Output GST reversal | Party |
| PAYMENT | Party | Bank |
| RECEIPT (with optional customer TDS) | Bank (net); TDS Receivable | Party (gross) |
| Suspense, money in | Bank | Suspense |
| Suspense, money out | Suspense | Bank |
| Reclassify suspense | Suspense ↔ target account (party, expense, income, loan, transfer) | |
| Loan TAKEN: disbursement / accrual / repayment | Bank / Interest expense / Principal + Interest payable | Principal / Interest payable / Bank (+ TDS payable) |
| Loan GIVEN | mirror image (interest income; TDS receivable) | |

Other rules:
- Trade lines post to `PURCHASES`/`SALES`/`COMMISSION_*`. If the party ledger is intercompany, they post to
  `INTERCOMPANY_PURCHASES`/`INTERCOMPANY_SALES` instead.
- Every line of a trade invoice carries `trade_id`, which feeds trade profitability.
- GST on standalone bills uses the per-line rate. If the supplier's and recipient's GSTIN state codes are equal it
  splits into CGST and SGST, otherwise it is IGST. **Trade-linked invoices carry no GST** (Bill of Supply; AD-05,
  pending CA confirmation).
- TDS applies only when a dated `TdsSection` exists. Supported: FULL or EXCESS thresholds per party per FY, PAN
  category rates, the no-PAN rate, and lower-deduction certificates.
- Expense allocation: a line can be split across trades by VALUE (trade total) or QUANTITY (kg) using
  largest-remainder paise, so the parts always sum exactly.

## 4. Trade integration

- **Post to books** (`invoice_from_trade` → `confirm_invoice` → `post_invoice`). The invoice is linked to the trade
  (OneToOne) and never recreated.
- **Validation:** the own side has books, the party exists, a date exists, total > 0, and Σ lines = subtotal.
- **Drift.** `source_version` hashes the fields posting depends on. If the trade changes after posting, its status
  becomes `EXCEPTION`, and `resync` reverses the old voucher and re-posts. Settlements are kept, provided the new
  total ≥ the settled amount.
- **Accounting status** per trade (`selectors/trade_status.py`) is computed only from records: NOT_ACCOUNTED,
  PENDING, ACCOUNTED, PARTIALLY_ACCOUNTED (unaccounted trade payments), EXCEPTION, REVERSED.
- **Deletion guard** (`models/guards.py`). A trade with posted or reversed accounting cannot be deleted
  (ProtectedError → HTTP 400). Draft links are removed together with the trade. An accounted `LicenseTradePayment`
  is PROTECTed.
  - **Behaviour change for the existing trade API:** deleting such trades now fails, and nested payment re-sync on
    an accounted trade can no longer silently drop an accounted payment.
- **Paired trades.** A SALE posts in the seller's books and a PURCHASE in the buyer's books. A leg whose own side
  has no books cannot be posted.

## 5. Settlement

- `Settlement` rows allocate a settling voucher (payment, receipt, note, or suspense reclassification) to a posted
  bill. The bill is row-locked, and over-allocation is refused.
- Outstanding = net − Σ active settlements.
- Status is derived as UNPAID, PARTIALLY_PAID, PAID or OVERDUE (due date passed and amount outstanding).
- Any unallocated part of a payment is an advance and can be allocated later. Reversing a payment deactivates its
  settlements and bank matches.

## 6. Banking and reconciliation (`services/banking.py`)

1. **Import** a CSV or XLSX of at most 10 MB. PDF is refused with guidance.
   - The header row is detected (skipping bank preambles) through aliases, or set with an explicit column mapping.
   - Dates, amounts (Indian grouping, Cr/Dr suffixes, parentheses), and the debit/credit side (separate columns or
     amount + Dr/Cr flag) are normalised.
   - The UTR is taken from the reference column or the narration.
2. **Duplicates.** The fingerprint is sha256 of bank, date, amounts, narration, reference, balance and the
   occurrence index within the file. It is unique per bank account, so re-importing a file adds nothing.
3. **Auto-match never posts.**
   - UTR/reference first: a unique candidate whose payment reference equals or appears in the line.
   - Then an exact amount within ±7 days, where the best score is unique (date and party name are supporting
     signals).
   - Ambiguous lines stay UNMATCHED and show ranked candidates.
4. **Manual and split matching.** One line can match several vouchers, and partial matches are allowed. Each match
   is checked against the line's remainder and the voucher's unmatched bank-side amount, on the correct side.
   Unmatching keeps history (`is_active = false` plus an audit event).
5. **Suspense** posts Bank ↔ Suspense for the unmatched remainder, with a reason, owner and follow-up date. It is
   resolved by one of:
   - reclassification through the engine, optionally with bill allocation;
   - matching an existing voucher, which reverses the suspense voucher so the bank is never counted twice.
6. **Bank reconciliation statement:**
   - expected statement = book − uncleared deposits + unpresented payments + unrecorded credits − unrecorded
     debits;
   - difference = statement balance − expected;
   - opening-balance and reversal vouchers are not book items.

## 7. Historical migration runbook (`services/migration.py`, UI: Migration Center)

1. Activate the entity's books with a `books_start_date` early enough to cover the history being migrated.
2. Create the bank account(s) that historical payments went through.
3. **Dry run.** Every own-side trade and each trade payment is classified as READY, NEEDS_REVIEW (with reasons),
   ALREADY_ACCOUNTED or EXCEPTION. Nothing is posted.
4. Review the reasons, fix the trades in the Trade module, and run the dry run again.
5. **Execute** with `confirm=true` (in the UI, typing the entity name). Each record is posted in its own transaction
   through the same engine, so failures are recorded and don't roll back the rest. Re-running is a no-op for
   records already accounted.
6. **Reconcile:** source trade totals vs accounted totals per FY. Differences stay visible.
7. **Production:** rehearse on a sanitised snapshot (OD-17) first, and execute only with the owner's approval.
   **Not done.**

## 8. Test evidence (2026-11-17)

- `apps/accounting/tests` — 56 tests:
  - posting engine and DB triggers;
  - trade purchase/sale/commission, TDS worked example (10,00,000 + 18% GST, 2% TDS → payable 11,60,000), TDS
    threshold;
  - edit → reverse and re-post; delete guards; intercompany pair;
  - banking end to end with reconciliation difference 0.00; split, partial and unmatch; suspense resolved without
    double counting;
  - full chain with TB, P&L, BS and cash flow agreeing; loans (accrual, repayment, closure); migration (dry run,
    execute, re-run no-op, reconcile); consolidation elimination;
  - API permissions, Decimal strings, and the HTTP workflow.
- `tests/architecture` — 9 tests. Accounting is a governed app.
- Frontend: `money.test.ts` and `AccountingWorkspace.test.tsx`, plus the existing suites. `tsc` and `vite build`
  pass.

## 9. Second review round (2026-11-17)

Rule changes made by the second review round (details: `07-integration-report.md`):
- Trade payment linking refuses `possible_duplicate` and offers to link an existing payment.
- TDS FULL mode catches up the FY aggregate once, the first time the threshold is crossed. Lower-deduction certificate limits are honoured.
- A payment reversal keeps its bank match: the reversal voucher matches the bank return line, and a voucher+reversal pair that never reached the bank nets off.
- Notes show their unapplied credit and are capped at the bill amount. Suspense on account can be allocated later.
- Cash flow treats opening balances as opening cash. An overdraft is a liability.
- An unregistered recipient is intra-state for GST.
- A backdated loan repayment trues up accrued interest.
- Consolidation eliminates only flows within the selected group, includes intercompany commission, and takes a stock reserve with a warning.
- Maker-checker also applies to posting bills and to reversals.
- Migration 0004 freezes the narration and posting audit columns of posted vouchers.
