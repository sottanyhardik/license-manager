"""
Regression: linking a BOE to a PLAN allotment must not release plan capacity.

Defect: plan usage was summed with the licence-balance filter, which excludes
allotments linked to a BOE (their CIF is represented by BOE CIF there).  Linking
the BOE therefore made the plan line look unused again, so the same planned
quantity could be allocated a second time.

Also covered: an overrun is reported as a signed residual with an explicit
over-utilisation flag, not hidden at zero.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.allotment.models import AllotmentItems
from apps.allotment.tests.test_allocate_items_plan_line_balance import (  # noqa: F401  (fixtures)
    _allocate,
    allotment_client,
    allotment_obj,
    veg_oil_split,
)
from apps.bill_of_entry.models import BillOfEntryModel
from apps.core.models import PortModel
from apps.license.services.plan_enforcement import plan_line_status_for, plan_line_status_for_many


def _link_boe(allotment, company, number):
    port = PortModel.objects.create(code=f"PT{number[-4:]}", name=f"Port {number}")
    boe = BillOfEntryModel.objects.create(
        company=company, bill_of_entry_number=number, bill_of_entry_date=date.today(), port=port,
    )
    boe.allotment.add(allotment)
    return boe


@pytest.mark.django_db
class TestPlanCapacitySurvivesBoeLink:
    def test_linking_boe_keeps_planned_quantity_consumed(self, allotment_client, allotment_obj, veg_oil_split):
        item = veg_oil_split["import_item"]
        pko = veg_oil_split["pko_line"]
        assert _allocate(
            allotment_client, allotment_obj, item.pk, Decimal("40"), Decimal("72.00"), plan_line_id=pko.pk,
        ).status_code in (200, 201)
        before = plan_line_status_for(pko)

        _link_boe(allotment_obj, allotment_obj.company, "CAP-BOE-LINK-1")

        after = plan_line_status_for(pko)
        assert before["remaining_quantity"] == Decimal("0")
        assert after["used_quantity"] == Decimal("40.000")
        assert after["remaining_quantity"] == Decimal("0")

    def test_second_plan_allocation_is_rejected_after_boe_link(self, allotment_client, allotment_obj, veg_oil_split):
        item = veg_oil_split["import_item"]
        pko = veg_oil_split["pko_line"]
        assert _allocate(
            allotment_client, allotment_obj, item.pk, Decimal("40"), Decimal("72.00"), plan_line_id=pko.pk,
        ).status_code in (200, 201)
        _link_boe(allotment_obj, allotment_obj.company, "CAP-BOE-LINK-2")

        second = _allocate(
            allotment_client, allotment_obj, item.pk, Decimal("1"), Decimal("1.80"), plan_line_id=pko.pk,
        )

        assert second.status_code >= 400, second.data
        assert AllotmentItems.objects.filter(
            allotment=allotment_obj, item=item, allocation_basis="PLAN",
        ).get().qty == Decimal("40.000")

    def test_overrun_is_reported_as_signed_residual_not_hidden(self, allotment_obj, veg_oil_split):
        item = veg_oil_split["import_item"]
        pko = veg_oil_split["pko_line"]
        AllotmentItems.objects.create(
            allotment=allotment_obj, item=item, qty=Decimal("50.000"), cif_fc=Decimal("90.00"),
            allocation_basis="PLAN", planning_target_item_id=pko.item_name_id,
        )

        status = plan_line_status_for(pko)

        assert status["remaining_quantity"] == Decimal("0")
        assert status["raw_remaining_quantity"] == Decimal("-10.000")
        assert status["over_utilised_quantity"] == Decimal("10.000")
        assert status["over_utilised"] is True
        assert status["raw_remaining_cif_fc"] == Decimal("-18.00")
        assert status["over_utilised_cif_fc"] == Decimal("18.00")

    def test_bulk_and_singleton_plan_status_agree(self, allotment_obj, veg_oil_split):
        item = veg_oil_split["import_item"]
        pko = veg_oil_split["pko_line"]
        cheese = veg_oil_split["cheese_line"]
        AllotmentItems.objects.create(
            allotment=allotment_obj, item=item, qty=Decimal("50.000"), cif_fc=Decimal("90.00"),
            allocation_basis="PLAN", planning_target_item_id=pko.item_name_id,
        )
        _link_boe(allotment_obj, allotment_obj.company, "CAP-BOE-PARITY")

        bulk = plan_line_status_for_many([pko, cheese])

        assert bulk[pko.pk] == plan_line_status_for(pko)
        assert bulk[cheese.pk] == plan_line_status_for(cheese)
