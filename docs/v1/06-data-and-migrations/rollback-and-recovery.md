# Rollback and recovery

Prefer forward recovery for migrated data; rollback code only when no data contract has changed. Each migration requires backup verification, resumable backfill, comparison report, cutover flag and tested restore procedure.
