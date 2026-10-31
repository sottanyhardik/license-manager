# Data migration and risk assessment

| Conceptual change | Compatibility/backfill | Deployment safety |
|---|---|---|
| Tenant + membership | Classify/backfill every historical company-linked record; isolate unmappable records. | Add nullable IDs/read scope first, validate counts/leaks, then enforce; reversible feature gate. |
| Restriction rule/group/usage | Map free-text condition types; retain raw source and mark ambiguous rows for review. | Dual-read/compare, immutable usage ledger, versioned rules; never silently infer group membership. |
| Journal/lines/accounts | Map source invoices/trades/payments and opening balances only after signed mapping approval. | Start prospective posting; reconcile trial balance; use controlled backfill and reversal—not overwrites. |
| Bank statements/matches | Fingerprint imports and preserve source rows/files. | Separate import batch, dry-run preview, duplicate controls, append-only match history. |

For every migration: backup/restore proof, validation queries, exception queue, counts/totals before/after, rollback plan and staged release are mandatory. No migration was created/applied during this assessment.
