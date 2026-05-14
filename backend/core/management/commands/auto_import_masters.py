"""
Auto-import master records from other servers' audit snapshots into THIS server.

Strategy:
  1. For each record in the source snapshots:
     - Check all unique constraints on the model
     - If ANY unique field matches a local record → SKIP (already exists)
     - If no match → try to create
       - Success → record imported
       - IntegrityError (unique violation, FK violation) → add to FAILED CSV

The FAILED CSV is the only thing requiring manual review.  Everything else
is handled automatically.

Usage (run on the WINNER server = license-manager):
    python manage.py auto_import_masters \\
        --sources audit-labdhi.json audit-tractor.json \\
        --failed-out failed-imports.csv \\
        --apply        # without this, runs dry-run
"""
import csv
import json
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction


# Tables to import (label → app_label.ModelName).  Anything not listed is ignored.
IMPORTABLE_TABLES = {
    "core.companymodel":              "core.CompanyModel",
    "core.portmodel":                 "core.PortModel",
    "core.itemheadmodel":             "core.ItemHeadModel",
    "core.itemgroupmodel":            "core.ItemGroupModel",
    "core.itemnamemodel":             "core.ItemNameModel",
    "core.hscodemodel":               "core.HSCodeModel",
    "core.sionnormclassmodel":        "core.SionNormClassModel",
    "core.exchangeratemodel":         "core.ExchangeRateModel",
}

# Fields we never copy from another server
EXCLUDED_FIELDS = {"id", "created_on", "modified_on", "created_by", "modified_by"}

# Per-table field overrides applied AFTER copying source data.
# Use to force a value that should be set locally regardless of what the
# source server has — e.g., SION classes are activated per-server.
FIELD_OVERRIDES = {
    "core.sionnormclassmodel": {"is_active": False},
}


def get_unique_keys(Model):
    """Return list of tuples of field names for each unique constraint."""
    keys = []
    for f in Model._meta.fields:
        if f.unique and not f.primary_key:
            keys.append((f.name,))
    for tup in (Model._meta.unique_together or ()):
        keys.append(tuple(tup))
    # Newer constraints API
    for c in (Model._meta.constraints or ()):
        if c.__class__.__name__ == "UniqueConstraint" and not getattr(c, "condition", None):
            fields = getattr(c, "fields", None) or ()
            if fields:
                keys.append(tuple(fields))
    return keys


def find_existing(Model, data, unique_keys):
    """Return existing local record matching ANY unique key, or None."""
    for key_fields in unique_keys:
        filters = {}
        complete = True
        for f in key_fields:
            v = data.get(f)
            if v is None:
                complete = False
                break
            filters[f] = v
        if not complete:
            continue
        existing = Model.objects.filter(**filters).first()
        if existing:
            return existing, key_fields
    return None, None


