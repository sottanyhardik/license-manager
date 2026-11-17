# ADR-004 — Central double-entry accounting engine fed by the Trade module

- **Status:** Proposed (2026-11-17). Not accepted. No code exists.
- **Context:** `docs/erp-accounting/00–05`. The repo has no accounting. The owner wants the existing Trade module to be
  the single source of purchase and sales transactions, feeding one general ledger for two (or more) legal entities.

## Decision (proposed)

1. Add one app, `apps/accounting`, inside the modular monolith (ADR-003). Banking, tax, expenses, loans and reports
   start as sub-packages.
2. Trade remains the source document and is **not** rebuilt. Accounting depends on trade (selectors and signal
   receivers). Trade never imports accounting.
3. Posting goes through explicit services and an outbox, with an idempotency key
   `{entity}:{source_type}:{source_id}:{event}:{source_version}`. Re-delivery is a no-op. A changed source is handled
   by reversal plus re-post.
4. Balance and immutability are enforced in the service **and** in Postgres (deferrable constraint trigger, immutable
   posted rows).
5. Every balance, outstanding figure and report is a GL query. Nothing caches a balance on trades or parties.
6. Legal entities are a books dimension (`LegalEntity` 1:1 `CompanyModel`), not an access-control boundary (OD-04).
7. Licence CIF utilisation stays fully separate from accounting balances.
8. The historical cut-over uses opening balances. Historical trades are never auto-posted.

## Consequences

- One new edge (trade → accounting) is added to the import-edge ratchet baseline.
- Posted trades can no longer be hard-deleted. The trade API's DELETE/PATCH behaviour on posted trades changes
  (an API CONTRACT CHANGE that needs the owner's approval of AD-06).
- Paired-trade semantics must be made explicit (AD-03) before posting can start.

## Alternatives considered

- **Separate accounting service.** Rejected: there is no scaling need, and two databases would break the
  transactional posting guarantee.
- **Accounting fields on LicenseTrade** (posted flag, GL balances). Rejected: it duplicates balances and couples trade
  to accounting.
- **Tally integration only (export vouchers).** Viable as an interim step, but it does not meet "no duplicate records
  in Tally/Excel". It could reuse the same posting rules as an export target.
