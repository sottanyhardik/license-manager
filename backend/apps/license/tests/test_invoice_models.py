from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.core.models import InvoiceEntity
from apps.license.models import Invoice, InvoiceItem, LicenseDetailsModel, LicenseImportItemsModel


@pytest.fixture
def invoice_entity(db):
    return InvoiceEntity.objects.create(
        name="Exporter Pvt Ltd",
        address_line_1="Line 1",
        pan_number="AAPFU0939F",
        gst_number="27AAPFU0939F1ZV",
        bank_account_number="1234567890",
        bank_name="Example Bank",
        ifsc_code="ABCD0123456",
        account_type="current",
    )


@pytest.fixture
def invoice(invoice_entity):
    return Invoice.objects.create(
        from_entity=invoice_entity,
        to_company_name=" Buyer Ltd ",
        to_company_pan=" aapfu0939f ",
        to_company_gst_number=" 27aapfu0939f1zv ",
        to_company_address_line_1=" Address ",
        invoice_number=" INV-001 ",
        billing_mode="kg",
    )


@pytest.fixture
def import_item(db):
    license_obj = LicenseDetailsModel.objects.create(license_number="INV-LIC-001")
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        quantity=Decimal("10.000"),
        cif_fc=Decimal("100.00"),
        cif_inr=Decimal("8300.00"),
    )


@pytest.mark.django_db
def test_invoice_save_normalizes_optional_tax_fields_and_required_text(invoice):
    invoice.refresh_from_db()

    assert invoice.to_company_name == "Buyer Ltd"
    assert invoice.to_company_pan == "AAPFU0939F"
    assert invoice.to_company_gst_number == "27AAPFU0939F1ZV"
    assert invoice.to_company_address_line_1 == "Address"
    assert invoice.invoice_number == "INV-001"
    assert str(invoice) == "INV-001"


@pytest.mark.django_db
def test_invoice_accepts_unicode_and_zero_boundary_values(invoice_entity):
    invoice = Invoice.objects.create(
        from_entity=invoice_entity,
        to_company_name=" Käufer 🚀 Pvt Ltd ",
        to_company_pan=None,
        to_company_gst_number="",
        to_company_address_line_1="  Straße 1  ",
        invoice_number=" INV-UNICODE ",
        billing_mode="kg",
        total_qty=Decimal("0.000"),
        total_amount=Decimal("0.00"),
    )

    assert invoice.to_company_name == "Käufer 🚀 Pvt Ltd"
    assert invoice.to_company_gst_number is None
    assert invoice.to_company_address_line_1 == "Straße 1"
    assert invoice.total_qty == Decimal("0.000")
    assert invoice.total_amount == Decimal("0.00")


@pytest.mark.django_db
def test_invoice_partial_update_normalizes_updated_tax_field(invoice):
    invoice.to_company_pan = " aapfu0939f "
    invoice.save(update_fields=["to_company_pan"])
    invoice.refresh_from_db()

    assert invoice.to_company_pan == "AAPFU0939F"


@pytest.mark.django_db
def test_invoice_empty_update_fields_preserves_django_noop_save(invoice):
    invoice.to_company_name = " Unsaved Change "
    invoice.save(update_fields=[])
    invoice.refresh_from_db()

    assert invoice.to_company_name == "Buyer Ltd"


