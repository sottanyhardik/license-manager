#!/usr/bin/env python
"""Debug script to inspect LicenseItemPlan structure and identify root cause."""

import django
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from apps.license.models import LicenseItemPlan, LicenseDetailsModel
from apps.core.models import ItemNameModel
from datetime import date, timedelta
from django.db.models import Q
from apps.core.constants import GE, MI, CO

# Get a license with E1 planning
license_obj = (LicenseDetailsModel.objects
    .filter(
        purchase_status__code__in=[GE, MI, CO],
        flags__is_active=True,
        license_expiry_date__gt=date.today() - timedelta(days=30),
        export_license__norm_class__norm_class='E1'
    )
    .select_related(
        'export_license',
        'export_license__norm_class'
    )
    .prefetch_related(
        'import_license__items',
        'import_license__items__sion_norm_class'
    )
    .first()
)

if not license_obj:
    print("No E1 license found")
    sys.exit(1)

print(f"License: {license_obj.license_number}")
print(f"Norm: {license_obj.export_license.norm_class.norm_class if license_obj.export_license else 'N/A'}")
print(f"\n=== LicenseItemPlan rows for this license ===")

plans = (LicenseItemPlan.objects
    .filter(license=license_obj)
    .select_related('item_name')
    .values('id', 'item_name_id', 'import_item_id', 'item_name__name',
            'planned_quantity', 'planned_cif_fc'))

item_names_in_plans = {}
for plan in plans[:10]:  # First 10 rows
    item_name_str = plan['item_name__name'] if plan['item_name__name'] else f"[NULL - import_item_id={plan['import_item_id']}]"
    print(f"  item_name_id={plan['item_name_id']:<5} item_name='{item_name_str}' planned_qty={float(plan['planned_quantity'] or 0):.2f} planned_cif={float(plan['planned_cif_fc'] or 0):.2f}")
    if plan['item_name_id']:
        item_names_in_plans[plan['item_name_id']] = item_name_str

print(f"\nTotal plans: {plans.count()}")

if not item_names_in_plans:
    print("\n⚠️ WARNING: No item_name_id values found in plans!")
    print("Plans are being created with item_name_id = NULL")
    print("This explains why planned_import_items aren't being matched in _build_license_row()")
    sys.exit(0)

# Now check: are these item_name_ids being added to all_items in the pivot?
print(f"\n=== Checking if planned item names exist in ItemNameModel ===")
planned_items = ItemNameModel.objects.filter(id__in=item_names_in_plans.keys()).values('id', 'name')
for item in planned_items:
    print(f"  id={item['id']} name='{item['name']}'")

print(f"\n=== Import items on this license ===")
import_items = license_obj.import_license.all()
for ii in import_items[:5]:
    print(f"  Import item {ii.id}: qty={ii.available_quantity}, description='{ii.description}'")
    for item in ii.items.all()[:3]:
        print(f"    → tagged with '{item.name}'")
