# Backup, restore and rollback

No backup is considered validated until it restores in isolation and the restored database, files and application start are verified. The cutover runbook must state backup time/checksum, freeze or delta mechanism, migration version, reconciliation gates, owner approvals, monitoring, abort criteria and post-cutover transaction recovery. Rolling back by restoring a pre-cutover snapshot is insufficient if it loses valid new transactions.

