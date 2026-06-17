# Management Commands Reference

All commands are run from `backend/` with the virtual environment active:
```bash
cd backend && source ../.venv/bin/activate
```

---

## License App

### `update_license_ownership`
Fetches current ownership & transfer history for DFIA licenses from the DGFT portal and syncs to one or more servers.

```bash
# Interactive server selection (recommended first-run)
python manage.py update_license_ownership

# Target a specific server, all active + never-fetched licenses
python manage.py update_license_ownership --server https://license-manager.duckdns.org

# Only expired licenses, descending expiry order
python manage.py update_license_ownership --server https://license-manager.duckdns.org --expired --order desc

# Specific licenses only
python manage.py update_license_ownership --licenses 5211019110,3411007259 --server https://license-manager.duckdns.org

# Local DB only — no server sync
python manage.py update_license_ownership --local-only

# Resume with custom IEC for licenses missing an exporter
python manage.py update_license_ownership --iec 0305000123

# Skip errors and continue; limit batch size
python manage.py update_license_ownership --skip-errors --limit 50
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--server` | interactive | Target server URL |
| `--local-only` | false | Skip server sync, update local DB only |
| `--licenses` | all | Comma-separated license numbers |
| `--expired` | false | Only expired licenses |
| `--order asc/desc` | desc | `desc` = latest expiry first; `asc` = None first then soonest |
| `--limit N` | none | Cap total licenses processed |
| `--iec` | LACPS9967D | Fallback IEC for licenses without an exporter |
| `--retry-count N` | 3 | DGFT API retries per license |
| `--skip-errors` | false | Continue past individual fetch failures |
| `--proxy URL` | none | HTTP/SOCKS5 proxy for DGFT API |

> **Remark:** Licenses that are expired AND already fetched once are automatically skipped on the next run — ownership data doesn't change after expiry. Use `--expired` to force re-fetch those. The current owner is derived from the last *Approved* transfer, not the DGFT API field (which can reflect the querying IEC's perspective).

---

### `sync_licenses`
Recalculates balance_cif, is_null/is_expired flags, and import item balances for all (or one) licenses.

```bash
# Sync all licenses
python manage.py sync_licenses

# Dry-run — see what would change
python manage.py sync_licenses --dry-run

# Single license
python manage.py sync_licenses --license 5211019110

# Skip import item recalculation (faster)
python manage.py sync_licenses --no-items --batch-size 200
```

> **Remark:** Run this after bulk BOE or allotment imports to bring all balances in sync. Use `--no-items` when only flag updates (is_null, is_expired) are needed.

---

### `update_balance_cif`
Recalculates only the `balance_cif` field using the LicenseBalanceCalculator service.

```bash
python manage.py update_balance_cif
python manage.py update_balance_cif --license-number 5211019110
python manage.py update_balance_cif --batch-size 200
```

> **Remark:** Lighter than `sync_licenses` — use when only CIF balance needs correcting (e.g., after manual BOE edits).

---

### `upload_dfia_copies`
Uploads PDF copies of DFIA licenses from a folder into the license documents store.

```bash
# Dry-run first to check matches
python manage.py upload_dfia_copies /path/to/pdfs --dry-run

# Actual upload
python manage.py upload_dfia_copies /path/to/pdfs
```

> **Remark:** Replaces existing LICENSE COPY documents. Filename must contain the license number in a recognisable format.

---

### `update_license_expiry`
Bulk-updates license expiry dates from a CSV file.

```bash
# Validate CSV first
python manage.py update_license_expiry expiry_dates.csv --dry-run

# Apply
python manage.py update_license_expiry expiry_dates.csv
```

CSV format: `license_number, license_expiry_date` (accepts DD/MM/YY, DD/MM/YYYY, YYYY-MM-DD).

> **Remark:** Use when DGFT validity dates need correcting in bulk. Safer to `--dry-run` first; license numbers not found in the DB are reported.

---

### `delete_licenses_by_exporter`
Deletes licenses (and all related allotments/BOEs) by exporter name filter.

```bash
# Preview — delete licenses containing "PARLE"
python manage.py delete_licenses_by_exporter --filter contains --exporter "PARLE" --dry-run

# Delete licenses NOT belonging to "GLOBAL MERCANTILE"
python manage.py delete_licenses_by_exporter --filter exclude --exporter "GLOBAL MERCANTILE" --confirm

# Fast deletion with signal disabling
python manage.py delete_licenses_by_exporter --filter contains --exporter "TEST" --confirm --disable-signals --batch-size 200
```

> **Remark:** **Destructive.** Always `--dry-run` first. `contains` mode deletes matching exporters; `exclude` mode deletes everything *except* matching exporters.

---

### `populate_license_items`
Links `ItemNameModel` records to `LicenseImportItemsModel` based on description/HS code matching.

```bash
python manage.py populate_license_items --dry-run
python manage.py populate_license_items --clear   # Clear existing links first
```

> **Remark:** Re-run after adding new ItemNameModel entries. Use `--clear` only if you want to rebuild all links from scratch.

---

## Allotment App

### `update_is_boe`
Sets the `is_boe` flag on allotments that have associated Bill of Entry records.

```bash
python manage.py update_is_boe --dry-run
python manage.py update_is_boe
```

> **Remark:** Run after importing BOEs to keep the allotment flag accurate.

---

### `update_exchange_rate`
Updates the USD→INR exchange rate for allotments and recalculates CIF INR values.

