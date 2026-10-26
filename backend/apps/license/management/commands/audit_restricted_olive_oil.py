"""Read-only audit of Olive Oil records on the restricted norm classes (A3627, E132).

Reports every stored Olive Oil item name, import item, plan row and SION output
mapping attached to a restricted norm. It never writes: correcting a record
needs the intended product established from the SION data first, so the
correction is a separate, reviewed step.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.core.models import ItemNameModel
from apps.license.models import (
    LicenseImportItemsModel, LicenseItemPlan, SionPlanningOutputMapping, SionPlanningRule,
)
from apps.license.services.product_norm_guard import RESTRICTED_OLIVE_OIL_NORMS, product_base_name


class Command(BaseCommand):
    help = "Report (read-only) Olive Oil records on norm classes A3627 and E132 for manual review."

    def handle(self, *args, **options):
        restricted = sorted(RESTRICTED_OLIVE_OIL_NORMS)

        olive_names = list(
            ItemNameModel.objects
            .filter(name__istartswith="OLIVE OIL")
            .filter(Q(sion_norm_class__norm_class__in=restricted) | Q(norms__norm_class__in=restricted))
            .distinct()
            .order_by("name")
        )
        olive_names = [name for name in olive_names if product_base_name(name.name) == "OLIVE OIL"]
        self.stdout.write(f"Olive Oil item names on restricted norms: {len(olive_names)}")
        for name in olive_names:
            self.stdout.write(f"  item_name id={name.id} name={name.name!r}")

        olive_ids = [name.id for name in olive_names]

        import_items = (
            LicenseImportItemsModel.objects
            .filter(items__in=olive_ids)
            .select_related("license", "hs_code")
            .distinct()
        )
        self.stdout.write(f"Import items linked to them: {import_items.count()}")
        for item in import_items:
            self.stdout.write(
                f"  import_item id={item.id} license={item.license.license_number!r} "
                f"hsn={item.hs_code.hs_code if item.hs_code_id else None!r} "
                f"description={item.description!r}"
            )

        plans = LicenseItemPlan.objects.filter(item_name_id__in=olive_ids).select_related("license", "item_name")
        self.stdout.write(f"Plan rows on these item names: {plans.count()}")
        for plan in plans:
            self.stdout.write(
                f"  plan id={plan.id} license={plan.license.license_number!r} item_name={plan.item_name.name!r}"
            )

        mappings = SionPlanningOutputMapping.objects.filter(output_item_id__in=olive_ids).select_related("output_item")
        self.stdout.write(f"SION output mappings to these item names: {mappings.count()}")
        for mapping in mappings:
            self.stdout.write(
                f"  mapping id={mapping.id} stable_key={mapping.stable_key!r} output_item={mapping.output_item.name!r}"
            )

        rules = SionPlanningRule.objects.filter(sion__norm_class__in=restricted, execution_output__icontains="olive")
        self.stdout.write(f"SION planning rules on restricted norms with an Olive Oil output: {rules.count()}")
        for rule in rules:
            self.stdout.write(f"  rule id={rule.id} stable_key={rule.stable_key!r} output={rule.execution_output!r}")

        self.stdout.write("Read-only: no records were modified.")
