# Release and cutover plan - preliminary

## Environment sequence

1. Local development: synthetic or approved anonymized fixtures only.
2. CI: isolated database/broker/files; repeatable migrations and test suite.
3. Staging: production-like topology plus authorized isolated data copy.
4. Production: only after explicit approval, tested backup restore and cutover/rollback rehearsal.

## Non-negotiable production gate

- deployed artifact/version identified;
- migration runbook reviewed;
- backup restore proven in isolation;
- data/file reconciliation has no unexplained material discrepancy;
- required test, security, performance and UAT evidence accepted;
- transaction freeze/delta plan and decision owner on-call;
- rollback or post-cutover delta-recovery plan accepted.

## Post-release verification

Compare first-day company-scoped operational dashboards, licence ledger totals, restricted-pool usage, BOE/invoice status, documents, APIs/jobs/errors and (if activated) accounting journal/subledger balances against the approved baseline. Any unexplained material divergence is a rollback/escalation decision, not a silent correction.

