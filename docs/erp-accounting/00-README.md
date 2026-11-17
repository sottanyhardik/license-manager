# ERP Accounting Integration — Phase Zero (2026-11-17)

Read-only audit of the existing License Manager. It is the basis for turning the existing Trade module into the source of a
double-entry accounting system. **No application code, schema or data was changed.**

Baseline: `feature/v5` @ `01223ea7`, plus the uncommitted trade work in the shared checkout (T1 `amount_override`,
`line_pricing.py`, migration `trade/0012`). That work is treated as current but not yet stable.

Builds on, and does not repeat: `docs/erp-transformation/00–14` (branch `feature/erp-implementation`, licence/CIF
focus), `docs/audits/ERP_FINANCIAL_DEPENDENCY_MAP.md` and `docs/audits/FINANCIAL_ENGINE_ARCHITECTURE.md`
(uncommitted, licence CIF engines).

## Headline findings

1. **No accounting exists in code.** There is no chart of accounts, voucher, journal, GL, party ledger, bank account,
   bank statement, GST rate, TDS or loan anywhere in `backend/apps` (grep-verified). The account codes 5303/4103 appear
   only in `docs/guides/COMMISSION_ACCOUNTING_GUIDE.md`. The "financial ledger" in the app is a **licence CIF ledger**,
   not an accounting ledger.
2. **The Trade module is a solid source document,** but it is not yet postable:
   - It has no lifecycle status (draft, confirmed, cancelled). Trades can be edited or hard-deleted (with cascade) at
     any time.
   - It has no tax, TDS, currency or due-date fields on the header.
   - Payments (`LicenseTradePayment`) have only `date`, `amount` and `note`, with no bank, mode, UTR or user.
   - Payments are **copied onto the counterpart leg** of a paired trade, so the same settlement exists twice.
3. **There is no "own legal entity" concept.** `CompanyModel` is the only party master. It is mirrored from MDS and
   holds own companies and counterparties alike. Which side of a trade is "us" is implied only by `direction`.
4. **Paired trades are the biggest double-posting risk.** Paired trades are a PURCHASE↔SALE counterpart copy created
   by `copy-to-*`, `auto_create_paired` or the legacy `linked_trade`. Whether a pair is one real transaction or two
   (for example an intercompany transfer between two Labdhi LLPs) decides whether one leg or both post. This is not
   derivable from code. **Owner decision AD-03.**
5. **The architecture rules fit a new `apps/accounting` app well.** ADR-003 and the AST ratchet tests require
   service-layer writes, `transaction.atomic` and audit records. Accounting may import trade one way. Trade must never
   import accounting.

## Documents

| # | File | Prompt deliverables |
|---|---|---|
| 01 | [01-existing-architecture-and-workflows.md](01-existing-architecture-and-workflows.md) | 1 architecture map, 2 trade→invoice workflow, 3 finance workflow, 4 DB relationship diagram |
| 02 | [02-calculations-gaps-duplicates.md](02-calculations-gaps-duplicates.md) | 5 financial calculation inventory, 6 missing accounting functionality, 7 duplicate functionality |
| 03 | [03-integrity-and-api-compatibility.md](03-integrity-and-api-compatibility.md) | 8 data integrity risks, 9 API compatibility |
| 04 | [04-accounting-integration-design.md](04-accounting-integration-design.md) | Proposed target design: accounting app, posting rules, event/outbox, entities, permissions |
| 05 | [05-phased-plan.md](05-phased-plan.md) | 10 phased implementation plan + acceptance tests |
| — | [../decisions/ADR-004-accounting-engine.md](../decisions/ADR-004-accounting-engine.md) | Architecture decision, **status: Proposed** |

## Owner decisions required before any implementation

These change architecture, data or statutory treatment, so per CLAUDE.md §2/§2a none is assumed. Each has a
recommendation in doc 04. They are listed in the order to ask them.

| ID | Decision | Recommendation |
|---|---|---|
| AD-01 | How "books-owning" legal entities are modelled | New `accounting.LegalEntity` 1:1 → `core.CompanyModel`, to avoid a schema change on the MDS-mirrored master |
| AD-02 | Accounting cut-over date and opening balances | Start at a FY boundary (e.g. 01-04-2026). Opening balances come from the CA-signed Tally trial balance and outstanding-bill lists. **No historical trade auto-posting.** |
| AD-03 | Meaning of paired trades (counterpart / linked_trade) | Classify every pair explicitly as `DOCUMENT_COPY` (post one leg) or `INTERCOMPANY` (post both legs, in different entities' books). Block posting of unclassified pairs. |
| AD-04 | Source of truth for payments and receipts | New bank-linked Payment/Receipt vouchers going forward. `LicenseTradePayment` becomes read-only history, displayed but not posted. |
| AD-05 | GST/TDS treatment of licence trades | CA confirms the tax treatment of licence (HSN 4907) supplies, which today are billed on a Bill of Supply with no GST, and of TDS (e.g. s.194Q) on purchases. All rates and thresholds come from dated configuration, never code. |
| AD-06 | When a trade becomes postable | Add an explicit "Post to books" action (with approval). Edits after posting create a reversal plus a re-post, never a rewrite. Deleting a posted trade is blocked. |
| AD-07 | Roles | New groups `ACCOUNTS_VIEWER` / `ACCOUNTS_MANAGER` / `ACCOUNTS_APPROVER`. The existing `ACCOUNT_ACCESS` is a BOE/report-read role and is left as is. |
| AD-08 | Chart of accounts seed | Import the CA's existing Tally chart (groups and ledgers) per entity rather than invent one |

Frozen items untouched by this programme: licence CIF rules (business-rules.md), A-2, T5–T9, OD-01…OD-21 decisions.
Accounting balances are **never** combined with licence utilisation balances.
