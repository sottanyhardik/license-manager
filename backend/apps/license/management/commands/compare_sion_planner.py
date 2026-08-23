from django.core.management.base import BaseCommand, CommandError

from apps.license.services.sion_shadow_comparison import (
    SUPPORTED_SHADOW_NORMS,
    compare_golden_norm,
)


class Command(BaseCommand):
    help = "Read-only exact shadow comparison of one SION generic planner against its legacy golden contract."

    def add_arguments(self, parser):
        parser.add_argument("--sion", required=True, type=str.upper, choices=SUPPORTED_SHADOW_NORMS)
        parser.add_argument(
            "--dataset", choices=("golden", "current"), default="golden",
            help="Golden is the immutable captured legacy oracle; current requires a separately reconciled real-data adapter.",
        )
        parser.add_argument(
            "--source", choices=("audited", "database"), default="audited",
            help="Execute audited migration documents or persisted DB profile rows.",
        )

    def handle(self, *args, **options):
        if options["dataset"] == "current":
            raise CommandError(
                "The current-data adapter is not enabled: running legacy planners can read/create supporting master "
                "rows, so it cannot satisfy the read-only shadow contract. Use --dataset golden until the canonical "
                "read-only record adapter is available."
            )
        norm = options["sion"]
        profile = None
        if options["source"] == "database":
            from apps.license.models import SionPlanningProfile
            profile = SionPlanningProfile.objects.filter(
                sion__norm_class__iexact=norm,
            ).order_by("-is_active", "-version", "-pk").first()
            if profile is None:
                raise CommandError(f"No persisted planning profile exists for {norm}.")
        results = compare_golden_norm(norm, profile=profile)
        differences = sum(len(result.differences) for result in results)
        for result in results:
            self.stdout.write(f"  {result.name}: {'PASS' if result.passed else 'FAIL'}")
            for difference in result.differences:
                location = f" row={difference.row_index}" if difference.row_index is not None else ""
                self.stdout.write(
                    f"    {difference.dimension}{location}: legacy={difference.legacy!r} generic={difference.generic!r}"
                )
        summary = (
            f"{norm}: source={options['source']} cases={len(results)} "
            f"exact_match={len(results) - sum(not r.passed for r in results)} differences={differences}"
        )
        if differences:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(summary + " PASS"))
