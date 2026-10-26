"""Correct the ACTIVE A3627 RUTILE / TITANIUM DIOXIDE / PP stored rules.

The stored rows predate the legacy configuration, so ``migrate_sion_planners_to_db``
(which matches rows by ``stable_key``) cannot update them. This command rewrites only
the expression of the three active A3627 rules, using the same audited legacy
expressions, with these guards:

- dry-run by default; nothing is written without ``--apply``;
- exactly one active A3627 row must exist per target name, or the command aborts;
- every new expression must pass the real SION validator before anything is written;
- the old expressions are written to a JSON backup before any change;
- all rows change in one transaction, and only ``expression`` and ``version`` change.
"""
import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.license.models import SionPlanningRule
from apps.license.services.sion_legacy_configurations import LEGACY_PLANNER_CONFIGURATIONS
from apps.license.services.sion_rule_engine import normalize_expression, validate_expression

# Stored rule name -> legacy A3627 output_key whose expression it must carry.
TARGETS = {"RUTILE": "RUTILE", "TITANIUM DIOXIDE": "TITANIUM", "PP": "PP"}


class Command(BaseCommand):
    help = "Correct the active A3627 RUTILE / TITANIUM DIOXIDE / PP rule expressions (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the corrected expressions.")
        parser.add_argument(
            "--backup-dir", default="/tmp/sion_rule_backups",
            help="Directory for the JSON backup of the old expressions (written before any change).",
        )

    def handle(self, *args, **options):
        legacy_rules = {row["output_key"]: row for row in LEGACY_PLANNER_CONFIGURATIONS["A3627"]["rules"]}
        plan = []
        for stored_name, output_key in TARGETS.items():
            rows = list(SionPlanningRule.objects.filter(
                sion__norm_class="A3627", is_active=True, name=stored_name,
            ))
            if len(rows) != 1:
                raise CommandError(
                    f"Expected exactly one active A3627 rule named {stored_name!r}, found {len(rows)}. Nothing changed."
                )
            new_expression = normalize_expression(legacy_rules[output_key]["expression"])
            validate_expression(new_expression)
            plan.append((rows[0], new_expression))

        for rule, new_expression in plan:
            self.stdout.write(f"rule id={rule.id} name={rule.name!r} priority={rule.priority} version={rule.version}")
            self.stdout.write(f"  old: {json.dumps(rule.expression, sort_keys=True)}")
            self.stdout.write(f"  new: {json.dumps(new_expression, sort_keys=True)}")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING(f"Dry run: {len(plan)} rule(s) would change. Pass --apply to write."))
            return

        backup_dir = Path(options["backup_dir"])
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"a3627_active_rules_{datetime.now():%Y%m%d_%H%M%S}.json"
        backup_path.write_text(json.dumps(
            [{"id": rule.id, "name": rule.name, "version": rule.version, "expression": rule.expression}
             for rule, _ in plan],
            indent=2, sort_keys=True,
        ))
        self.stdout.write(f"Backup written: {backup_path}")

        with transaction.atomic():
            for rule, new_expression in plan:
                locked = SionPlanningRule.objects.select_for_update().get(pk=rule.pk)
                locked.expression = new_expression
                locked.version = locked.version + 1
                locked.save(update_fields=["expression", "version"])
        self.stdout.write(self.style.SUCCESS(f"Updated {len(plan)} active A3627 rule(s)."))
