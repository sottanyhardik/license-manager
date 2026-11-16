# DB integrity tooling (read-only)

Wave 0 of the modernization plan (`docs/modernization/FINAL_MODERNIZATION_REPORT.md` §4).
Every script refuses a non-local DB host and runs inside a rolled-back `READ ONLY` transaction.

| Script | Purpose |
|---|---|
| `inventory.py [OUT]` | server, constraint/index health, migrations per app, row count per table |
| `balance_baseline.py OUT.csv` | every `LicenseBalanceCalculator` term per licence + `is_over_utilised` + stored balance |
| `diff_baseline.py A.csv B.csv` | per-licence diff of two baselines; exit 1 on any difference (no DB needed) |

Around any migration or balance-code change:

```bash
PY=backend/.venv/bin/python
$PY scripts/dev/db_integrity/inventory.py ~/lm_backups/inventory_before.txt
$PY scripts/dev/db_integrity/balance_baseline.py ~/lm_backups/balance_before.csv
# ... change + migrate (local only) ...
$PY scripts/dev/db_integrity/balance_baseline.py ~/lm_backups/balance_after.csv
python3 scripts/dev/db_integrity/diff_baseline.py ~/lm_backups/balance_before.csv ~/lm_backups/balance_after.csv
diff ~/lm_backups/inventory_before.txt ~/lm_backups/inventory_after.txt
```

Write outputs to `~/lm_backups/` (outside the repo). They contain business data; never commit them.
