# License Manager assessment — executive summary

**Inspected baseline:** `develop` / `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65` (2026-10-28). `origin/HEAD` is `develop`; local/remote `master` diverges by one commit in each direction. This does not establish the deployed version. Assessment date: 2026-10-31.

## Position

License Manager is a substantial Django/React modular monolith for DFIA/SION licences, allotments, BOEs, trade, planning, document generation, master data and BOE-to-invoice reconciliation. It has meaningful transactional controls, role checks, audit fields, PDF import/export and tests. It is **not evidenced as a tenant-isolated SaaS**, a double-entry accounting system, or a bank-reconciliation product.

The most material confirmed scope risks are: global role permissions without demonstrated tenant/company scoping (SEC-01); condition-pool grouping by free-text percentage rather than an explicit restriction group (DFR-01); a separate, potentially divergent SION percentage calculator with broad exception-to-zero paths (DFR-02); and no discovered chart-of-accounts/journal/bank statement domain. These are evidence-backed code findings, not runtime reproductions.

## Priorities

1. Decide internal multi-company versus external SaaS, then establish tenant/membership and scope every query/mutation.
2. Freeze and characterise balance/restriction outputs; define authoritative restriction bases, pools, AU treatment and rule priority before redesign.
3. Consolidate calculations behind backend services and migrate callers incrementally with regression comparisons.
4. Build immutable double-entry foundation before advanced accounting reports or bank reconciliation.
5. Redesign high-use licence/allotment/BOE/trade planning screens only after correctness contracts are fixed.

## Readiness assessment

| Area | Assessment |
|---|---|
| Licence/planning | Implemented but complex; restriction semantics and shared-pool representation need clarification/consolidation. |
| Accounting | Commercial invoices/trade payments exist; general ledger, posting, period controls and financial statements were not found. |
| Bank reconciliation | Current reconciliation is BOE/invoice allocation, explicitly not bank matching. |
| External SaaS | Blocked pending tenant isolation, security/runtime verification, audit/operations and release gates. |
| UI/UX | React design system/test assets exist; runtime interaction evidence is recorded separately and is not inferred from source. |

See the linked reports in [ASSESSMENT_STATUS.md](ASSESSMENT_STATUS.md).
