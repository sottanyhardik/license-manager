"""Plan a SION through the same DB-driven orchestration used by the API.

The positional norm argument is retained for backwards compatibility.  New
automation may use ``--sion``.  The safe/default mode is NEW; ``--all`` keeps
its historical meaning of reprocessing the full eligible universe for the
selected norm (it never means "all SIONs").
"""

from datetime import timedelta
from time import monotonic

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import SionNormClassModel
from apps.license.models import LicenseDetailsModel
from apps.license.services.sion_planning_execution import (
    PlannerConfigurationError,
    SionPlanningExecutionService,
)


def _fmt_duration(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


class Command(BaseCommand):
    help = "Plan one SION using its saved active database rules."

    def add_arguments(self, parser):
        parser.add_argument(
            "norms_class",
            nargs="?",
            type=str.upper,
            help="Backward-compatible selected SION (for example E1).",
        )
        parser.add_argument(
            "--sion",
            dest="sion_code",
            type=str.upper,
            metavar="SION",
            help="Selected SION (for example E1).",
        )
        parser.add_argument(
            "--license",
            dest="license_number",
            metavar="LICENSE_NUMBER",
            help="Optionally restrict planning to one license number.",
        )
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument(
            "--new",
            dest="mode",
            action="store_const",
            const="NEW",
            help="Plan only canonical identities that are not already planned (default).",
        )
        modes.add_argument(
            "--all",
            dest="mode",
            action="store_const",
            const="ALL",
            help="Force reprocess the full eligible universe for this SION.",
        )
        parser.set_defaults(mode="NEW")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview through the canonical service without writing plans.",
        )

    def handle(self, *args, **options):
        positional = options.get("norms_class")
        selected = options.get("sion_code")
        if positional and selected and positional != selected:
            raise CommandError(
                f"Conflicting SION values: positional {positional!r} and --sion {selected!r}."
            )
        code = selected or positional
        if not code:
            raise CommandError("Select exactly one SION using --sion E1 or the positional E1 argument.")

        try:
            sion = SionNormClassModel.objects.get(norm_class__iexact=code)
        except SionNormClassModel.DoesNotExist as exc:
            raise CommandError(f"Unknown SION {code!r}.") from exc
        except SionNormClassModel.MultipleObjectsReturned as exc:
            raise CommandError(f"SION {code!r} is not unique in the canonical master.") from exc

        license_ids = None
        license_number = options.get("license_number")
        if license_number:
            ids = list(
                LicenseDetailsModel.objects.filter(license_number=license_number)
                .order_by("pk").values_list("pk", flat=True)
            )
            if not ids:
                raise CommandError(f"License {license_number!r} not found.")
            if len(ids) != 1:
                raise CommandError(
                    f"License number {license_number!r} is ambiguous; use the API's ID restriction."
                )
            license_ids = ids

        mode = options["mode"]
        dry_run = options["dry_run"]
        self.stdout.write(self.style.MIGRATE_HEADING("Starting SION planning…"))
        self.stdout.write(f"  SION        : {sion.norm_class}")
        self.stdout.write(f"  Mode        : {'FORCE ALL' if mode == 'ALL' else 'NEW'}")
        if license_number:
            self.stdout.write(f"  License     : {license_number}")
        if dry_run:
            self.stdout.write("  " + self.style.WARNING("Dry Run     : nothing will be saved"))

        started = monotonic()
        try:
            result = SionPlanningExecutionService.plan_sion(
                sion,
                license_ids=license_ids,
                persist=not dry_run,
                mode=mode,
            )
        except (PlannerConfigurationError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        summary = result.get("summary", {})
        rules = summary.get("rules", len(result.get("rules_executed", result.get("rules_processed", ()))))
        eligible = summary.get("eligible_licenses", result.get("eligible_licenses", 0))
        matched = summary.get("matched_items", result.get("matched_items", 0))
        planned = result.get("planned_licenses", summary.get("planned_licenses", 0))
        already = result.get("already_planned", summary.get("already_planned", 0))
        skipped = result.get("skipped_count", summary.get("skipped_count", 0))
        failed = result.get("failed_count", summary.get("failed_count", 0))
        shortages = result.get("shortages", summary.get("shortages", 0))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("SION planning completed"))
        self.stdout.write(f"  SION                : {sion.norm_class}")
        self.stdout.write(f"  Mode                : {'FORCE ALL' if mode == 'ALL' else 'NEW'}")
        self.stdout.write(f"  Rules processed     : {rules}")
        self.stdout.write(f"  Eligible licenses   : {eligible}")
        self.stdout.write(f"  Matched items       : {matched}")
        self.stdout.write(f"  Planned licenses    : {planned}")
        self.stdout.write(f"  Already planned     : {already}")
        self.stdout.write(f"  Skipped             : {skipped}")
        self.stdout.write(f"  Failed              : {failed}")
        self.stdout.write(f"  Shortages           : {shortages}")
        self.stdout.write(f"  Execution time      : {_fmt_duration(monotonic() - started)}")
        # Stable labels retained for scripts which parsed the legacy summary.
        self.stdout.write(f"  Total Licenses       : {eligible}")
        self.stdout.write(f"  Successfully Planned : {planned}")
        self.stdout.write(f"  Already Planned      : {already}")
        if dry_run:
            self.stdout.write("  " + self.style.WARNING("DRY RUN — no data was modified."))
