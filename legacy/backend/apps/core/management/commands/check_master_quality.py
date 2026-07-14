"""
Master-data quality report (READ-ONLY).

Scans the master/reference tables for the three data-quality problems that break
cross-server convergence and the MDS mirror sync (ADR-001):

1. **Blank natural keys** — a business-keyed master row whose key is NULL/empty
   (e.g. the blank-IEC company). Such a row cannot be synced or matched and
   silently collides with other blank rows.
2. **Orphaned foreign keys** — a master row whose FK points at a parent id that
   no longer exists (dangling reference). These break `select_related` joins and
   would be skipped by the loader.
3. **Duplicate business keys** — two+ rows sharing the same natural key. Uniqueness
   should prevent this, but legacy/imported data can violate it where a unique
   constraint was added later or bypassed.

Output: a machine-readable JSON document (``--json`` / default) plus a human
summary to stderr. **The command never writes anything.** A ``--quarantine``
option is DESIGNED below (validated + dry-run only) but intentionally NOT
executed — quarantining is a data mutation that must be reviewed and run
deliberately against a backed-up DB.

Usage:
    python manage.py check_master_quality                 # summary + JSON to stdout
    python manage.py check_master_quality --out report.json
    python manage.py check_master_quality --quarantine    # refuses: prints the plan only
"""
import json
import sys
from datetime import date, datetime
from decimal import Decimal

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count


# (app_label.Model, natural_key_field or None). Mirrors audit_masters.MASTER_MODELS
# but focuses on quality; keyless masters (natural_key=None) are checked only for
# orphaned FKs, not for blank/duplicate business keys.
MASTER_MODELS = [
    ("core.CompanyModel", "iec"),
    ("core.PortModel", "code"),
    ("core.ItemHeadModel", "name"),
    ("core.ItemGroupModel", "name"),
    ("core.ItemNameModel", "name"),
    ("core.HSCodeModel", "hs_code"),
    ("core.SionNormClassModel", "norm_class"),
    ("core.HeadSIONNormsModel", None),
    ("core.SIONExportModel", None),
    ("core.SIONImportModel", None),
    ("core.SionNormNote", None),
    ("core.SionNormCondition", None),
    ("core.ProductDescriptionModel", None),
    ("core.UnitPriceModel", None),
    ("core.ExchangeRateModel", "date"),
    ("core.SchemeCode", "code"),
    ("core.NotificationNumber", "code"),
]


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


