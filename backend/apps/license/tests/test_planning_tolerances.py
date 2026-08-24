from decimal import Decimal
from datetime import date, timedelta

import pytest

from apps.core.models import CompanyModel, HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseFlags
from apps.license.services.sion_planning_execution import (
    PlannerConfigurationError, SionPlanningExecutionService,
)

from apps.license.services.planning_tolerances import (
    effective_planning_available_quantity,
    effective_planning_balance_cif,
)


@pytest.mark.parametrize(("raw", "expected"), [
    ("3.89", "0.00"),
    ("199.999", "0.000"),
    ("200.000", "200.000"),
    ("200.001", "200.001"),
    ("0", "0.000"),
    ("-0.001", "-0.001"),
])
def test_effective_available_quantity_boundaries(raw, expected):
    assert effective_planning_available_quantity(Decimal(raw)) == Decimal(expected)


@pytest.mark.parametrize(("raw", "expected"), [
    ("499.99", "0.00"),
    ("500.00", "500.00"),
    ("500.01", "500.01"),
    ("0", "0.00"),
    ("-0.01", "-0.01"),
])
def test_effective_balance_cif_boundaries(raw, expected):
    assert effective_planning_balance_cif(Decimal(raw)) == Decimal(expected)


@pytest.mark.parametrize(("qty", "cif", "effective_qty", "effective_cif"), [
    ("150", "5000", "0", "5000"),
    ("900", "450", "900", "0"),
    ("150", "450", "0", "0"),
])
def test_tolerances_are_independent(qty, cif, effective_qty, effective_cif):
    assert effective_planning_available_quantity(Decimal(qty)) == Decimal(effective_qty)
    assert effective_planning_balance_cif(Decimal(cif)) == Decimal(effective_cif)


@pytest.mark.django_db
def test_positive_sub_500_balance_remains_eligible_and_is_capped_without_mutation(monkeypatch):
    head = HeadSIONNormsModel.objects.create(name="Tolerance")
    sion = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E126T", is_active=True,
    )
    company = CompanyModel.objects.create(iec="TOLERANCE1", name="Tolerance Co")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company,
        license_number="BALANCE-TOLERANCE-3-89",
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=sion, cif_fc=Decimal("502912.57"),
    )

    monkeypatch.setattr(
        "apps.license.services.balance_calculator."
        "LicenseBalanceCalculator.calculate_financial_balance_for_licenses",
        lambda _ids: {license_obj.pk: Decimal("3.89")},
    )

    licenses, raw_balances = SionPlanningExecutionService._eligible_licenses(
        sion, [license_obj.pk], force_plan=False,
    )

    # Actual Balance CIF is the absolute cap; a positive live balance must
    # remain eligible rather than being silently discarded by a legacy
    # operational tolerance.
    assert [row.pk for row in licenses] == [license_obj.pk]
    assert raw_balances[license_obj.pk] == Decimal("3.89")
    license_obj.refresh_from_db()
    assert license_obj.export_license.get().cif_fc == Decimal("502912.57")


@pytest.mark.django_db
def test_expired_license_816_is_sion_planning_eligible_without_status_mutation(monkeypatch):
    """Expiry must not block Auto Plan, manual replan, preview, or worker execution.

    All those paths ultimately use ``_eligible_licenses``.  This production
    shaped regression uses the reported licence identifier while retaining
    the normal live-CIF cap returned to the planner.
    """
    head = HeadSIONNormsModel.objects.create(name="Expired planning")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="E1-816", is_active=True)
    company = CompanyModel.objects.create(iec="EXPIRED816", name="Expired Planning Co")
    license_obj = LicenseDetailsModel.objects.create(
        id=816,
        exporter=company,
        license_number="816",
        license_date=date.today() - timedelta(days=90),
        license_expiry_date=date.today() - timedelta(days=1),
    )
    LicenseFlags.objects.filter(license=license_obj).update(is_active=False, is_expired=True)
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=sion, cif_fc=Decimal("1000.00"),
    )
    monkeypatch.setattr(
        "apps.license.services.balance_calculator."
        "LicenseBalanceCalculator.calculate_financial_balance_for_licenses",
        lambda _ids: {license_obj.pk: Decimal("1000.00")},
    )

    licenses, live_balances = SionPlanningExecutionService._eligible_licenses(sion, [816])

    assert [row.pk for row in licenses] == [816]
    assert live_balances[816] == Decimal("1000.00")
    license_obj.refresh_from_db()
    license_obj.flags.refresh_from_db()
    assert license_obj.license_expiry_date < date.today()
    assert license_obj.flags.is_expired is True
    assert license_obj.flags.is_active is False


@pytest.mark.django_db
def test_inactive_non_expired_license_remains_ineligible_for_sion_planning():
    """The expiry exception must not broaden planning to other inactive licences."""
    head = HeadSIONNormsModel.objects.create(name="Inactive planning")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="E1-INACT", is_active=True)
    company = CompanyModel.objects.create(iec="INACTIVE01", name="Inactive Planning Co")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company,
        license_number="INACTIVE-NOT-EXPIRED",
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseFlags.objects.filter(license=license_obj).update(is_active=False, is_expired=False)
    LicenseExportItemModel.objects.create(license=license_obj, norm_class=sion, cif_fc=Decimal("1000.00"))

    with pytest.raises(PlannerConfigurationError, match="unavailable for this SION"):
        SionPlanningExecutionService._eligible_licenses(sion, [license_obj.pk])
