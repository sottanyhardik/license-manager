from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.license.services.sion_legacy_configurations import LEGACY_PLANNER_CONFIGURATIONS
from apps.license.services.sion_legacy_importer import import_planner_definition
from apps.license.services.sion_planner_config.e1_e5 import LEGACY_PLANNER_CONFIG_BY_SION as E1_E5_CONFIGS
from apps.license.services.sion_planner_config.importer import import_profile_document

ALL_CONFIGS = {**E1_E5_CONFIGS, **LEGACY_PLANNER_CONFIGURATIONS}


class Command(BaseCommand):
    help = "Persist audited legacy SION planner configuration (inactive by default)."

    def add_arguments(self, parser):
        parser.add_argument("--sion", action="append", choices=sorted(ALL_CONFIGS))
        parser.add_argument("--apply", action="store_true", help="Write configuration; default is dry-run.")

    def handle(self, *args, **options):
        norms = options["sion"] or sorted(ALL_CONFIGS)
        for norm in norms:
            definition = ALL_CONFIGS[norm]
            rules = len(definition.get("rules", next(
                (row["config"].get("rules", ()) for row in definition["actions"] if row["action_type"] == "MATCH"),
                (),
            )))
            self.stdout.write(
                f"{norm}: rules={rules} actions={len(definition['actions'])} "
                f"mappings={len(definition['mappings'])} active=false"
            )
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run only; pass --apply to persist."))
            return
        try:
            with transaction.atomic():
                results = []
                for norm in norms:
                    if norm in E1_E5_CONFIGS:
                        profile = import_profile_document(E1_E5_CONFIGS[norm])
                        results.append({"norm": norm, "profile_id": profile.pk})
                    else:
                        results.append(import_planner_definition(norm, LEGACY_PLANNER_CONFIGURATIONS[norm]))
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        for result in results:
            self.stdout.write(self.style.SUCCESS(
                f"{result['norm']}: profile={result['profile_id']} imported inactive"
            ))