```bash
# Update all allotments to ₹85.50/USD
python manage.py update_exchange_rate --exchange-rate 85.50 --dry-run
python manage.py update_exchange_rate --exchange-rate 85.50

# Only for a specific company
python manage.py update_exchange_rate --exchange-rate 85.50 --filter-company "PARLE"
```

> **Remark:** Use when the customs exchange rate changes mid-year. Always `--dry-run` first to verify the sample changes.

---

## Core App

### `refresh_materialized_views`
Refreshes PostgreSQL materialized views used for balance calculations and dashboard stats.

```bash
python manage.py refresh_materialized_views --all
python manage.py refresh_materialized_views --view license_balance_mv
python manage.py refresh_materialized_views --stats    # View sizes & row counts
python manage.py refresh_materialized_views --all --no-concurrent   # Blocking but faster
```

> **Remark:** Run automatically by Celery beat after balance updates. Run manually after large data imports. `--no-concurrent` locks the table but is faster for initial population.

---

### `clearcache`
Clears the entire Redis cache.

```bash
python manage.py clearcache
```

> **Remark:** Use when stale cached data is causing incorrect responses. Cache will rebuild on next requests.

---

### `cache_stats`
Displays Redis cache statistics and manages cache keys.

```bash
python manage.py cache_stats              # Show stats
python manage.py cache_stats --keys       # List all keys
python manage.py cache_stats --clear      # Clear everything
python manage.py cache_stats --pattern "license_*"   # Clear matching keys
```

> **Remark:** Useful for debugging cache-related issues or memory pressure.

---

### `update_dgft_descriptions`
Fetches SION norms from the DGFT website and updates descriptions in the database.

```bash
python manage.py update_dgft_descriptions
python manage.py update_dgft_descriptions --product-group "Food Products"
python manage.py update_dgft_descriptions --dry-run
```

> **Remark:** Requires active DGFT website access. Session and CSRF tokens are managed internally. Run periodically to keep SION descriptions current.

---

### `update_aluminium_foil_items` / `update_sugar_items`
Links license import items to specific commodity ItemNameModel variants by norm class.

```bash
python manage.py update_aluminium_foil_items --dry-run
python manage.py update_aluminium_foil_items

python manage.py update_sugar_items --dry-run
python manage.py update_sugar_items
```

> **Remark:** These are commodity-specific helpers. Run after `populate_license_items` if aluminium foil (HSN 7607) or sugar (HSN 1701) items need precise norm-class linking (e.g., E1, E132).

---

### `convert_docx_to_pdf`
Converts all DOCX files in a folder to PDF using LibreOffice.

```bash
python manage.py convert_docx_to_pdf --path /path/to/folder
python manage.py convert_docx_to_pdf --path /path/to/folder --keep-docx
```

> **Remark:** Requires LibreOffice (`soffice`) installed on the server. On macOS, Microsoft Word is tried first. Original DOCX files are deleted after successful conversion unless `--keep-docx` is specified.

---

### `sync_from_ge_server`
Syncs database structure and/or data from the GE server.

```bash
python manage.py sync_from_ge_server --full
python manage.py sync_from_ge_server --data-only
python manage.py sync_from_ge_server --structure-only
python manage.py sync_from_ge_server --license 5211019110
python manage.py sync_from_ge_server --dry-run --full
```

> **Remark:** Primarily used during initial setup or disaster recovery. Use `--dry-run` to preview changes.

---

### `check_db_structure` / `validate_db_fields` / `sync_database_schema` / `rebuild_migrations`
Database health and migration tools.

```bash
# Check for missing/extra tables
python manage.py check_db_structure --verbose
python manage.py check_db_structure --app license --fix

# Validate field types and constraints
python manage.py validate_db_fields --detailed --fix-suggestions
python manage.py validate_db_fields --table license_licensedetailsmodel

# Sync schema with Django models
python manage.py sync_database_schema --show-sql
python manage.py sync_database_schema --fix

# Rebuild migrations (after schema conflicts)
python manage.py rebuild_migrations --dry-run
python manage.py rebuild_migrations --full --apps license,core
```

> **Remark:** Use `check_db_structure` and `validate_db_fields` when the app throws `column does not exist` errors. Use `rebuild_migrations` only when migration history is severely corrupted — it deletes and recreates migration files.

---

### `rqworker`
Runs RQ background workers.

```bash
python manage.py rqworker default
python manage.py rqworker default high --burst    # Process queue then exit
python manage.py rqworker --with-scheduler        # Include RQ Scheduler
```

> **Remark:** Typically managed by Supervisor. Use `--burst` for one-off queue drains.

---

### `clean_duplicate_rowdetails`
Removes duplicate and orphaned RowDetails records.

```bash
python manage.py clean_duplicate_rowdetails
```

> **Remark:** Safe to run on a live DB. Keeps one record per (bill_of_entry, sr_number, transaction_type) group. Also removes records where bill_of_entry is NULL and transaction_type is 'D'.

---

### `clean_item_names`
Deletes **all** ItemNameModel records.

```bash
python manage.py clean_item_names --confirm
```

> **Remark:** **Destructive.** Only use before a full re-import of item names. Requires `--confirm` flag.

---

### `fetch_detail_conf` / `fetch_detail_bisc` / `report_fetch`
Legacy report generators that produce Excel/CSV output files.

```bash
python manage.py fetch_detail_conf
python manage.py fetch_detail_bisc expired
python manage.py report_fetch active
```

> **Remark:** These commands have placeholder help text (`"Closes the specified poll for voting"`) — a known issue. They still function correctly but should be reviewed and cleaned up.
