# Business rules catalogue

## Licence balance

**Observed evidence:** existing documentation identifies a materialised `available_quantity` field and a documented calculation of `quantity - debited_quantity - allotted_quantity - direct_sale_quantity`. Other documented display paths omit components. See `01-database/licence-balance-analysis.md` and `docs/architecture/CALCULATION_OWNERSHIP.md`.

**Current status:** PARTIALLY_CONFIRMED. The precise lifecycle and all callers must be verified against current source and an authorised dataset.

**Target rule:** source facts create immutable usage/reservation/release/reversal events; a canonical balance service builds one read model; snapshot/cache values are reconcilable, not independent truth.

## DFIA/SION restrictions and AU

**Observed evidence:** `docs/assessment/DFIA_SION_RESTRICTION_SCOPE.md` records free-text `condition_type`, a CIF condition pool keyed by exact percentage text, a separate SION percentage-capacity mechanism, and AU as a transfer restriction in one existing interpretation.

**Rule classification:** BUSINESS_DECISION_REQUIRED. The reported 2%, 3%, 5% and 10% values are not universal legal rules. For every versioned rule, the owner must define documentary source, effective period, base, unit, individual/shared scope, named pool, AU evidence and override control.

**Target rule:** a resolver evaluates the effective versioned rule; named membership defines aggregate caps; immutable usage/reservation events consume capacity atomically; missing/ambiguous configuration blocks or explicitly warns; reports and UI display resolver output only.

## Reconciliation

The locally displayed counts (including 1,699 duplicate-debit candidates) are display metrics, not confirmed financial errors. A candidate requires query definition, record evidence, owner disposition and correction policy. No automated destructive cleanup is allowed.

## Accounting

Existing static evidence found invoices/trade payments, not a complete general ledger. New accounting must define source-event bridges, exactly-once posting keys, balanced journals, reversals, periods, AR/AP, bank matching and CA-approved policy. Drafts or screen views do not create financial entries.