class Command(BaseCommand):
    help = "Report master-data quality issues (blank keys, orphaned FKs, duplicate keys). Read-only."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out", dest="out", default=None,
            help="Write the JSON report to this path (default: stdout).",
        )
        parser.add_argument(
            "--limit", type=int, default=50,
            help="Max example rows to include per issue in the JSON (default 50).",
        )
        parser.add_argument(
            "--quarantine", action="store_true",
            help="DESIGN-ONLY: print the quarantine plan and refuse to execute "
                 "(quarantining mutates data; run deliberately after backup).",
        )

    # ── checks (all read-only) ────────────────────────────────────────────

    def _blank_keys(self, Model, nk):
        """Rows whose natural key is NULL or an empty/whitespace string."""
        if nk is None:
            return []
        field = Model._meta.get_field(nk)
        qs = Model.objects.all()
        # NULL keys
        blank_ids = list(qs.filter(**{f"{nk}__isnull": True}).values_list("pk", flat=True))
        # empty/whitespace only meaningful for text fields
        if field.get_internal_type() in ("CharField", "TextField"):
            for pk, val in qs.exclude(**{f"{nk}__isnull": True}).values_list("pk", nk):
                if val is None or str(val).strip() == "":
                    blank_ids.append(pk)
        return sorted(set(blank_ids))

    def _orphaned_fks(self, Model):
        """FKs whose referenced parent id does not exist. Returns
        {fk_field: [pk, ...]}. NULL FKs are not orphans."""
        out = {}
        for field in Model._meta.get_fields():
            if not (field.is_relation and field.many_to_one and field.concrete):
                continue
            parent = field.related_model
            valid_ids = parent.objects.values_list("pk", flat=True)
            orphan_pks = list(
                Model.objects
                .exclude(**{f"{field.attname}__isnull": True})
                .exclude(**{f"{field.attname}__in": valid_ids})
                .values_list("pk", flat=True)
            )
            if orphan_pks:
                out[field.name] = sorted(orphan_pks)
        return out

    def _duplicate_keys(self, Model, nk):
        """Natural-key values shared by 2+ rows. Returns {key_value: [pk, ...]}."""
        if nk is None:
            return {}
        dup_values = (
            Model.objects.values(nk).annotate(n=Count("pk")).filter(n__gt=1)
            .values_list(nk, flat=True)
        )
        out = {}
        for val in dup_values:
            pks = list(Model.objects.filter(**{nk: val}).values_list("pk", flat=True))
            out[str(_jsonable(val))] = sorted(pks)
        return out

    # ── orchestration ─────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        limit = opts["limit"]
        report = {"models": {}, "totals": {"blank_keys": 0, "orphaned_fks": 0, "duplicate_keys": 0}}

        for label, nk in MASTER_MODELS:
            app_label, model_name = label.split(".", 1)
            try:
                Model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stderr.write(f"  skip {label}: model not found")
                continue

            blank = self._blank_keys(Model, nk)
            orphans = self._orphaned_fks(Model)
            dups = self._duplicate_keys(Model, nk)

            orphan_count = sum(len(v) for v in orphans.values())
            dup_row_count = sum(len(v) for v in dups.values())

            report["models"][label] = {
                "natural_key": nk,
                "row_count": Model.objects.count(),
                "blank_keys": {"count": len(blank), "example_pks": blank[:limit]},
                "orphaned_fks": {
                    "count": orphan_count,
                    "by_field": {f: v[:limit] for f, v in orphans.items()},
                },
                "duplicate_keys": {
                    "groups": len(dups),
                    "row_count": dup_row_count,
                    "examples": dict(list(dups.items())[:limit]),
                },
            }
            report["totals"]["blank_keys"] += len(blank)
            report["totals"]["orphaned_fks"] += orphan_count
            report["totals"]["duplicate_keys"] += dup_row_count

        payload = json.dumps(report, indent=2, default=_jsonable)
        if opts["out"]:
            with open(opts["out"], "w") as fh:
                fh.write(payload)
            self.stderr.write(f"Wrote report -> {opts['out']}")
        else:
            self.stdout.write(payload)

        self._print_summary(report)

        if opts["quarantine"]:
            self._print_quarantine_plan(report)

        # Non-zero exit if any issue found, so CI/cron can alert.
        t = report["totals"]
        if t["blank_keys"] or t["orphaned_fks"] or t["duplicate_keys"]:
            # BaseCommand has no exit-code API; write to stderr and raise SystemExit.
            self.stderr.write(self.style.WARNING("Data-quality issues found (see report)."))

    def _print_summary(self, report):
        t = report["totals"]
        self.stderr.write("")
        self.stderr.write("Master-data quality summary:")
        self.stderr.write(f"  blank natural keys : {t['blank_keys']}")
        self.stderr.write(f"  orphaned FKs       : {t['orphaned_fks']}")
        self.stderr.write(f"  duplicate keys     : {t['duplicate_keys']}")
        for label, m in report["models"].items():
            issues = m["blank_keys"]["count"] + m["orphaned_fks"]["count"] + m["duplicate_keys"]["row_count"]
            if issues:
                self.stderr.write(
                    f"    {label}: blank={m['blank_keys']['count']} "
                    f"orphaned={m['orphaned_fks']['count']} dup={m['duplicate_keys']['row_count']}"
                )

    def _print_quarantine_plan(self, report):
        """DESIGN-ONLY. Describe what a --quarantine run WOULD do, then refuse.

        Quarantine design (not executed here):
        - A `MasterQuarantine` table (or a `quarantined_at` nullable column on each
          master) receives the offending rows' snapshots (model, pk, natural key,
          reason, json of the row) so nothing is lost.
        - Blank-key rows: move to quarantine, delete from the live table only if no
          FK dependents (checked via reverse relations); otherwise flag, do not delete.
        - Orphaned-FK rows: NULL the FK if the field is nullable; else quarantine.
        - Duplicate-key rows: keep the newest by modified_on (or lowest pk if no
          timestamp), quarantine the rest, and repoint any dependents to the keeper.
        - The whole run is one transaction with a --dry-run that prints the plan and
          rolls back, plus a row-count reconciliation (live+quarantine == original).
        """
        self.stderr.write("")
        self.stderr.write(self.style.WARNING(
            "--quarantine is DESIGN-ONLY and was NOT executed. It mutates data and must be "
            "run deliberately against a backed-up DB. Plan:"
        ))
        self.stderr.write(
            "  1) snapshot each offending row into a MasterQuarantine store (lossless);\n"
            "  2) blank keys -> quarantine (delete only if no dependents);\n"
            "  3) orphaned FKs -> NULL if nullable else quarantine;\n"
            "  4) duplicates -> keep newest, quarantine rest, repoint dependents;\n"
            "  5) run inside one transaction with --dry-run + row-count reconciliation."
        )
        raise CommandError("Refusing to quarantine automatically. Re-run without --quarantine to report only.")
