"""Map BOE/allotment actual usage to consolidated planning targets safely."""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
from apps.core.constants import DEBIT
from apps.license.services.planning_actual_target_mapping import resolve_targets_for_source


class Command(BaseCommand):
    help = "Dry-run or apply deterministic BOE/unlinked-allotment planning-target mapping. Never guesses names."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist deterministic mappings. Default is dry-run.")

    def handle(self, *args, **options):
        apply = options["apply"]
        counts = Counter()
        target_cache = {}
        boe_rows = annotate_and_exclude_hidden(
            RowDetails.objects.filter(transaction_type=DEBIT), boe_field="bill_of_entry"
        ).select_related("sr_number")
        allotment_rows = AllotmentItems.objects.filter(
            allotment__bill_of_entry__isnull=True, allotment__is_boe=False, is_boe=False,
        ).select_related("item")

        with transaction.atomic():
            for usage, source in [
                *((row, row.sr_number) for row in boe_rows),
                *((row, row.item) for row in allotment_rows),
            ]:
                if source is None:
                    counts["UNMAPPED_NO_TARGET"] += 1
                    continue
                before = (usage.planning_target_item_id, usage.planning_mapping_status, usage.planning_mapping_source)
                resolution = target_cache.get(source.pk)
                if resolution is None:
                    resolution = resolve_targets_for_source(source)
                    target_cache[source.pk] = resolution
                if usage.planning_target_item_id:
                    if usage.planning_target_item_id in resolution.target_ids:
                        usage.planning_mapping_status = "MAPPED_EXPLICIT"
                        usage.planning_mapping_source = "USER_SELECTED"
                    else:
                        usage.planning_mapping_status = "INVALID_PERSISTED_TARGET"
                        usage.planning_mapping_source = ""
                elif resolution.is_unique:
                    usage.planning_target_item_id = resolution.target_ids[0]
                    usage.planning_mapping_status = "MAPPED_DETERMINISTIC"
                    usage.planning_mapping_source = "UNIQUE_TARGET"
                elif resolution.target_ids:
                    usage.planning_mapping_status = "UNMAPPED_AMBIGUOUS"
                    usage.planning_mapping_source = ""
                else:
                    usage.planning_mapping_status = "UNMAPPED_NO_TARGET"
                    usage.planning_mapping_source = ""
                counts[usage.planning_mapping_status] += 1
                if apply and before != (usage.planning_target_item_id, usage.planning_mapping_status, usage.planning_mapping_source):
                    usage.save(update_fields=("planning_target_item", "planning_mapping_status", "planning_mapping_source", "modified_on"))
            if not apply:
                transaction.set_rollback(True)

        self.stdout.write(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
        for status in ("MAPPED_EXPLICIT", "MAPPED_DETERMINISTIC", "UNMAPPED_AMBIGUOUS", "UNMAPPED_NO_TARGET", "INVALID_PERSISTED_TARGET"):
            self.stdout.write(f"{status}: {counts[status]}")
