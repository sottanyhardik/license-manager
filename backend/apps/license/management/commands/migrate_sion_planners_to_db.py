from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.license.services.sion_legacy_configurations import LEGACY_PLANNER_CONFIGURATIONS
from apps.license.services.sion_legacy_importer import import_planner_definition


class Command(BaseCommand):
    help = "Persist audited legacy SION planner configuration (inactive by default)."

    def add_arguments(self, parser):
        parser.add_argument("--sion", action="append", choices=sorted(LEGACY_PLANNER_CONFIGURATIONS))
        parser.add_argument("--apply", action="store_true", help="Write configuration; default is dry-run.")

    def handle(self, *args, **options):
        norms = options["sion"] or sorted(LEGACY_PLANNER_CONFIGURATIONS)
        for norm in norms:
            definition = LEGACY_PLANNER_CONFIGURATIONS[norm]
            self.stdout.write(
                f"{norm}: rules={len(definition['rules'])} actions={len(definition['actions'])} "
                f"mappings={len(definition['mappings'])} active=false"
            )
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run only; pass --apply to persist."))
            return
        try:
            with transaction.atomic():
                results = [import_planner_definition(norm, LEGACY_PLANNER_CONFIGURATIONS[norm]) for norm in norms]
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        for result in results:
            self.stdout.write(self.style.SUCCESS(
                f"{result['norm']}: created profile={int(result['profile_created'])} "
                f"rules={result['rules_created']} actions={result['actions_created']} "
                f"mappings={result['mappings_created']}"
            ))