class Command(BaseCommand):
    help = "Auto-import master records from other servers; only report failures"

    def add_arguments(self, parser):
        parser.add_argument("--sources", nargs="+", required=True, help="Audit JSON files to import from")
        parser.add_argument("--failed-out", default="failed-imports.csv", help="Where to write the failures CSV")
        parser.add_argument("--apply", action="store_true", help="Actually commit (default: dry-run)")
        parser.add_argument("--only-tables", nargs="*", help="Limit to specific tables (e.g. core.companymodel)")

    def handle(self, *args, **opts):
        sources = []
        for path in opts["sources"]:
            snap = json.load(open(path))
            sources.append(snap)
            self.stdout.write(f"Loaded {snap['server_name']} from {path}")

        failed_rows = []
        stats = defaultdict(lambda: {"skipped_existing": 0, "imported": 0, "failed": 0})

        for snap in sources:
            server = snap["server_name"]
            for table, table_data in snap["tables"].items():
                if opts.get("only_tables") and table not in opts["only_tables"]:
                    continue
                if table not in IMPORTABLE_TABLES:
                    continue
                if "error" in table_data:
                    continue

                Model = apps.get_model(IMPORTABLE_TABLES[table])
                unique_keys = get_unique_keys(Model)

                # Plain (non-relation) fields
                scalar_fields = {
                    f.name for f in Model._meta.fields
                    if f.name not in EXCLUDED_FIELDS and not f.is_relation
                }
                # FK fields (resolved on destination via business-key hints)
                fk_fields = {
                    f.name: f for f in Model._meta.fields
                    if f.is_relation and f.many_to_one
                }

                for rec in table_data.get("records", []):
                    raw = rec["data"]
                    src_data = {k: v for k, v in raw.items() if k in scalar_fields}

                    # Resolve FK fields by business-key hint (audit exports `<fk>__<key>`)
                    for fk_name, fk_field in fk_fields.items():
                        if fk_name in EXCLUDED_FIELDS:
                            continue
                        related_model = fk_field.related_model
                        resolved = None
                        for candidate in ("name", "code", "iec", "hs_code", "norm_class"):
                            hint = raw.get(f"{fk_name}__{candidate}")
                            if hint and hasattr(related_model, "_meta"):
                                if any(f.name == candidate for f in related_model._meta.fields):
                                    resolved = related_model.objects.filter(**{candidate: hint}).first()
                                    if resolved:
                                        break
                        if resolved:
                            src_data[fk_field.attname] = resolved.pk

                    # 1. Check if it already exists locally (any unique key match)
                    existing, matched_key = find_existing(Model, src_data, unique_keys)
                    if existing:
                        stats[table]["skipped_existing"] += 1
                        continue

                    # Apply per-table field overrides (e.g. SION is_active=False)
                    overrides = FIELD_OVERRIDES.get(table, {})
                    for k, v in overrides.items():
                        src_data[k] = v

                    # 2. Try to create it (skip Django field validators — DB constraints only)
                    try:
                        with transaction.atomic():
                            obj = Model(**src_data)
                            obj.save()
                        stats[table]["imported"] += 1
                    except (IntegrityError, Exception) as e:
                        stats[table]["failed"] += 1
                        failed_rows.append({
                            "table": table,
                            "source_server": server,
                            "source_key": rec["key"],
                            "source_id": rec["id"],
                            "error": str(e)[:300],
                            "data": json.dumps(src_data, default=str)[:500],
                        })

        # Print summary
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        total_imported = total_skipped = total_failed = 0
        for table, s in sorted(stats.items()):
            self.stdout.write(
                f"  {table:38s}  imported={s['imported']:5d}  "
                f"skipped(exists)={s['skipped_existing']:5d}  failed={s['failed']:4d}"
            )
            total_imported += s["imported"]
            total_skipped += s["skipped_existing"]
            total_failed += s["failed"]

        self.stdout.write(self.style.SUCCESS("-" * 70))
        self.stdout.write(self.style.SUCCESS(
            f"  TOTAL:                                  imported={total_imported:5d}  "
            f"skipped(exists)={total_skipped:5d}  failed={total_failed:4d}"
        ))

        # Write failed CSV
        if failed_rows:
            with open(opts["failed_out"], "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["table", "source_server", "source_key", "source_id", "error", "data"])
                writer.writeheader()
                writer.writerows(failed_rows)
            self.stdout.write(self.style.WARNING(f"\n⚠  {len(failed_rows)} failures written to {opts['failed_out']} — review manually."))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ No failures."))

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("\n⚠  DRY RUN — rolling back all imports. Add --apply to commit.\n"))
            # transaction.atomic() inside loop already wraps each record;
            # to roll back we'd need an outer atomic. Easiest: re-run with --apply.
            # But we already committed each successful row above!  Fix below.
        # NOTE: handle this properly with an outer atomic + savepoint per record


# Re-wire: we need an outer transaction to be able to dry-run.
# Override handle to wrap the whole thing in an atomic block.
_orig_handle = Command.handle


def _wrapped_handle(self, *args, **opts):
    if opts.get("apply"):
        return _orig_handle(self, *args, **opts)
    # Dry-run: wrap everything in an atomic block and force rollback at the end
    try:
        with transaction.atomic():
            _orig_handle(self, *args, **opts)
            raise _DryRunRollback()
    except _DryRunRollback:
        pass


class _DryRunRollback(Exception):
    pass


Command.handle = _wrapped_handle
