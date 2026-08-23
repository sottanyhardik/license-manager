"""Promote legacy actual-detail mappings to BOE/allotment parent mappings."""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Dry-run or apply canonical planning target mappings for all BOEs and allotments."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist unambiguous parent mappings.")

    @staticmethod
    def _resolution(detail_rows):
        """Return target/status without inventing a target for conflicting rows."""
        targets = {row.planning_target_item_id for row in detail_rows if row.planning_target_item_id}
        if len(targets) == 1:
            return targets.pop(), "MAPPED_EXPLICIT", "MIGRATED_DETAIL_MAPPING"
        if len(targets) > 1:
            return None, "UNMAPPED_AMBIGUOUS", ""

        # No legacy selection: use the existing configuration-driven resolver
        # and only promote a target when every source resolves to the same one.
        from apps.license.services.planning_actual_target_mapping import resolve_targets_for_source
        candidates = set()
        for row in detail_rows:
            source = getattr(row, "sr_number", None) or getattr(row, "item", None)
            if not source:
                continue
            resolution = resolve_targets_for_source(source)
            if not resolution.is_unique:
                return None, "UNMAPPED_AMBIGUOUS", ""
            candidates.add(resolution.target_ids[0])
        if len(candidates) == 1:
            return candidates.pop(), "MAPPED_DETERMINISTIC", "UNIQUE_TARGET"
        return None, "UNMAPPED_NO_TARGET" if not candidates else "UNMAPPED_AMBIGUOUS", ""

    def handle(self, *args, **options):
        from apps.allotment.models import AllotmentModel
        from apps.bill_of_entry.models import BillOfEntryModel

        apply = options["apply"]
        counts = Counter()
        groups = (
            ("BOE", BillOfEntryModel.objects.prefetch_related("item_details__sr_number")),
            ("ALLOTMENT", AllotmentModel.objects.prefetch_related("allotment_details__item")),
        )
        with transaction.atomic():
            for label, parents in groups:
                for parent in parents:
                    rows = list(parent.item_details.all() if label == "BOE" else parent.allotment_details.all())
                    if not rows:
                        continue
                    target_id, status, source = self._resolution(rows)
                    counts[f"{label}:{status}"] += 1
                    self.stdout.write(f"{label} {parent.pk}: {status}" + (f" -> {target_id}" if target_id else ""))
                    if apply:
                        parent.planning_target_item_id = target_id
                        parent.planning_mapping_status = status
                        parent.planning_mapping_source = source
                        parent.save(update_fields=["planning_target_item", "planning_mapping_status", "planning_mapping_source", "modified_on"])
            if not apply:
                transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS("; ".join(f"{key}={value}" for key, value in sorted(counts.items()))))
