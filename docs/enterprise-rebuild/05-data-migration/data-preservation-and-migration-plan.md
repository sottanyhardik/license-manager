# Data preservation and migration plan

1. Capture authorised backup plus document/file inventory and prove isolated restore.
2. Create field-level source-to-target mapping with identifiers, transform/null/default policy, relationship, owner and reconciliation query.
3. Migrate facts and history without regeneration; derive target snapshots/read models separately and compare results.
4. Reconcile counts, identifiers, relationships, company scope, documents/hashes, licence usage/balances, BOE/trade/reconciliation data and later accounting openings/postings.
5. Run at least two dry migrations before approval.
6. Cut over by approved maintenance window or designed delta capture; preserve legacy read-only reference.

Unexplained material discrepancy blocks release. A row count alone is not reconciliation.

