# Migration and rollback plan - design gate

## Rules

1. No destructive migration or production write is permitted during discovery.
2. Backup success is insufficient: restore it into isolation and validate applications/files.
3. Every source-to-target field requires a mapping, null/default/uniqueness policy, reconciliation query and rollback/delta treatment.
4. Preserve source identifiers/references; do not fabricate history or force balancing adjustments to hide discrepancies.
5. Run at least two dry runs and preserve the legacy application read-only after cutover.

## Cutover decision

Choose one only after rehearsals:

- controlled maintenance window and final delta migration; or
- designed dual-write/delta capture with reconciliation and failure recovery.

The rollback design must explain how new post-cutover transactions are retained or reconciled. Restoring an old backup that discards real activity is not an acceptable complete rollback plan.

