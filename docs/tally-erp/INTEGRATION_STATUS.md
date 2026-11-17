# Tally ERP — integration status (`feature/v5`, 2026-11-17)

How this was produced: a search of `feature/v5` code and docs, every local and remote branch, every worktree, and
commit messages (`git grep -i tally`, `git branch -a`, `git log --all --grep=tally`). **No tests were run.**

Statuses: **COMPLETED** · **IN PROGRESS** · **DEFERRED** · **BLOCKED**.

## Summary

The "Tally ERP" work in this repository is the **in-app double-entry accounting engine that replaces Tally**
(`backend/apps/accounting`, `/accounting/*`), designed in ADR-004. **There is no Tally connector** (XML/ODBC/TDL
export, import, or sync) in any branch, worktree or stash. Nothing Tally-specific was left to consolidate.

## Status by capability

| Capability | Status | Where / evidence |
|---|---|---|
| Tally-equivalent books: entity books, FY and periods, groups and ledgers, vouchers, gap-free numbering, reversal | COMPLETED | `apps/accounting` models, `services/posting.py`; see `docs/erp-accounting/08-completion-inventory.md` §A |
| Tally-style reports: TB, P&L, Balance Sheet, Cash Flow, GL, party ledger, ageing, registers, GST/TDS registers, bank/cash book | COMPLETED | `selectors/reports.py`, Reports screen (14 tabs) |
| Bill-wise receivables/payables (Tally "bill-wise details") | COMPLETED | payments, allocation and on-account allocation services |
| Banking and bank reconciliation (Tally BRS) | COMPLETED | `services/banking.py`, Banking workbench, BRS |
| Tally-style CR/DR licence ledger view (licence module, pre-existing) | COMPLETED | commit `ae46557a` (licence ledger, not accounting) |
| Opening balances from the CA's Tally trial balance and open bills (AD-02) | DEFERRED | Only a manual OPENING journal exists; there is no bulk import screen (inventory §B) |
| Import of the CA's Tally chart of accounts (AD-08) | DEFERRED | A default Indian trading chart is seeded per entity instead; the accountant can add and rename ledgers |
| Tally voucher export (XML/TDL) as an export target (ADR-004 alternative, gap item 10h) | DEFERRED | Not implemented. ADR-004 rejected it as the *primary* path; it could reuse the posting rules |
| Tally import / two-way sync | DEFERRED | Not implemented, and not designed |
| System of record (in-app books vs Tally) and cut-over date | BLOCKED | Owner/CA decision: D6 in `docs/modernization/backend-audit/12_TRADE_TO_FINANCE_LIFECYCLE_AUDIT.md`, AD-02 in `docs/erp-accounting/00-README.md`. Overlap risk R13: historical trades may already be in Tally |
| Historical posting on production | BLOCKED | Needs a sanitised-snapshot rehearsal and approval (rehearsed locally on a copy: 482 trades, 0 differences) |

Nothing is IN PROGRESS for Tally: no branch, worktree or uncommitted file contains Tally work.

## Next steps (in order, once the owner/CA decides)
1. Decide the system of record and the cut-over date (D6 / AD-02).
2. If the books stay in-app: build the opening-balance import (TB + open bills through `post_voucher`), optionally with a
   chart import from the Tally group/ledger export.
3. If Tally stays the system of record: add a voucher export (Tally XML) built from the same posting rules.
