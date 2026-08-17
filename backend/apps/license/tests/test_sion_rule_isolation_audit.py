from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    LicenseItemPlan, SionPlanningRule,
)
from apps.license.services.sion_rule_engine import (
    SionRulePlanningService, SionRulePriorityService,
)

pytestmark = pytest.mark.django_db


def _license(company, sion, number, hsn):
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company, license_number=number, license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=sion, cif_fc=Decimal("100.00"),
    )
    code = HSCodeModel.objects.create(
        hs_code=hsn, product_description="Audit item",
        unit_price=Decimal("1.00"), unit="kg",
    )
    LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=code,
        description="Audit item", unit="kg", quantity=Decimal("5.000"),
        available_quantity=Decimal("5.000"),
    )
    return license_obj


@pytest.fixture
def isolated_norms():
    head = HeadSIONNormsModel.objects.create(name="Isolation audit")
    e1 = SionNormClassModel.objects.create(head_norm=head, norm_class="QA-E1", is_active=True)
    e5 = SionNormClassModel.objects.create(head_norm=head, norm_class="QA-E5", is_active=True)
    company = CompanyModel.objects.create(iec="9300000001", name="Isolation Company")
    e1_license = _license(company, e1, "QA-E1-LIC", "01010101")
    e5_license = _license(company, e5, "QA-E5-LIC", "05050505")
    expression = {"field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "audit"}
    e1_rule = SionPlanningRule.objects.create(
        sion=e1, name="E1 only", expression=expression, max_unit_price=Decimal("2.00"),
        unit="kg", priority=1,
    )
    e5_rule = SionPlanningRule.objects.create(
        sion=e5, name="E5 only", expression=expression, max_unit_price=Decimal("2.00"),
        unit="kg", priority=1,
    )
    return company, e1, e5, e1_license, e5_license, e1_rule, e5_rule


def test_e1_preview_never_executes_e5_rules_or_licenses(isolated_norms):
    company, e1, _e5, e1_license, _e5_license, e1_rule, _e5_rule = isolated_norms
    before = LicenseItemPlan.objects.count()
    result = SionRulePlanningService.preview_sion(e1.pk, None, company_id=company.pk)
    assert result["rules_processed"] == [{
        "id": e1_rule.pk, "version": e1_rule.version, "priority": 1,
    }]
    assert [row["license_id"] for row in result["licenses"]] == [e1_license.pk]
    assert LicenseItemPlan.objects.count() == before


def test_reordering_e1_cannot_change_e5_priority(isolated_norms):
    _company, e1, _e5, _e1_license, _e5_license, first, e5_rule = isolated_norms
    second = SionPlanningRule.objects.create(
        sion=e1, name="E1 second",
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "01"},
        max_unit_price=Decimal("2.00"), unit="kg", priority=2,
    )
    SionRulePriorityService.reorder(e1.pk, [second.pk, first.pk])
    e5_rule.refresh_from_db()
    assert e5_rule.priority == 1
    assert list(SionPlanningRule.objects.filter(
        sion=e1, is_active=True,
    ).order_by("priority").values_list("pk", flat=True)) == [second.pk, first.pk]
