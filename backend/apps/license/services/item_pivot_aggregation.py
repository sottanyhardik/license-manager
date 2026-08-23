"""
Read-only Item Pivot Aggregation Service

Aggregates persisted LicenseItemPlan records into the pivot grid structure.
This service reads ONLY from saved canonical data — it never invokes planning
logic or calculates planned values. It is safe to call from GET endpoints.

All planned values are pre-computed and persisted by the planning write paths.
This service aggregates and presents them only.
"""
from decimal import Decimal
from typing import Dict, List, Any, Tuple
from django.db.models import Prefetch, Sum, Q
from django.db.models.functions import Coalesce

from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
)
from apps.core.models import ItemNameModel


class ItemPivotAggregationService:
    """
    Aggregates persisted LicenseItemPlan records into pivot grid format.

    Input: List of licenses to display
    Output: Per-license, per-item-name rows with:
      - planned_quantity (sum of all plan lines for this item)
      - planned_cif (sum of all plan lines for this item)
      - splits (list of individual plan line details)
      - effective_planned_cif (manual plan value, or 0 if no plan)
      - effective_planned_quantity (manual plan quantity, or 0 if no plan)

    This service reads ONLY from:
      - LicenseItemPlan (persisted plans)
      - LicenseImportItemsModel (available quantities)
      - ItemNameModel (split labels)

    It does NOT:
      - Call any planning logic
      - Call legacy planners (E1_plan, E5_plan, etc.)
      - Calculate planned values
      - Match against item names
      - Allocate quantities
      - Infer missing plans
    """

    @staticmethod
    def build_pivot_item_data(license_obj: LicenseDetailsModel) -> Dict[str, Dict[str, Any]]:
        """
        Build per-item-name pivot data for one license from persisted plans.

        Returns: {item_name: {
            'planned_quantity': total planned qty for this item across all plan lines,
            'planned_cif': total planned CIF for this item across all plan lines,
            'unit_price': calculated avg unit price (CIF / qty) or 0,
            'available_quantity': total available qty from import items with this item name,
            'splits': [ { split detail rows } ],
            'has_plan': bool (true if any plan line exists for any import item with this item name),
            'effective_planned_quantity': planned qty (0 if no plan),
            'effective_planned_cif': planned CIF (0 if no plan),
        }}
        """
        result = {}

        # 1. Fetch all persisted LicenseItemPlan records for this license
        plans = (
            LicenseItemPlan.objects
            .filter(license=license_obj)
            .select_related('import_item', 'item_name')
            .values(
                'import_item_id',
                'item_name__name',
                'planned_quantity',
                'unit_price',
                'planned_cif_fc',
            )
        )

        # 2. Group by item_name and aggregate
        plan_by_item_name = {}
        for plan in plans:
            item_name = plan['item_name__name'] or "Unspecified"
            if item_name not in plan_by_item_name:
                plan_by_item_name[item_name] = {
                    'total_qty': Decimal('0'),
                    'total_cif': Decimal('0'),
                    'count': 0,
                    'splits': [],
                }

            plan_by_item_name[item_name]['total_qty'] += Decimal(str(plan['planned_quantity'] or 0))
            plan_by_item_name[item_name]['total_cif'] += Decimal(str(plan['planned_cif_fc'] or 0))
            plan_by_item_name[item_name]['count'] += 1
            plan_by_item_name[item_name]['splits'].append(plan)

        # 3. Calculate available quantities per item name from import items
        import_items = (
            LicenseImportItemsModel.objects
            .filter(license=license_obj)
            .prefetch_related('items')
            .values_list('id', 'available_quantity')
        )

        available_by_item_name = {}
        for import_item_id, available_qty in import_items:
            items_for_import = (
                ItemNameModel.objects
                .filter(importitems_items__license_import_item_id=import_item_id)
                .values_list('name', flat=True)
            )
            for item_name in items_for_import:
                available_by_item_name[item_name] = (
                    available_by_item_name.get(item_name, Decimal('0')) + Decimal(str(available_qty or 0))
                )

        # 4. Build result with both manual plans and available quantities
        for item_name, plan_data in plan_by_item_name.items():
            total_qty = plan_data['total_qty']
            total_cif = plan_data['total_cif']
            unit_price = round(float(total_cif / total_qty), 2) if total_qty else 0.0

            result[item_name] = {
                'planned_quantity': float(total_qty),
                'planned_cif': float(total_cif),
                'unit_price': unit_price,
                'available_quantity': float(available_by_item_name.get(item_name, Decimal('0'))),
                'splits': plan_data['splits'],
                'has_plan': plan_data['count'] > 0,
                'effective_planned_quantity': float(total_qty),
                'effective_planned_cif': float(total_cif),
            }

        return result

    @staticmethod
    def build_notification_item_data(licenses: List[LicenseDetailsModel], item_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Build aggregated pivot data for multiple licenses across specified item names.

        Returns per-item summary:
        {item_name: {
            'total_planned_qty': sum across all licenses,
            'total_planned_cif': sum across all licenses,
            'total_available': sum of available quantities,
            'unit_price': blended average,
        }}
        """
        result = {}

        # Fetch all plans for all licenses in one batch
        plans = (
            LicenseItemPlan.objects
            .filter(license__in=licenses)
            .select_related('item_name')
            .values('item_name__name', 'planned_quantity', 'planned_cif_fc')
        )

        # Aggregate by item name
        for plan in plans:
            item_name = plan['item_name__name'] or "Unspecified"
            if item_name not in result:
                result[item_name] = {
                    'total_qty': Decimal('0'),
                    'total_cif': Decimal('0'),
                }

            result[item_name]['total_qty'] += Decimal(str(plan['planned_quantity'] or 0))
            result[item_name]['total_cif'] += Decimal(str(plan['planned_cif_fc'] or 0))

        # Calculate available quantities
        import_items = (
            LicenseImportItemsModel.objects
            .filter(license__in=licenses)
            .prefetch_related('items')
        )

        available_by_item = {}
        for import_item in import_items:
            for item in import_item.items.all():
                available_by_item[item.name] = (
                    available_by_item.get(item.name, Decimal('0')) +
                    Decimal(str(import_item.available_quantity or 0))
                )

        # Format result
        final_result = {}
        for item_name, data in result.items():
            total_qty = data['total_qty']
            total_cif = data['total_cif']
            unit_price = round(float(total_cif / total_qty), 2) if total_qty else 0.0

            final_result[item_name] = {
                'total_planned_qty': float(total_qty),
                'total_planned_cif': float(total_cif),
                'total_available': float(available_by_item.get(item_name, Decimal('0'))),
                'unit_price': unit_price,
            }

        return final_result
