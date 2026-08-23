from django.core.management.base import BaseCommand, CommandError

from apps.license.services.sion_shadow_comparison import SUPPORTED_SHADOW_NORMS, compare_golden_norm


class Command(BaseCommand):
    help = "Run read-only exact golden shadow comparison for every migrated SION planner."

    def add_arguments(self, parser):
        parser.add_argument("--source", choices=("audited", "database"), default="audited")

    def handle(self, *args, **options):
        failures = []
        for norm in SUPPORTED_SHADOW_NORMS:
            profile = None
            if options["source"] == "database":
                from apps.license.models import SionPlanningProfile
                profile = SionPlanningProfile.objects.filter(
                    sion__norm_class__iexact=norm,
                ).order_by("-is_active", "-version", "-pk").first()
                if profile is None:
                    self.stdout.write(f"{norm:<7} FAIL no persisted profile")
                    failures.append(norm)
                    continue
            results = compare_golden_norm(norm, profile=profile)
            differences = sum(len(result.differences) for result in results)
            status = "PASS" if not differences else "FAIL"
            self.stdout.write(f"{norm:<7} {status} cases={len(results)} differences={differences}")
            if differences:
                failures.append(norm)
        if failures:
            raise CommandError(f"Shadow equivalence failed: {', '.join(failures)}")
        self.stdout.write(self.style.SUCCESS(
            f"All SION planner golden comparisons passed exactly (source={options['source']})."
        ))
