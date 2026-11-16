"""Over-utilised licences: licence-level CIF balance is signed (no floor at 0).

Approved BUSINESS-RULE CHANGE 2026-11-16: engines return negatives and expose
`is_over_utilised`; cap/availability/planning consumers still see 0.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, PropertyMock, patch

import pytest

from apps.core.constants import DEC_0
from apps.core.filtersets import LicenseFilterSet
from apps.license.models import LicenseDetailsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.plan_utilization import plan_utilization_rows
from apps.license.services.validation_service import LicenseValidationService

NEG = Decimal("-400.00")


def _patch_licence_level(credit="100", debit="300", allot="200", hidden="0"):
    return (
        patch.object(LBC, "calculate_credit", return_value=Decimal(credit)),
        patch.object(LBC, "calculate_boe_debit_total", return_value=Decimal(debit)),
        patch.object(LBC, "calculate_hidden_boe_debit_total", return_value=Decimal(hidden)),
        patch.object(LBC, "calculate_allotment", return_value=Decimal(allot)),
    )


def test_single_licence_engines_return_signed_value():
    p = _patch_licence_level()
    with p[0], p[1], p[2], p[3]:
        assert LBC.calculate_balance(Mock()) == NEG
        assert LBC.calculate_customs_balance(Mock()) == NEG
        assert LBC.calculate_all_components(Mock())["balance"] == NEG


def test_financial_balance_single_is_signed():
    with patch.object(LBC, "calculate_opening_balance", return_value=Decimal("100")), \
         patch.object(LBC, "calculate_purchase_credit", return_value=DEC_0), \
         patch.object(LBC, "calculate_trade", return_value=DEC_0), \
         patch.object(LBC, "calculate_debit", return_value=Decimal("300")), \
         patch.object(LBC, "calculate_allotment", return_value=Decimal("200")):
        assert LBC._calculate_financial_balance(Mock()) == NEG


def test_bulk_engines_return_signed_value():
    with patch.object(LBC, "calculate_credit_for_licenses", return_value={1: Decimal("100")}), \
         patch.object(LBC, "calculate_boe_debit_total_for_licenses", return_value={1: Decimal("300")}), \
         patch.object(LBC, "calculate_hidden_boe_debit_total_for_licenses", return_value={1: DEC_0}), \
         patch.object(LBC, "calculate_allotment_for_licenses", return_value={1: Decimal("200")}):
        assert LBC.calculate_balance_for_licenses([1]) == {1: NEG}
        assert LBC.calculate_customs_balance_for_licenses([1]) == {1: NEG}


def test_financial_balance_bulk_is_signed():
    with patch.object(LBC, "calculate_credit_for_licenses", return_value={1: Decimal("100")}), \
         patch.object(LBC, "calculate_purchase_credit_for_licenses", return_value={1: DEC_0}), \
         patch.object(LBC, "calculate_opening_balance_for_licenses", return_value={1: Decimal("100")}), \
         patch.object(LBC, "calculate_trade_for_licenses", return_value={1: DEC_0}), \
         patch.object(LBC, "calculate_boe_debit_total_for_licenses", return_value={1: Decimal("300")}), \
         patch.object(LBC, "calculate_debit_for_licenses", return_value={1: Decimal("300")}, create=True), \
         patch.object(LBC, "calculate_allotment_for_licenses", return_value={1: Decimal("200")}):
        assert LBC.calculate_financial_balance_for_licenses([1]) == {1: NEG}


def test_helpers():
    assert LBC.is_over_utilised(Decimal("-0.01")) is True
    assert LBC.is_over_utilised(DEC_0) is False
    assert LBC.is_over_utilised(Decimal("5")) is False
    assert LBC.available_for_allocation(NEG) == DEC_0
    assert LBC.available_for_allocation(Decimal("7.50")) == Decimal("7.50")


def test_cap_consumer_sees_zero_availability_for_negative_licence():
    """validate_sufficient_balance: a negative licence behaves exactly like 0."""
    lic = Mock()
    lic.get_balance_cif = NEG
    ok, _ = LicenseValidationService.validate_sufficient_balance(lic, Decimal("0"))
    assert ok is True  # identical to a 0-balance licence requesting 0
    ok, msg = LicenseValidationService.validate_sufficient_balance(lic, Decimal("1"))
    assert ok is False
    assert "Available: 0" in msg  # clamped, not -400


def test_filterset_exhausted_option_includes_negative_licences():
    qs = Mock()
    fs = LicenseFilterSet.__new__(LicenseFilterSet)
    fs.filter_has_balance(qs, "has_balance", False)
    qs.filter.assert_called_once_with(balance__balance_cif__lte=0)
    qs2 = Mock()
    fs.filter_has_balance(qs2, "has_balance", True)
    qs2.filter.assert_called_once_with(balance__balance_cif__gt=0)


@pytest.mark.django_db
def test_plan_utilization_treats_negative_balance_as_exhausted():
    from apps.core.models import CompanyModel, PortModel
    from apps.license.models import LicenseImportItemsModel
    company = CompanyModel.objects.create(iec="5234567890", name="NegBal Exporter")
    port = PortModel.objects.create(code="INNEG1", name="NegBal Port")
    lic = LicenseDetailsModel.objects.create(
        license_number="NEG-BAL-001", license_date=date.today(),
        license_expiry_date=date.today(), exporter=company, port=port,
    )
    LicenseImportItemsModel.objects.create(
        license=lic, serial_number=1, description="Item",
        quantity=Decimal("10.000"), available_quantity=Decimal("10.000"),
        available_value=Decimal("100.00"),
    )
    with patch.object(LicenseDetailsModel, "get_balance_cif", new_callable=PropertyMock, return_value=NEG):
        rows = plan_utilization_rows(lic)
    assert rows
    row = rows[0]
    assert row["license_balance_cif"] == NEG  # raw signed value stays visible
    assert row["effective_license_balance_cif"] == DEC_0
    assert row["planner_cif_exhausted"] is True
    assert row["balance_cif_ignored_by_tolerance"] is False


@pytest.mark.django_db
def test_serializer_exposes_signed_balance_and_flag():
    from apps.core.models import CompanyModel, PortModel
    from apps.license.serializers.license import LicenseDetailsSerializer
    company = CompanyModel.objects.create(iec="6234567890", name="NegBal Exporter 2")
    port = PortModel.objects.create(code="INNEG2", name="NegBal Port 2")
    lic = LicenseDetailsModel.objects.create(
        license_number="NEG-BAL-002", license_date=date.today(),
        license_expiry_date=date.today(), exporter=company, port=port,
    )
    with patch.object(LicenseDetailsModel, "get_balance_cif", new_callable=PropertyMock, return_value=NEG):
        data = LicenseDetailsSerializer(lic).data
    assert Decimal(str(data["balance_cif"])) == NEG
    assert data["is_over_utilised"] is True
    with patch.object(LicenseDetailsModel, "get_balance_cif", new_callable=PropertyMock, return_value=Decimal("50")):
        data = LicenseDetailsSerializer(lic).data
    assert data["is_over_utilised"] is False
