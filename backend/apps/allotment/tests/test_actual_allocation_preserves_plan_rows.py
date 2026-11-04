"""
Regression: an ACTUAL allocation must never fold into an existing PLAN ledger row.

Defect (views_actions.py allocate_items, ACTUAL branch): the existing-row lookup
filtered only ``plan_line__isnull=True``.  PLAN rows are also written with a NULL
``plan_line`` (the legacy FK is never populated), so an ACTUAL debit on the same
item and allotment matched the PLAN row, rewrote its ``allocation_basis`` to
ACTUAL and cleared its target.  The plan's debit disappeared, so the same plan
capacity could be spent a second time.
"""
from decimal import Decimal

import pytest

from apps.allotment.models import AllotmentItems
from apps.license.services.plan_enforcement import plan_line_status_for
from apps.allotment.tests.test_allocate_items_plan_line_balance import (  # noqa: F401  (fixtures)
    _allocate,
    allotment_client,
    allotment_obj,
    veg_oil_split,
)


@pytest.mark.django_db
class TestActualAllocationPreservesPlanRows:
    def test_actual_debit_on_same_item_does_not_convert_plan_row(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        item = veg_oil_split["import_item"]
        pko = veg_oil_split["pko_line"]

        plan_response = _allocate(
            allotment_client, allotment_obj, item.pk, Decimal("40"), Decimal("72.00"),
            plan_line_id=pko.pk,
        )
        assert plan_response.status_code in (200, 201), plan_response.data

        actual_response = _allocate(
            allotment_client, allotment_obj, item.pk, Decimal("10"), Decimal("18.00"),
        )
        assert actual_response.status_code in (200, 201), actual_response.data

        plan_rows = AllotmentItems.objects.filter(
            allotment=allotment_obj, item=item, allocation_basis="PLAN",
        )
        actual_rows = AllotmentItems.objects.filter(
            allotment=allotment_obj, item=item, allocation_basis="ACTUAL",
        )

        # The PLAN debit must survive untouched: same quantity, still tied to PKO.
        assert plan_rows.count() == 1
        plan_row = plan_rows.get()
        assert plan_row.qty == Decimal("40.000")
        assert plan_row.planning_target_item_id == pko.item_name_id

        # The ACTUAL debit is its own identity with no plan target.
        assert actual_rows.count() == 1
        actual_row = actual_rows.get()
        assert actual_row.qty == Decimal("10.000")
        assert actual_row.planning_target_item_id is None

        # Plan capacity stays fully consumed by the PLAN debit.
        assert plan_line_status_for(pko)["remaining_quantity"] == Decimal("0")

    def test_second_plan_debit_is_still_capped_after_actual_debit(
        self, allotment_client, allotment_obj, veg_oil_split,
    ):
        item = veg_oil_split["import_item"]
        pko = veg_oil_split["pko_line"]

        assert _allocate(
            allotment_client, allotment_obj, item.pk, Decimal("40"), Decimal("72.00"),
            plan_line_id=pko.pk,
        ).status_code in (200, 201)
        assert _allocate(
            allotment_client, allotment_obj, item.pk, Decimal("10"), Decimal("18.00"),
        ).status_code in (200, 201)

        # Before the fix this PLAN request succeeded, because the ACTUAL debit
        # had released the 40 kg PKO capacity by rewriting the PLAN row.
        second_plan = _allocate(
            allotment_client, allotment_obj, item.pk, Decimal("1"), Decimal("1.80"),
            plan_line_id=pko.pk,
        )
        assert second_plan.status_code >= 400, second_plan.data
        assert AllotmentItems.objects.filter(
            allotment=allotment_obj, item=item, allocation_basis="PLAN",
        ).get().qty == Decimal("40.000")
