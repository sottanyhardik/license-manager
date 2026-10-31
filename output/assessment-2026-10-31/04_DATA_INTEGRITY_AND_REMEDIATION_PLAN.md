# Data integrity and remediation plan

1. Snapshot and reproduce every live metric in an isolated read-only extract; record query, date/time, company scope, deleted/hidden/merged policy and count unit.
2. Classify duplicate debit candidates as actual duplicate, legitimate repeated debit, duplicate reference, historical/superseded, hidden/merged, or insufficient evidence. Do not label them errors before this review.
3. Use five remediation lanes: safe detection; candidate+manual approval; manual review; source-document verification; business-policy decision.
4. Prioritise BOE/invoice links, CIF/quantity differences, missing DGFT, zero/missing quantity, stale product/rule mappings, orphan documents and duplicate master records.
5. Every correction requires source evidence, before/after values, actor/time/reason, dependent-impact preview and controlled reverse/reopen route. No bulk deletion.

Acceptance: baseline counts are reproducible; each candidate has disposition/owner; corrections reconcile to source documents and canonical balances; exceptions are visible to owner.
