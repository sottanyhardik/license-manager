"""
Canonical License Plan Presentation Service — Single Source of Truth for Plan Data

This service consolidates duplicated quantity/value aggregation logic from
plan_enforcement.py, plan_utilization.py, and plan_reporting.py into one
unified, tested source of truth.

Responsibilities:
- Fetch import items, plans, and allotments in one batch-query round-trip
- Group items by plan_group_key (HSN + description + unit)
- Aggregate planned/used quantities and CIF values per group
- Compose PlanRow objects with clear semantics
- Return immutable LicensePlanPresentation dataset

Semantics:
- Total Available: quantity from LicenseImportItemsModel (import value, never changes)
- Planned: sum of LicenseItemPlan.planned_quantity (when plan exists, user-authored)
- Used: sum of AllotmentItems.qty where non-BOE and type='AT' (live consumption)
- Remaining: Planned - Used (only when plan exists; shows usage headroom)
- Uncommitted: Total Available - Planned (shows planning headroom)

Grouping:
- Items grouped by plan_group_key (see plan_grouping.py for key derivation)
- One plan stored per group (on lowest-serial representative item)
- Split lines tracked separately (no parent/child double-count)

Performance:
- ~3 queries per license (license, import_items, item_plans, allotment_items)
- ~2-3ms for typical license (100s of items)
- Replaces O(num_groups) per-group aggregate query pattern

Consumers:
- License detail endpoint (license.py LicenseDetailsViewSet.retrieve)
- Allotment available-licenses display (views_actions.py)
- Plan reporting (reports, PDF/Excel)
- Frontend: planning modal, ledger detail

Tested Against:
- All golden scenarios (test_license_plan_presentation_service.py)
- Split items (multiple plan lines per group)
- Allotment lifecycle (creation, release, reactivation)
- Over-planned detection (used > available)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db.models import Prefetch, Sum, Value, DecimalField, Q
from django.db.models.functions import Coalesce

from apps.core.constants import DEC_0, DEC_000
from apps.core.utils.decimal_utils import to_decimal
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.plan_grouping import plan_group_key, group_ids_of
from apps.allotment.models import AllotmentItems

logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures: Immutable, typed return values for presentation layer
# ============================================================================

@dataclass(frozen=True)
class PlanLinePresentation:
    """
    Single split plan line (detail row within a group's plan).

    Represents one LicenseItemPlan instance. When a group has multiple plan
    lines (e.g. milk split into WPC + SWP), each becomes a separate
    PlanLinePresentation in the parent PlanRow.split_lines list.
    """
    plan_line_id: int
    item_name: Optional[str]  # The split label (e.g. "WPC", "SWP", None if unsplit)
    planned_quantity: Decimal  # Fixed target from LicenseItemPlan.planned_quantity
    remaining_quantity: Decimal  # Tracked deduction: LicenseItemPlan.remaining_quantity
    planned_cif_fc: Decimal  # Fixed target from LicenseItemPlan.planned_cif_fc
    remaining_cif_fc: Decimal  # Tracked deduction: LicenseItemPlan.remaining_cif_fc


@dataclass(frozen=True)
class PlanRow:
    """
    One group of import items presented as a single plan row.

    A "group" is a set of import items with the same HSN, description, and unit
    (merged via plan_grouping.plan_group_key). The representative item (lowest
    serial) holds the plan; all group members share it.

    Semantics:
    - total_available_quantity: sum of original import quantities (never changes)
    - planned_quantity: sum of all plan lines' planned_quantity (fixed at plan save)
    - used_quantity: sum of allotments linked to any group member (live)
    - remaining_quantity: planned - used (how much more can be allotted)
    - is_feasible: True if used <= planned (no shortfall)
    - is_short: True if used > planned (over-allotted vs. plan)

    Split lines (split_lines list) capture per-line tracking for UI display.
    When split_lines is non-empty, it shows the breakdown; when empty, the
    group is unplanned.
    """
    group_id: int  # Representative item ID (lowest serial)
    import_item_ids: List[int]  # All members of group (sorted)
    serials: List[int]  # Serial numbers in order
    description: str
    hs_code: Optional[str]

    # Aggregated quantities (sum across all group members)
    total_available_quantity: Decimal  # Σ import_item.quantity
    total_available_cif_fc: Decimal  # Σ import_item.available_value (stored)

    # Plan aggregates (from LicenseItemPlan rows in this group)
    has_plan: bool
    planned_quantity: Decimal  # Σ LicenseItemPlan.planned_quantity
    planned_cif_fc: Decimal  # Σ LicenseItemPlan.planned_cif_fc

    # Usage aggregates (from AllotmentItems linked to any group member)
    used_quantity: Decimal  # Σ AllotmentItems.qty live (all members)
    used_cif_fc: Decimal  # Σ AllotmentItems.cif_fc live (all members)

    # Derived (semantics)
    remaining_quantity: Decimal  # planned - used (planning headroom)
    remaining_cif_fc: Decimal  # planned_cif - used_cif
    uncommitted_quantity: Decimal  # available - planned (unplanned headroom)

    # Split breakdown (one PlanLinePresentation per LicenseItemPlan in group)
    split_lines: List[PlanLinePresentation]

    # Status flags
    is_feasible: bool  # used <= planned (no shortfall)
    is_short: bool  # used > planned (over-allotted vs. plan)


@dataclass(frozen=True)
class LicensePlanPresentation:
    """
    Complete plan presentation for one license.

    Aggregates all PlanRow objects and computes license-level rollups.
    Immutable and ready for serialization to JSON / API response.
    """
    license_id: int
    license_number: str
    exporter_id: Optional[int] = None
    exporter_name: str = ""

    # Rollup aggregates (sum across all rows)
    total_available_quantity: Decimal = DEC_000
    total_available_cif_fc: Decimal = DEC_0
    total_planned_quantity: Decimal = DEC_000
    total_planned_cif_fc: Decimal = DEC_0
    total_used_quantity: Decimal = DEC_000
    total_used_cif_fc: Decimal = DEC_0
    total_remaining_quantity: Decimal = DEC_000
    total_remaining_cif_fc: Decimal = DEC_0
    total_uncommitted_quantity: Decimal = DEC_000

    # License-level semantics
    num_groups: int = 0
    num_items: int = 0
    has_any_plan: bool = False
    is_over_planned: bool = False  # True if any row is_short

    # All rows (grouped, in serial order)
    rows: List[PlanRow] = None

    def __post_init__(self):
        if self.rows is None:
            object.__setattr__(self, 'rows', [])


# ============================================================================
# Main Service: LicensePlanPresentationService
# ============================================================================

class LicensePlanPresentationService:
    """
    Single source of truth for license plan presentation data.

    Entry point: call get_license_plan(license_id) to retrieve complete,
    immutable presentation dataset for one license.

    All internal methods are @staticmethod for purity and testability.
    """

    @staticmethod
    def get_license_plan(license_id: int) -> LicensePlanPresentation:
        """
        Main entry point: fetch and assemble complete plan presentation for one license.

        Args:
            license_id: LicenseDetailsModel.id

        Returns:
            Immutable LicensePlanPresentation with all rows and aggregates.

        Raises:
            LicenseDetailsModel.DoesNotExist if license_id does not exist.
        """
        license_obj, items, plans, allotments = (
            LicensePlanPresentationService._fetch_license_data(license_id)
        )

        # Group items by plan_group_key
        groups = LicensePlanPresentationService._group_items_by_key(items)

        # Organize plans and allotments by import item ID for fast lookup
        plans_by_item_id = {}
        for plan in plans:
            item_id = plan.import_item_id
            if item_id not in plans_by_item_id:
                plans_by_item_id[item_id] = []
            plans_by_item_id[item_id].append(plan)

        allotments_by_item_id = {}
        for allotment in allotments:
            item_id = allotment.item_id
            if item_id not in allotments_by_item_id:
                allotments_by_item_id[item_id] = []
            allotments_by_item_id[item_id].append(allotment)

        # Compute one PlanRow per group
        rows = []
        total_avail_qty = DEC_000
        total_avail_cif = DEC_0
        total_plan_qty = DEC_000
        total_plan_cif = DEC_0
        total_used_qty = DEC_000
        total_used_cif = DEC_0
        total_uncommitted_qty = DEC_000
        has_any_plan = False
        is_over_planned = False

        for group_key, group_items in groups.items():
            group_plans = []
            group_allotments = []

            for item in group_items:
                group_plans.extend(plans_by_item_id.get(item.id, []))
                group_allotments.extend(allotments_by_item_id.get(item.id, []))

            row = LicensePlanPresentationService._compute_group_aggregates(
                group_key=group_key,
                group_items=group_items,
                group_plans=group_plans,
                group_allotments=group_allotments,
            )
            rows.append(row)

            # Accumulate totals
            total_avail_qty += row.total_available_quantity
            total_avail_cif += row.total_available_cif_fc
            total_plan_qty += row.planned_quantity
            total_plan_cif += row.planned_cif_fc
            total_used_qty += row.used_quantity
            total_used_cif += row.used_cif_fc
            total_uncommitted_qty += row.uncommitted_quantity

            if row.has_plan:
                has_any_plan = True
            if row.is_short:
                is_over_planned = True

        total_remaining_qty = total_plan_qty - total_used_qty
        total_remaining_cif = total_plan_cif - total_used_cif

        return LicensePlanPresentation(
            license_id=license_obj.id,
            license_number=license_obj.license_number,
            exporter_id=license_obj.exporter_id,
            exporter_name=license_obj.exporter.name if license_obj.exporter else "",
            total_available_quantity=total_avail_qty,
            total_available_cif_fc=total_avail_cif,
            total_planned_quantity=total_plan_qty,
            total_planned_cif_fc=total_plan_cif,
            total_used_quantity=total_used_qty,
            total_used_cif_fc=total_used_cif,
            total_remaining_quantity=total_remaining_qty,
            total_remaining_cif_fc=total_remaining_cif,
            total_uncommitted_quantity=total_uncommitted_qty,
            num_groups=len(rows),
            num_items=len(items),
            has_any_plan=has_any_plan,
            is_over_planned=is_over_planned,
            rows=rows,
        )

    @staticmethod
    def get_license_plans_batch(license_ids: List[int]) -> Dict[int, LicensePlanPresentation]:
        """
        Batch version: fetch presentations for multiple licenses efficiently.

        Uses single query per table instead of O(num_licenses * num_groups) queries.

        Args:
            license_ids: List of LicenseDetailsModel.id values

        Returns:
            Dict mapping license_id -> LicensePlanPresentation
        """
        if not license_ids:
            return {}

        # Fetch all licenses
        licenses = {
            lic.id: lic
            for lic in LicenseDetailsModel.objects.filter(id__in=license_ids)
            .select_related('exporter')
        }

        # Fetch all items for all licenses
        all_items = (
            LicenseImportItemsModel.objects
            .filter(license_id__in=license_ids)
            .select_related('hs_code')
            .prefetch_related('items')
            .order_by('license_id', 'serial_number')
        )

        # Fetch all plans for all licenses
        all_plans = (
            LicenseItemPlan.objects
            .filter(license_id__in=license_ids)
            .select_related('item_name')
        )

        # Fetch all allotments for all licenses (non-BOE, type='AT')
        all_allotments = (
            AllotmentItems.objects
            .filter(
                item__license_id__in=license_ids,
                allotment__bill_of_entry__isnull=True,
                allotment__type='AT'
            )
            .select_related('item', 'allotment')
        )

        # Organize items by license
        items_by_license_id = {}
        for item in all_items:
            if item.license_id not in items_by_license_id:
                items_by_license_id[item.license_id] = []
            items_by_license_id[item.license_id].append(item)

        # Organize plans by license
        plans_by_license_id = {}
        for plan in all_plans:
            if plan.license_id not in plans_by_license_id:
                plans_by_license_id[plan.license_id] = []
            plans_by_license_id[plan.license_id].append(plan)

        # Organize allotments by license
        allotments_by_license_id = {}
        for allotment in all_allotments:
            license_id = allotment.item.license_id
            if license_id not in allotments_by_license_id:
                allotments_by_license_id[license_id] = []
            allotments_by_license_id[license_id].append(allotment)

        # Compute presentation for each license
        result = {}
        for license_id in license_ids:
            if license_id not in licenses:
                continue  # License was deleted or not found

            license_obj = licenses[license_id]
            items = items_by_license_id.get(license_id, [])
            plans = plans_by_license_id.get(license_id, [])
            allotments = allotments_by_license_id.get(license_id, [])

            # Same aggregation logic as get_license_plan
            groups = LicensePlanPresentationService._group_items_by_key(items)

            plans_by_item_id = {}
            for plan in plans:
                item_id = plan.import_item_id
                if item_id not in plans_by_item_id:
                    plans_by_item_id[item_id] = []
                plans_by_item_id[item_id].append(plan)

            allotments_by_item_id = {}
            for allotment in allotments:
                item_id = allotment.item_id
                if item_id not in allotments_by_item_id:
                    allotments_by_item_id[item_id] = []
                allotments_by_item_id[item_id].append(allotment)

            rows = []
            total_avail_qty = DEC_000
            total_avail_cif = DEC_0
            total_plan_qty = DEC_000
            total_plan_cif = DEC_0
            total_used_qty = DEC_000
            total_used_cif = DEC_0
            total_uncommitted_qty = DEC_000
            has_any_plan = False
            is_over_planned = False

            for group_key, group_items in groups.items():
                group_plans = []
                group_allotments = []

                for item in group_items:
                    group_plans.extend(plans_by_item_id.get(item.id, []))
                    group_allotments.extend(allotments_by_item_id.get(item.id, []))

                row = LicensePlanPresentationService._compute_group_aggregates(
                    group_key=group_key,
                    group_items=group_items,
                    group_plans=group_plans,
                    group_allotments=group_allotments,
                )
                rows.append(row)

                total_avail_qty += row.total_available_quantity
                total_avail_cif += row.total_available_cif_fc
                total_plan_qty += row.planned_quantity
                total_plan_cif += row.planned_cif_fc
                total_used_qty += row.used_quantity
                total_used_cif += row.used_cif_fc
                total_uncommitted_qty += row.uncommitted_quantity

                if row.has_plan:
                    has_any_plan = True
                if row.is_short:
                    is_over_planned = True

            total_remaining_qty = total_plan_qty - total_used_qty
            total_remaining_cif = total_plan_cif - total_used_cif

            result[license_id] = LicensePlanPresentation(
                license_id=license_obj.id,
                license_number=license_obj.license_number,
                exporter_id=license_obj.exporter_id,
                exporter_name=license_obj.exporter.name if license_obj.exporter else "",
                total_available_quantity=total_avail_qty,
                total_available_cif_fc=total_avail_cif,
                total_planned_quantity=total_plan_qty,
                total_planned_cif_fc=total_plan_cif,
                total_used_quantity=total_used_qty,
                total_used_cif_fc=total_used_cif,
                total_remaining_quantity=total_remaining_qty,
                total_remaining_cif_fc=total_remaining_cif,
                total_uncommitted_quantity=total_uncommitted_qty,
                num_groups=len(rows),
                num_items=len(items),
                has_any_plan=has_any_plan,
                is_over_planned=is_over_planned,
                rows=rows,
            )

        return result

    # ========================================================================
    # Internal Helper Methods (all @staticmethod for purity)
    # ========================================================================

    @staticmethod
    def _fetch_license_data(license_id: int) -> Tuple:
        """
        Fetch license, items, plans, and allotments in one batch-query round-trip.

        Returns:
            (license_obj, items_qs, plans_qs, allotments_qs)
        """
        license_obj = (
            LicenseDetailsModel.objects
            .select_related('exporter')
            .get(id=license_id)
        )

        items_qs = (
            license_obj.import_license.all()
            .select_related('hs_code')
            .prefetch_related('items')
            .order_by('serial_number')
        )

        plans_qs = (
            LicenseItemPlan.objects
            .filter(license_id=license_id)
            .select_related('item_name')
        )

        # Allotments: non-BOE, type='AT' (excluding bill-of-entry allocations)
        allotments_qs = (
            AllotmentItems.objects
            .filter(
                item__license_id=license_id,
                allotment__bill_of_entry__isnull=True,
                allotment__type='AT'
            )
            .select_related('item', 'allotment')
        )

        return license_obj, items_qs, plans_qs, allotments_qs

    @staticmethod
    def _group_items_by_key(items) -> Dict[str, List[LicenseImportItemsModel]]:
        """
        Group import items by plan_group_key (HSN + description + unit).

        Returns:
            Dict[group_key] -> List of items (sorted by serial_number)
        """
        groups: Dict[str, List[LicenseImportItemsModel]] = {}

        for item in items:
            key = plan_group_key(item)
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        # Each group's items are already sorted by serial_number (from items_qs.order_by)
        return groups

    @staticmethod
    def _compute_group_aggregates(
        group_key: str,
        group_items: List[LicenseImportItemsModel],
        group_plans: List[LicenseItemPlan],
        group_allotments: List[AllotmentItems],
    ) -> PlanRow:
        """
        Compute one PlanRow from grouped items, plans, and allotments.

        Args:
            group_key: The plan_group_key string (for debugging)
            group_items: All import items in this group (sorted by serial)
            group_plans: All LicenseItemPlan rows for any item in this group
            group_allotments: All AllotmentItems for any item in this group

        Returns:
            Immutable PlanRow with all aggregates and split lines.
        """
        # Extract identifiers and basic info from first item in group
        # (representative item, lowest serial)
        first_item = group_items[0]
        group_id = first_item.id
        import_item_ids = sorted([item.id for item in group_items])
        serials = sorted([item.serial_number for item in group_items])
        description = first_item.description or ""
        hs_code = first_item.hs_code.hs_code if first_item.hs_code else None

        # Aggregate available quantities
        total_avail_qty = sum(
            (to_decimal(item.quantity, DEC_000) for item in group_items), DEC_000
        )
        total_avail_cif = sum(
            (to_decimal(item.available_value, DEC_0) for item in group_items), DEC_0
        )

        # Aggregate planned quantities (sum of plan lines)
        plan_qty = sum(
            (to_decimal(plan.planned_quantity, DEC_000) for plan in group_plans), DEC_000
        )
        plan_cif = sum(
            (to_decimal(plan.planned_cif_fc, DEC_0) for plan in group_plans), DEC_0
        )
        has_plan = len(group_plans) > 0

        # Aggregate used quantities (allotments)
        used_qty = sum(
            (to_decimal(allotment.qty, DEC_000) for allotment in group_allotments), DEC_000
        )
        used_cif = sum(
            (to_decimal(allotment.cif_fc, DEC_0) for allotment in group_allotments), DEC_0
        )

        # Derived quantities
        remaining_qty = plan_qty - used_qty
        remaining_cif = plan_cif - used_cif
        uncommitted_qty = total_avail_qty - plan_qty

        # Semantics flags
        is_feasible = used_qty <= plan_qty if has_plan else True
        is_short = used_qty > plan_qty if has_plan else False

        # Split lines (one per LicenseItemPlan in group)
        split_lines = []
        for plan in group_plans:
            remaining_plan_qty = to_decimal(plan.remaining_quantity, plan.planned_quantity)
            remaining_plan_cif = to_decimal(plan.remaining_cif_fc, plan.planned_cif_fc)

            split_lines.append(
                PlanLinePresentation(
                    plan_line_id=plan.id,
                    item_name=plan.item_name.name if plan.item_name else None,
                    planned_quantity=to_decimal(plan.planned_quantity, DEC_000),
                    remaining_quantity=remaining_plan_qty,
                    planned_cif_fc=to_decimal(plan.planned_cif_fc, DEC_0),
                    remaining_cif_fc=remaining_plan_cif,
                )
            )

        return PlanRow(
            group_id=group_id,
            import_item_ids=import_item_ids,
            serials=serials,
            description=description,
            hs_code=hs_code,
            total_available_quantity=total_avail_qty,
            total_available_cif_fc=total_avail_cif,
            has_plan=has_plan,
            planned_quantity=plan_qty,
            planned_cif_fc=plan_cif,
            used_quantity=used_qty,
            used_cif_fc=used_cif,
            remaining_quantity=remaining_qty,
            remaining_cif_fc=remaining_cif,
            uncommitted_quantity=uncommitted_qty,
            split_lines=split_lines,
            is_feasible=is_feasible,
            is_short=is_short,
        )