@pytest.mark.django_db
def test_invoice_rejects_blank_required_text_after_stripping(invoice_entity):
    invoice = Invoice(
        from_entity=invoice_entity,
        to_company_name="   ",
        to_company_address_line_1="   ",
        invoice_number="   ",
        billing_mode="kg",
    )

    with pytest.raises(ValidationError) as exc:
        invoice.full_clean()

    assert "to_company_name" in exc.value.message_dict
    assert "to_company_address_line_1" in exc.value.message_dict
    assert "invoice_number" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_rejects_none_required_text_without_type_error(invoice_entity):
    invoice = Invoice(
        from_entity=invoice_entity,
        to_company_name=None,
        to_company_address_line_1=None,
        invoice_number=None,
        billing_mode="kg",
    )

    with pytest.raises(ValidationError) as exc:
        invoice.full_clean()

    assert "to_company_name" in exc.value.message_dict
    assert "to_company_address_line_1" in exc.value.message_dict
    assert "invoice_number" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_rejects_invalid_pan_and_gst(invoice_entity):
    invoice = Invoice(
        from_entity=invoice_entity,
        to_company_name="Buyer Ltd",
        to_company_pan="BAD",
        to_company_gst_number="27BADGST0000000",
        to_company_address_line_1="Address",
        invoice_number="INV-BAD",
        billing_mode="kg",
    )

    with pytest.raises(ValidationError) as exc:
        invoice.full_clean()

    assert "to_company_pan" in exc.value.message_dict
    assert "to_company_gst_number" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_rejects_duplicate_invoice_number_after_normalization(invoice, invoice_entity):
    duplicate = Invoice(
        from_entity=invoice_entity,
        to_company_name="Buyer Ltd",
        to_company_address_line_1="Address",
        invoice_number=" INV-001 ",
        billing_mode="kg",
    )

    with pytest.raises(ValidationError) as exc:
        duplicate.full_clean()

    assert "invoice_number" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_rejects_missing_foreign_key(invoice_entity):
    invoice = Invoice(
        to_company_name="Buyer Ltd",
        to_company_address_line_1="Address",
        invoice_number="INV-MISSING-FK",
        billing_mode="kg",
    )

    with pytest.raises(ValidationError) as exc:
        invoice.full_clean()

    assert "from_entity" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_rejects_negative_totals(invoice_entity):
    invoice = Invoice(
        from_entity=invoice_entity,
        to_company_name="Buyer Ltd",
        to_company_address_line_1="Address",
        invoice_number="INV-NEG",
        billing_mode="kg",
        total_amount=Decimal("-0.01"),
    )

    with pytest.raises(ValidationError) as exc:
        invoice.full_clean()

    assert "total_amount" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_rejects_decimal_overflow(invoice_entity):
    invoice = Invoice(
        from_entity=invoice_entity,
        to_company_name="Buyer Ltd",
        to_company_address_line_1="Address",
        invoice_number="INV-OVERFLOW",
        billing_mode="kg",
        total_amount=Decimal("10000000000000.00"),
    )

    with pytest.raises(ValidationError) as exc:
        invoice.full_clean()

    assert "total_amount" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_database_constraint_rejects_bulk_negative_total(invoice_entity):
    with pytest.raises(IntegrityError):
        Invoice.objects.bulk_create(
            [
                Invoice(
                    from_entity=invoice_entity,
                    to_company_name="Buyer Ltd",
                    to_company_address_line_1="Address",
                    invoice_number="INV-BULK-NEG",
                    billing_mode="kg",
                    total_amount=Decimal("-0.01"),
                )
            ]
        )


@pytest.mark.django_db
def test_invoice_item_save_populates_license_number(invoice, import_item):
    item = InvoiceItem.objects.create(
        invoice=invoice,
        sr_number=import_item,
        license_no="",
        rate=Decimal("12.50"),
        amount=Decimal("125.00"),
    )

    assert item.license_no == "INV-LIC-001"
    assert str(item) == "INV-LIC-001 - 125.00"


@pytest.mark.django_db
def test_invoice_item_partial_update_preserves_cleaned_text(invoice, import_item):
    item = InvoiceItem.objects.create(
        invoice=invoice,
        sr_number=import_item,
        license_no="INV-LIC-001",
        hs_code="490700",
        rate=Decimal("12.50"),
        amount=Decimal("125.00"),
    )

    item.hs_code = "  490799  "
    item.save(update_fields=["hs_code"])
    item.refresh_from_db()

    assert item.hs_code == "490799"


@pytest.mark.django_db
def test_invoice_item_empty_update_fields_preserves_django_noop_save(invoice, import_item):
    item = InvoiceItem.objects.create(
        invoice=invoice,
        sr_number=import_item,
        license_no="INV-LIC-001",
        hs_code="490700",
        rate=Decimal("12.50"),
        amount=Decimal("125.00"),
    )

    item.hs_code = "490799"
    item.save(update_fields=[])
    item.refresh_from_db()

    assert item.hs_code == "490700"


@pytest.mark.django_db
def test_invoice_item_rejects_negative_amount(invoice, import_item):
    item = InvoiceItem(
        invoice=invoice,
        sr_number=import_item,
        license_no="INV-LIC-001",
        rate=Decimal("12.50"),
        amount=Decimal("-0.01"),
    )

    with pytest.raises(ValidationError) as exc:
        item.full_clean()

    assert "amount" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_item_rejects_negative_optional_quantity(invoice, import_item):
    item = InvoiceItem(
        invoice=invoice,
        sr_number=import_item,
        license_no="INV-LIC-001",
        qty=Decimal("-0.001"),
        rate=Decimal("12.50"),
        amount=Decimal("125.00"),
    )

    with pytest.raises(ValidationError) as exc:
        item.full_clean()

    assert "qty" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_item_rejects_blank_license_number_without_source_item(invoice):
    item = InvoiceItem(
        invoice=invoice,
        license_no="   ",
        rate=Decimal("12.50"),
        amount=Decimal("125.00"),
    )

    with pytest.raises(ValidationError) as exc:
        item.full_clean()

    assert "license_no" in exc.value.message_dict
    assert "sr_number" in exc.value.message_dict


@pytest.mark.django_db
def test_invoice_item_rejects_blank_hs_code(invoice, import_item):
    item = InvoiceItem(
        invoice=invoice,
        sr_number=import_item,
        license_no="INV-LIC-001",
        hs_code="   ",
        rate=Decimal("12.50"),
        amount=Decimal("125.00"),
    )

    with pytest.raises(ValidationError) as exc:
        item.full_clean()

    assert "hs_code" in exc.value.message_dict
