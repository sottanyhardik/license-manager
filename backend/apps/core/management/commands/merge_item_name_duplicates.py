"""Transactional exact-name ItemNameModel merger.

Only names equal after trim/collapse/case normalization are eligible.  This
command never strips norm suffixes or applies product-family heuristics.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails
from apps.core.models import ItemNameModel
from apps.license.models import (
    LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan,
    SionInputAliasConfig, SionPlanningOutputMapping, SionPlanningPercentageRow,
    SionPlanningRule, SionPlanningUnitValueRow,
)


REFERENCE_FIELDS = (
    (SionPlanningRule, "import_item"),
    (SionPlanningPercentageRow, "import_item"),
    (SionPlanningUnitValueRow, "import_item"),
    (RowDetails, "planning_target_item"),
    (AllotmentItems, "planning_target_item"),
    (LicenseItemPlan, "item_name"),
    (LicenseExportItemModel, "item"),
    (SionInputAliasConfig, "output_item"),
    (SionPlanningOutputMapping, "output_item"),
)


class Command(BaseCommand):
    help = "Merge only exactly normalized duplicate ItemNameModel rows after explicitly repointing all references."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Perform the transactional merge. Default is dry-run.")

    def handle(self, *args, **options):
        apply = options["apply"]
        groups = defaultdict(list)
        for item in ItemNameModel.objects.order_by("pk").prefetch_related("norms"):
            groups[ItemNameModel.normalize_name(item.name)].append(item)
        groups = [members for members in groups.values() if len(members) > 1]
        self.stdout.write(f"Eligible exact duplicate groups: {len(groups)}")
        if not apply:
            for members in groups:
                self.stdout.write(f"  {members[0].normalized_name}: survivor={members[0].pk}, duplicates={[i.pk for i in members[1:]]}")
            self.stdout.write("Dry run only. Re-run with --apply after reviewing this output.")
            return

        try:
            with transaction.atomic():
                for members in groups:
                    locked = list(ItemNameModel.objects.select_for_update().filter(pk__in=[item.pk for item in members]).order_by("pk"))
                    survivor, *duplicates = locked
                    survivor.norms.add(*[norm.pk for item in locked for norm in item.norms.all()])
                    for duplicate in duplicates:
                        # The source-item M2M is a business reference too. A
                        # duplicate junction is redundant after identity merge;
                        # preserve one link, never the source row.
                        through = LicenseImportItemsModel.items.through
                        source_ids = list(through.objects.filter(itemnamemodel_id=duplicate.pk).values_list("licenseimportitemsmodel_id", flat=True))
                        for source_id in source_ids:
                            through.objects.get_or_create(licenseimportitemsmodel_id=source_id, itemnamemodel_id=survivor.pk)
                        through.objects.filter(itemnamemodel_id=duplicate.pk).delete()
                        for model, field in REFERENCE_FIELDS:
                            model._default_manager.filter(**{f"{field}_id": duplicate.pk}).update(**{f"{field}_id": survivor.pk})
                        remaining = sum(model._default_manager.filter(**{f"{field}_id": duplicate.pk}).count() for model, field in REFERENCE_FIELDS)
                        if remaining or through.objects.filter(itemnamemodel_id=duplicate.pk).exists():
                            raise CommandError(f"Duplicate ItemNameModel {duplicate.pk} still has references; transaction rolled back.")
                        duplicate.delete()
        except IntegrityError as exc:
            raise CommandError(f"A uniqueness collision prevents a safe merge; no changes committed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS("Exact duplicate ItemNameModel rows merged with explicit reference repointing."))
