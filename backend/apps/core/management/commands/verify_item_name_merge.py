"""Post-merge referential-conservation audit for ItemNameModel consolidation."""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails
from apps.core.models import ItemNameModel
from apps.license.models import (
    LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan,
    SionInputAliasConfig, SionPlanningOutputMapping, SionPlanningPercentageRow,
    SionPlanningRule, SionPlanningUnitValueRow,
)


REFERENCES = (
    (SionPlanningRule, "import_item_id"),
    (SionPlanningPercentageRow, "import_item_id"),
    (SionPlanningUnitValueRow, "import_item_id"),
    (RowDetails, "planning_target_item_id"),
    (AllotmentItems, "planning_target_item_id"),
    (LicenseItemPlan, "item_name_id"),
    (LicenseExportItemModel, "item_id"),
    (SionInputAliasConfig, "output_item_id"),
    (SionPlanningOutputMapping, "output_item_id"),
)


class Command(BaseCommand):
    help = "Verify every ItemNameModel FK/M2M relationship after master consolidation. Read-only."

    def handle(self, *args, **options):
        valid_ids = set(ItemNameModel.objects.values_list("pk", flat=True))
        failures = []
        totals = {}
        for model, field in REFERENCES:
            ids = set(model.objects.exclude(**{f"{field}__isnull": True}).values_list(field, flat=True))
            missing = ids - valid_ids
            totals[f"{model._meta.label}.{field[:-3]}"] = model.objects.exclude(**{f"{field}__isnull": True}).count()
            if missing:
                failures.append(f"{model._meta.label}.{field} points to missing ItemNameModel IDs: {sorted(missing)}")

        through = LicenseImportItemsModel.items.through
        m2m_ids = set(through.objects.values_list("itemnamemodel_id", flat=True))
        missing_m2m = m2m_ids - valid_ids
        totals["license.LicenseImportItemsModel.items (M2M)"] = through.objects.count()
        if missing_m2m:
            failures.append(f"LicenseImportItemsModel.items M2M points to missing ItemNameModel IDs: {sorted(missing_m2m)}")

        duplicate_keys = list(
            ItemNameModel.objects.values("normalized_name").exclude(normalized_name__isnull=True)
            .annotate(count=Count("pk")).filter(count__gt=1)
        )
        if duplicate_keys:
            failures.append(f"Remaining normalized duplicate names: {duplicate_keys}")

        for name, count in sorted(totals.items()):
            self.stdout.write(f"{name}: {count}")
        if failures:
            raise CommandError("\n".join(failures))
        self.stdout.write(self.style.SUCCESS("PASS: all ItemNameModel FK and M2M references resolve to surviving master rows."))
