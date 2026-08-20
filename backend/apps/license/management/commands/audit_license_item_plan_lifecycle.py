from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import Count


class Command(BaseCommand):
    help = "Read-only lifecycle and identity audit for LicenseItemPlan rows."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Required acknowledgement; command never writes.")

    def handle(self, *args, **options):
        if not options["dry_run"]:
            self.stderr.write("This audit is read-only; pass --dry-run to run it.")
            return
        from apps.license.models import LicenseItemPlan
        from apps.license.services.plan_lifecycle import resolve_plan_sion

        plans = LicenseItemPlan.objects.select_related("license", "import_item", "item_name")
        rows = list(plans)
        active = [p for p in rows if p.is_active and not p.is_deleted and not p.is_cancelled]
        resolutions = [resolve_plan_sion(plan) for plan in rows]
        def grouped(field):
            return dict(plans.values(field).annotate(count=Count("id")).order_by(field).values_list(field, "count"))
        self.stdout.write(f"total_plan_rows: {len(rows)}")
        self.stdout.write(f"rows_by_licence: {grouped('license_id')}")
        self.stdout.write(f"rows_by_licence_item: {grouped('import_item_id')}")
        self.stdout.write(f"rows_by_sion: {dict(Counter(r.sion_code for r in resolutions if r.status == 'RESOLVED'))}")
        self.stdout.write(f"rows_by_planning_target_item: {grouped('item_name_id')}")
        duplicates = active and LicenseItemPlan.objects.filter(
            is_active=True, is_deleted=False, is_cancelled=False
        ).values("license_id", "import_item_id", "item_name_id").annotate(count=Count("id")).filter(count__gt=1).count()
        self.stdout.write(f"duplicate_active_plan_identities: {duplicates or 0}")
        self.stdout.write(f"multiple_active_candidates: {duplicates or 0}")
        self.stdout.write(f"active_plans: {len(active)}")
        self.stdout.write(f"inactive_plans: {sum(1 for p in rows if not p.is_active)}")
        self.stdout.write(f"deleted_plans: {sum(1 for p in rows if p.is_deleted)}")
        self.stdout.write(f"cancelled_plans: {sum(1 for p in rows if p.is_cancelled)}")
        self.stdout.write(f"resolved_sion_plans: {sum(r.status == 'RESOLVED' for r in resolutions)}")
        self.stdout.write(f"unresolved_sion_plans: {sum(r.status == 'UNRESOLVED' for r in resolutions)}")
        self.stdout.write(f"ambiguous_sion_plans: {sum(r.status == 'AMBIGUOUS' for r in resolutions)}")
        self.stdout.write(f"sion_resolution_sources: {dict(Counter(r.source for r in resolutions))}")
        self.stdout.write(f"plans_missing_planning_target_item: {sum(1 for p in rows if not p.item_name_id)}")
        self.stdout.write(f"plans_zero_quantity_only: {sum(1 for p in rows if not p.planned_quantity and p.planned_cif_fc > 0)}")
        self.stdout.write(f"plans_zero_cif_only: {sum(1 for p in rows if p.planned_quantity > 0 and not p.planned_cif_fc)}")
        self.stdout.write(f"plans_zero_quantity_and_cif: {sum(1 for p in rows if not p.planned_quantity and not p.planned_cif_fc)}")
        self.stdout.write(f"orphaned_plan_references: {sum(1 for p in rows if not p.license_id or not p.import_item_id)}")
        self.stdout.write(f"contradictory_lifecycle_states: {sum(1 for p in rows if p.is_active and (p.is_deleted or p.is_cancelled))}")
