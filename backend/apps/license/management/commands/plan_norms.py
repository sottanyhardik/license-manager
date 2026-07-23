"""
Management command — run Auto Plan for all licenses of a given Norms Class.

Usage
-----
    python manage.py plan_norms E1
    python manage.py plan_norms E5 --pending-only
    python manage.py plan_norms E1 --license 3411007711
    python manage.py plan_norms E1 --force
    python manage.py plan_norms E5 --dry-run
    python manage.py plan_norms E1 --force --dry-run

Arguments
---------
    norms_class     Required. E1, E5, E132, or any registered norm.

Optional flags
--------------
    --license       Process only the specified license number.
    --pending-only  Skip licenses already ≥ 99 % planned.
                    (default: skip already-planned unless --force is set)
    --force         Re-plan even fully-planned licenses (overrides --pending-only).
    --dry-run       Compute and display what would be saved without committing.
"""

import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from apps.license.services.norm_plan import detect_norm
from apps.license.services.planner_factory import PlannerFactory


# ── helpers ──────────────────────────────────────────────────────────────────

def _fmt_duration(seconds: float) -> str:
    """Format elapsed seconds as HH:MM:SS."""
    return str(timedelta(seconds=int(seconds)))


def _is_fully_planned(license_obj, threshold: float = 0.99) -> bool:
    """Return True when the existing plan covers ≥ *threshold* of balance CIF."""
    bal = float(license_obj.balance_cif or 0)
    if bal <= 0:
        return False
    from django.db.models import Sum
    total = float(
        LicenseItemPlan.objects
        .filter(license=license_obj)
        .aggregate(t=Sum("planned_cif_fc"))["t"] or 0
    )
    return total >= bal * threshold


def _save_lines(license_obj, lines: list[dict]) -> None:
    """Full-replace: delete existing plan, insert new lines atomically."""
    from apps.license.services.plan_enforcement import save_plan_lines_for_license
    save_plan_lines_for_license(license_obj, lines)


# ── command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Run Auto Plan for all licenses belonging to a specific Norms Class."

    def add_arguments(self, parser):
        parser.add_argument(
            "norms_class",
            type=str.upper,
            help=(
                "Norm identifier to process (E1, E5, E132, …). "
                f"Supported: {', '.join(PlannerFactory.supported_norms())}."
            ),
        )
        parser.add_argument(
            "--license",
            dest="license_number",
            metavar="LICENSE_NUMBER",
            default=None,
            help="Process only the specified license number.",
        )
        parser.add_argument(
            "--all",
            dest="replan_all",
            action="store_true",
            default=False,
            help="Re-plan ALL licenses, including those already ≥ 99 %% planned.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Compute plans and print them without saving any changes.",
        )

    # ── main ─────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        norms_class: str = options["norms_class"]
        license_number   = options["license_number"]
        replan_all: bool = options["replan_all"]
        dry_run: bool    = options["dry_run"]

        # Validate norm.
        if not PlannerFactory.is_supported(norms_class):
            raise CommandError(
                f"Norm '{norms_class}' is not supported. "
                f"Supported: {', '.join(PlannerFactory.supported_norms())}."
            )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Starting Auto Plan…"))
        self.stdout.write("")
        self.stdout.write(f"  Norms Class : {norms_class}")
        if license_number:
            self.stdout.write(f"  License     : {license_number}")
        mode = "ALL licenses (--all)" if replan_all else "Not-yet-planned only"
        self.stdout.write(f"  Mode        : {mode}")
        if dry_run:
            self.stdout.write(
                "  " + self.style.WARNING("Dry Run     : nothing will be saved")
            )
        self.stdout.write("")

        # Build queryset.
        qs = (
            LicenseDetailsModel.objects
            .filter(flags__is_active=True, balance__balance_cif__gt=0)
            .prefetch_related(
                "export_license__norm_class",
                "import_license__items",
                "import_license__hs_code",
            )
            .select_related("balance")
            .order_by("license_date", "license_number")
        )
        if license_number:
            qs = qs.filter(license_number=license_number)
            if not qs.exists():
                raise CommandError(f"License '{license_number}' not found.")

        # Counters.
        total = skipped_norm = already_planned = succeeded = failed = 0
        failures: list[tuple[str, str]] = []

        start = time.monotonic()

        for lic in qs:  # prefetch_related is incompatible with iterator(); plain loop is correct
            # Verify norm at runtime.
            detected = detect_norm(lic)
            if detected != norms_class:
                skipped_norm += 1
                continue

            total += 1
            num = lic.license_number

            # Default: skip already-planned licenses.
            # --all: re-plan everything regardless of current plan status.
            if not replan_all and _is_fully_planned(lic):
                already_planned += 1
                self.stdout.write(
                    f"  Processing License : {num} … "
                    + self.style.WARNING("SKIPPED (Already Planned)")
                )
                continue

            # Run planner.
            try:
                result = PlannerFactory.run(lic, norms_class)

                if not result.lines:
                    already_planned += 1
                    self.stdout.write(
                        f"  Processing License : {num} … "
                        + self.style.WARNING("SKIPPED (No plannable items)")
                    )
                    continue

                if dry_run:
                    total_cif = sum(ln["planned_cif_fc"] for ln in result.lines)
                    succeeded += 1
                    self.stdout.write(
                        f"  Processing License : {num} … "
                        + self.style.SUCCESS(
                            f"DRY-RUN OK  ({len(result.lines)} lines, "
                            f"${total_cif:,.2f} planned, "
                            f"${result.remaining_cif:,.2f} remaining)"
                        )
                    )
                else:
                    with transaction.atomic():
                        _save_lines(lic, result.lines)
                    succeeded += 1
                    self.stdout.write(
                        f"  Processing License : {num} … "
                        + self.style.SUCCESS("SUCCESS")
                    )

            except Exception as exc:  # noqa: BLE001
                failed += 1
                reason = str(exc)
                failures.append((num, reason))
                self.stdout.write(
                    f"  Processing License : {num} … "
                    + self.style.ERROR("FAILED")
                )
                self.stdout.write(
                    f"  {'':>29}Reason: {reason}"
                )

        elapsed = time.monotonic() - start

        # Summary.
        self.stdout.write("")
        self.stdout.write("-" * 50)
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Auto Plan Completed"))
        self.stdout.write("")
        self.stdout.write(f"  Norms Class          : {norms_class}")
        self.stdout.write(f"  Total Licenses       : {total}")
        self.stdout.write(
            f"  Successfully Planned : "
            + (self.style.SUCCESS(str(succeeded)) if succeeded else "0")
        )
        self.stdout.write(
            f"  Already Planned      : "
            + (self.style.WARNING(str(already_planned)) if already_planned else "0")
        )
        self.stdout.write(
            f"  Failed               : "
            + (self.style.ERROR(str(failed)) if failed else "0")
        )
        self.stdout.write(f"  Execution Time       : {_fmt_duration(elapsed)}")
        if dry_run:
            self.stdout.write("")
            self.stdout.write(
                "  " + self.style.WARNING("DRY RUN — no data was modified.")
            )
        self.stdout.write("")

        if failures:
            self.stdout.write(self.style.ERROR("Failed licenses:"))
            for num, reason in failures:
                self.stdout.write(f"  {num}: {reason}")
            self.stdout.write("")
