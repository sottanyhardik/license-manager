"""
Apply a reviewed merge plan: import master records from other servers' audit
snapshots into THIS server.

Usage (run on the WINNER server = license-manager):
    python manage.py merge_masters \\
        --plan merge-plan.csv \\
        --others audit-labdhi.json audit-tractor.json \\
        --apply        # without this flag, runs in dry-run mode

The plan CSV is the output of `diff_masters`. You should:
  1. Review the CSV manually
  2. For rows where status = CONFLICT, set the `action` column to one of:
         KEEP_WINNER     — leave winner record alone, ignore the others
         OVERWRITE       — replace winner record with the other server's data
         IMPORT_TO_WINNER — winner doesn't have it, pull from the others
         SKIP            — do nothing
  3. Run this command. It only acts on rows where action ∈ {IMPORT_TO_WINNER, OVERWRITE}.

SAFE BY DEFAULT: dry-run unless --apply is passed.
"""
import csv
import json

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction


# Map table label (lowercased) → (app_label.ModelName, business_key_field)
TABLE_TO_MODEL = {
    "core.companymodel":              ("core.CompanyModel",            "iec"),
    "core.portmodel":                 ("core.PortModel",               "code"),
    "core.itemheadmodel":             ("core.ItemHeadModel",           "name"),
    "core.itemgroupmodel":            ("core.ItemGroupModel",          "name"),
    "core.itemnamemodel":             ("core.ItemNameModel",           "name"),
    "core.hscodemodel":               ("core.HSCodeModel",             "hs_code"),
    "core.sionnormclassmodel":        ("core.SionNormClassModel",      "norm_class"),
    "core.exchangeratemodel":         ("core.ExchangeRateModel",       "date"),
}


def _strip_unsafe(data, keep_fields):
    """Keep only fields safe to copy across servers — drops IDs, audit fields, FKs unless mapped."""
    safe = {}
    for k, v in data.items():
        if k in ("id", "created_on", "modified_on", "created_by", "modified_by"):
            continue
        if k in keep_fields:
            safe[k] = v
    return safe


class Command(BaseCommand):
    help = "Apply a reviewed merge plan to import missing master records"

    def add_arguments(self, parser):
        parser.add_argument("--plan", required=True, help="Reviewed CSV from diff_masters")
        parser.add_argument("--others", nargs="+", required=True, help="Other servers' audit JSON files")
        parser.add_argument("--apply", action="store_true", help="Actually apply changes (default: dry-run)")

    def handle(self, *args, **opts):
        # Load other servers' snapshots, indexed by (table, key) → record
        others_data = {}
        for path in opts["others"]:
            snap = json.load(open(path))
            for table_name, t in snap["tables"].items():
                for r in t.get("records", []):
                    key = (table_name, r["key"])
                    # First seen wins (or could prefer most recent)
                    others_data.setdefault(key, (snap["server_name"], r))

        # Load plan
        plan_rows = list(csv.DictReader(open(opts["plan"])))

        actionable = [r for r in plan_rows if r["action"] in ("IMPORT_TO_WINNER", "OVERWRITE")]
        self.stdout.write(f"Plan has {len(plan_rows)} total rows, {len(actionable)} actionable.\n")

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made. Add --apply to commit.\n"))

        created = updated = skipped = 0

        with transaction.atomic():
            for row in actionable:
                table = row["table"]
                key   = row["key"]
                action = row["action"]

                if table not in TABLE_TO_MODEL:
                    self.stdout.write(self.style.WARNING(f"  SKIP unknown table: {table}"))
                    skipped += 1
                    continue

                model_label, key_field = TABLE_TO_MODEL[table]
                Model = apps.get_model(model_label)

                # Find source record in others_data
                source = others_data.get((table, key))
                if not source:
                    self.stdout.write(self.style.WARNING(f"  SKIP no source for {table}:{key}"))
                    skipped += 1
                    continue
                source_server, source_rec = source

                # Field whitelist = all model fields except id/audit/FK we can't resolve
                keep_fields = {f.name for f in Model._meta.fields
                               if f.name not in ("id", "created_on", "modified_on", "created_by", "modified_by")
                               and not f.is_relation}

                safe_data = _strip_unsafe(source_rec["data"], keep_fields)

                # Lookup by business key
                lookup = {key_field: safe_data.get(key_field)}

                if action == "IMPORT_TO_WINNER":
                    existing = Model.objects.filter(**lookup).first()
                    if existing:
                        self.stdout.write(f"  SKIP {table}:{key} already exists locally (id={existing.pk})")
                        skipped += 1
                        continue
                    if opts["apply"]:
                        obj = Model.objects.create(**safe_data)
                        self.stdout.write(self.style.SUCCESS(f"  CREATED {table}:{key} (from {source_server}, id={obj.pk})"))
                    else:
                        self.stdout.write(f"  [dry] CREATE {table}:{key} from {source_server} → {safe_data}")
                    created += 1

                elif action == "OVERWRITE":
                    existing = Model.objects.filter(**lookup).first()
                    if not existing:
                        if opts["apply"]:
                            obj = Model.objects.create(**safe_data)
                            self.stdout.write(self.style.SUCCESS(f"  CREATED {table}:{key} (overwrite, id={obj.pk})"))
                        created += 1
                    else:
                        if opts["apply"]:
                            for f, v in safe_data.items():
                                setattr(existing, f, v)
                            existing.save()
                            self.stdout.write(self.style.SUCCESS(f"  UPDATED {table}:{key} (id={existing.pk}) from {source_server}"))
                        else:
                            self.stdout.write(f"  [dry] UPDATE {table}:{key} from {source_server}")
                        updated += 1

            if not opts["apply"]:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"\nResult: created={created}  updated={updated}  skipped={skipped}"
        ))
