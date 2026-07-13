"""
Signal receiver tests for apps.license.signals.

These tests verify that the 4 cross-app signal handlers (allotment, BOE, trade,
company-delete) are correctly wired to their model senders and fire the
expected update/archive logic when those models change.

Patch target: ``apps.license.signals.update_license_flags``
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import RowDetails, BillOfEntryModel
from apps.trade.models import LicenseTrade, LicenseTradeLine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_license(suffix="SIGT01"):
    """Create a minimal LicenseDetailsModel. All nullable FKs omitted."""
    return LicenseDetailsModel.objects.create(
        license_number=f"TEST-{suffix}",
    )


def _make_import_item(license_obj):
    """Create a minimal LicenseImportItemsModel linked to *license_obj*."""
    # serial_number must be unique per license
    next_serial = (
        LicenseImportItemsModel.objects.filter(license=license_obj)
        .order_by("-serial_number")
        .values_list("serial_number", flat=True)
        .first()
        or 0
    ) + 1
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=next_serial,
    )


# ---------------------------------------------------------------------------
# 1. AllotmentItems — post_save / post_delete
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAllotmentItemSignal(TestCase):
    """update_license_on_allotment_item_change fires on AllotmentItems saves/deletes."""

    def _make_allotment(self, company):
        return AllotmentModel.objects.create(
            company=company,
            item_name="Test Commodity",
        )

    def test_post_save_calls_update_license_flags(self):
        company = CompanyModel.objects.create(name="Test Co A")
        license_obj = _make_license("AIT01")
        import_item = _make_import_item(license_obj)
        allotment = self._make_allotment(company)

        with patch("apps.license.signals.update_license_flags") as mock_update:
            AllotmentItems.objects.create(
                item=import_item,
                allotment=allotment,
                cif_inr=Decimal("1000.00"),
                cif_fc=Decimal("12.00"),
                qty=Decimal("100.000"),
            )
            # The signal handler checks instance.item and instance.item.license
            # and calls update_license_flags with the license.
            mock_update.assert_called_once_with(license_obj)

    def test_post_delete_calls_update_license_flags(self):
        company = CompanyModel.objects.create(name="Test Co B")
        license_obj = _make_license("AIT02")
        import_item = _make_import_item(license_obj)
        allotment = self._make_allotment(company)

        ai = AllotmentItems.objects.create(
            item=import_item,
            allotment=allotment,
            cif_inr=Decimal("500.00"),
            cif_fc=Decimal("6.00"),
            qty=Decimal("50.000"),
        )

        with patch("apps.license.signals.update_license_flags") as mock_update:
            ai.delete()
            mock_update.assert_called_once_with(license_obj)


# ---------------------------------------------------------------------------
# 2. RowDetails (BOE) — post_save / post_delete
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRowDetailsSignal(TestCase):
    """update_license_on_boe_item_change fires on RowDetails saves/deletes."""

    def test_post_save_calls_update_license_flags(self):
        license_obj = _make_license("BOE01")
        import_item = _make_import_item(license_obj)
        boe = BillOfEntryModel.objects.create()

        with patch("apps.license.signals.update_license_flags") as mock_update:
            RowDetails.objects.create(
                bill_of_entry=boe,
                sr_number=import_item,
                cif_inr=Decimal("0.000"),
                cif_fc=Decimal("0.000"),
                qty=Decimal("0.000"),
            )
            mock_update.assert_called_once_with(license_obj)

    def test_post_delete_calls_update_license_flags(self):
        license_obj = _make_license("BOE02")
        import_item = _make_import_item(license_obj)
        boe = BillOfEntryModel.objects.create()

        row = RowDetails.objects.create(
            bill_of_entry=boe,
            sr_number=import_item,
            cif_inr=Decimal("0.000"),
            cif_fc=Decimal("0.000"),
            qty=Decimal("0.000"),
        )

        with patch("apps.license.signals.update_license_flags") as mock_update:
            row.delete()
            mock_update.assert_called_once_with(license_obj)


# ---------------------------------------------------------------------------
# 3. LicenseTradeLine — post_save / post_delete
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLicenseTradeLineSignal(TestCase):
    """update_license_on_trade_line_change fires on LicenseTradeLine saves/deletes."""

    def _make_trade(self):
        return LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            license_type=LicenseTrade.LICENSE_TYPE_DFIA,
        )

    def test_post_save_calls_update_license_flags(self):
        license_obj = _make_license("TRD01")
        import_item = _make_import_item(license_obj)
        trade = self._make_trade()

        with patch("apps.license.signals.update_license_flags") as mock_update:
            LicenseTradeLine.objects.create(
                trade=trade,
                sr_number=import_item,
                mode=LicenseTradeLine.MODE_CIF_INR,
            )
            mock_update.assert_called_once_with(license_obj)

    def test_post_delete_calls_update_license_flags(self):
        license_obj = _make_license("TRD02")
        import_item = _make_import_item(license_obj)
        trade = self._make_trade()

        line = LicenseTradeLine.objects.create(
            trade=trade,
            sr_number=import_item,
            mode=LicenseTradeLine.MODE_CIF_INR,
        )

        with patch("apps.license.signals.update_license_flags") as mock_update:
            line.delete()
            mock_update.assert_called_once_with(license_obj)


# ---------------------------------------------------------------------------
# 4. CompanyModel pre_delete — archived_exporter_name snapshot
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSnapshotExporterNameSignal(TestCase):
    """snapshot_exporter_name_on_company_delete preserves the company name
    on all linked licenses before the CompanyModel row is deleted."""

    def test_archived_exporter_name_is_set_before_delete(self):
        company = CompanyModel.objects.create(name="Acme Exporters Ltd")
        license_obj = _make_license("EXP01")
        # Link company as exporter
        license_obj.exporter = company
        license_obj.save(update_fields=["exporter"])

        # Pre-condition: snapshot field is empty
        license_obj.refresh_from_db()
        assert license_obj.archived_exporter_name == ""

        # Delete triggers pre_delete signal
        company.delete()

        license_obj.refresh_from_db()
        assert license_obj.archived_exporter_name == "Acme Exporters Ltd"

    def test_archived_exporter_name_uses_empty_string_when_name_is_blank(self):
        company = CompanyModel.objects.create(name="")
        license_obj = _make_license("EXP02")
        license_obj.exporter = company
        license_obj.save(update_fields=["exporter"])

        company.delete()

        license_obj.refresh_from_db()
        # Signal does: archived_exporter_name = instance.name or ""
        assert license_obj.archived_exporter_name == ""
