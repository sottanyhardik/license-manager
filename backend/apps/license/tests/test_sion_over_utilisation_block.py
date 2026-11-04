"""
Over-utilised licences are blocked explicitly by SION planning.

Before: a negative reconciled budget was clamped to zero, so an over-utilised
licence looked like one with nothing left, with no reason recorded.
Now: the licence is reported as BLOCKED_OVER_UTILISED with the excess amount, and
no planning line is generated or written for it.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import CompanyModel, HeadSIONNormsModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
    SionPlanningRule,
)
from apps.license.services.sion_rule_engine import SionRulePlanningService

pytestmark = pytest.mark.django_db


def _world(export_cif, usage_cif):
    company = CompanyModel.objects.create(iec="OVERUTIL01", name="Over Utilised Co")
    head = HeadSIONNormsModel.objects.create(name="Over Util Head")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="E1", is_active=True)
    licence = LicenseDetailsModel.objects.create(
        license_number="OVER-UTIL-LIC",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    LicenseExportItemModel.objects.create(
        license=licence, description="Export E1", norm_class=sion, cif_fc=Decimal(export_cif),
    )
    from apps.core.models import HSCodeModel
    hs = HSCodeModel.objects.create(hs_code="15079010", product_description="Crude soya oil", unit_price=Decimal("1.00"), unit="kg")
    item = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=1, description="Vegetable oil", hs_code=hs,
        quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
        available_value=Decimal("100.00"), condition_type="",
    )
    SionPlanningRule.objects.create(
        sion=sion, name="Oil", unit="kg", max_unit_price=Decimal("5.00"), priority=1, is_active=True,
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "1507"},
    )
    # Historical usage that the reconciliation counts as already debited.
    usage_allotment = AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000.00"))
    AllotmentItems.objects.create(
        allotment=usage_allotment, item=item, qty=Decimal("10.000"), cif_fc=Decimal(usage_cif),
    )
    return company, sion, licence


def test_over_utilised_licence_is_blocked_with_explicit_excess_and_no_lines():
    _company, sion, licence = _world(export_cif="1000.00", usage_cif="1200.00")

    result = SionRulePlanningService.preview_sion(sion.pk, [licence.pk], mode="ALL")

    assert result["over_utilised_count"] == 1, result
    blocked = [row for row in result["excluded_licenses"] if row["license_id"] == licence.pk]
    assert blocked, result
    assert blocked[0]["reason"] == "BLOCKED_OVER_UTILISED"
    assert Decimal(blocked[0]["over_utilised_cif"]) == Decimal("200.00")
    assert result["planned_licenses"] == 0
    assert LicenseItemPlan.objects.filter(license=licence).count() == 0


def test_licence_within_its_cif_is_not_blocked():
    _company, sion, licence = _world(export_cif="1000.00", usage_cif="100.00")

    result = SionRulePlanningService.preview_sion(sion.pk, [licence.pk], mode="ALL")

    # Control: a licence that still has CIF must never be reported as blocked.
    assert result["over_utilised_count"] == 0, result
    assert not [row for row in result["excluded_licenses"] if row["reason"] == "BLOCKED_OVER_UTILISED"]


