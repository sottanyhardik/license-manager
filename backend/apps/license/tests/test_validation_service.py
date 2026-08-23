from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.constants import GE
from apps.core.models import (
    CompanyModel,
    HeadSIONNormsModel,
    NotificationNumber,
    PortModel,
    PurchaseStatus,
    SionNormClassModel,
)
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.validation_service import LicenseValidationService


@pytest.fixture
def company():
    return CompanyModel.objects.create(iec="4234567890", name="Validation Exporter")


@pytest.fixture
def port():
    return PortModel.objects.create(code="INVAL1", name="Validation Port")


@pytest.fixture
def ge_status():
    return PurchaseStatus.objects.create(code=GE, label="GE Purchase")


@pytest.fixture
def notification():
    return NotificationNumber.objects.create(code="N001", label="Notification 001")


@pytest.fixture
def norm_class():
    head = HeadSIONNormsModel.objects.create(name="Validation Norm")
    return SionNormClassModel.objects.create(head_norm=head, norm_class="E1")


@pytest.fixture
def license_obj(company, port, ge_status, notification, norm_class):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="VALIDATION-001",
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=120),
        file_number="FILE-001",
        purchase_status=ge_status,
        notification_number=notification,
        exporter=company,
        port=port,
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Export item",
        norm_class=norm_class,
        cif_fc=Decimal("1000.00"),
    )
    return license_obj


@pytest.fixture
def import_item(license_obj):
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Import item",
        quantity=Decimal("20.000"),
        available_quantity=Decimal("20.000"),
        cif_fc=Decimal("1000.00"),
    )


def test_validation_service_handles_missing_objects():
    assert LicenseValidationService.validate_license_active(None) == (False, "License is required")
    assert LicenseValidationService.validate_license_complete(None) == (False, ["license"])
    assert LicenseValidationService.check_license_expiring_soon(None) is False
    assert LicenseValidationService.validate_sufficient_balance(None, Decimal("1.00")) == (
        False,
        "License is required",
    )
    assert LicenseValidationService.validate_sufficient_quantity(None, Decimal("1.000")) == (
        False,
        "Import item is required",
    )
    assert LicenseValidationService.validate_restriction_limit(None, None, Decimal("1.00")) == (
        False,
        "License is required",
    )
    assert LicenseValidationService.validate_allocation(None, None, Decimal("1.000"), Decimal("1.00")) == (
        False,
        ["License is required", "Import item is required"],
    )
    assert LicenseValidationService.check_individual_license(None) is False
    assert LicenseValidationService.update_license_flags(None) == {
        "is_null": True,
        "is_expired": False,
        "is_active": False,
        "is_incomplete": True,
        "is_individual": False,
    }


@pytest.mark.django_db
def test_validation_service_rejects_negative_requirements(license_obj, import_item):
    assert LicenseValidationService.validate_sufficient_balance(license_obj, Decimal("-0.01")) == (
        False,
        "Required value cannot be negative: -0.01",
    )
    assert LicenseValidationService.validate_sufficient_quantity(import_item, Decimal("-0.001")) == (
        False,
        "Required quantity cannot be negative: -0.001",
    )


@pytest.mark.django_db
def test_validation_service_valid_paths(license_obj, import_item):
    assert LicenseValidationService.validate_license_active(license_obj) == (True, "")
    assert LicenseValidationService.validate_license_complete(license_obj) == (True, [])
    assert LicenseValidationService.validate_sufficient_balance(license_obj, Decimal("100.00")) == (True, "")
    assert LicenseValidationService.validate_sufficient_quantity(import_item, Decimal("5.000")) == (True, "")
    assert LicenseValidationService.validate_restriction_limit(license_obj, import_item, Decimal("100.00")) == (
        True,
        "",
    )
    assert LicenseValidationService.validate_allocation(
        license_obj,
        import_item,
        Decimal("5.000"),
        Decimal("100.00"),
    ) == (True, [])


@pytest.mark.django_db
def test_validation_service_expiry_and_flag_helpers(license_obj):
    assert LicenseValidationService.check_license_expiring_soon(license_obj, days="bad") is False
    assert LicenseValidationService.check_license_expiring_soon(license_obj, days=130) is True

    flags = LicenseValidationService.update_license_flags(license_obj)

    assert flags == {
        "is_null": False,
        "is_expired": False,
        "is_active": True,
        "is_incomplete": False,
        "is_individual": False,
    }
