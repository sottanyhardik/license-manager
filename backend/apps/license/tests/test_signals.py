"""
Signal receiver tests for apps.license.signals.

These tests verify that the 4 cross-app signal handlers (allotment, BOE, trade,
company-delete) are correctly wired to their model senders and fire the
expected update/archive logic when those models change.

Patch target: ``apps.license.signals.update_license_flags``
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.utils import timezone

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import RowDetails, BillOfEntryModel
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.signals import (
    _flags_suspended,
    _update_all_import_items_available_value,
    suspend_license_flag_recalc,
    update_license_flags,
    update_license_on_import_item_change,
)
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


# ---------------------------------------------------------------------------
# 5. License signal helper hardening
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLicenseSignalHelpers(TestCase):
    """Direct regression tests for skip paths and materialized balance helpers."""

    def test_suspend_license_flag_recalc_restores_previous_state_after_exception(self):
        assert _flags_suspended() is False

        with pytest.raises(RuntimeError, match="boom"):
            with suspend_license_flag_recalc():
                assert _flags_suspended() is True
                raise RuntimeError("boom")

        assert _flags_suspended() is False

    def test_update_license_flags_ignores_none_and_unsaved_instances(self):
        update_license_flags(None)
        update_license_flags(LicenseDetailsModel(license_number="UNSAVED-SIG"))

    def test_import_item_signal_skips_balance_only_update_fields(self):
        license_obj = _make_license("BAL01")
        import_item = _make_import_item(license_obj)

        with patch("apps.license.signals.update_license_flags") as mock_update:
            update_license_on_import_item_change(
                sender=LicenseImportItemsModel,
                instance=import_item,
                created=False,
                update_fields={"available_value", "debited_value"},
            )

        mock_update.assert_not_called()

    def test_import_item_signal_skips_when_suspended(self):
        license_obj = _make_license("SUS01")
        import_item = _make_import_item(license_obj)

        with patch("apps.license.signals.update_license_flags") as mock_update:
            with suspend_license_flag_recalc():
                update_license_on_import_item_change(
                    sender=LicenseImportItemsModel,
                    instance=import_item,
                    created=False,
                )

        mock_update.assert_not_called()

    def test_update_license_flags_updates_expired_and_null_subrows(self):
        license_obj = LicenseDetailsModel.objects.create(
            license_number="FLAG-SIG01",
            license_expiry_date=timezone.now().date() - timedelta(days=1),
        )

        update_license_flags(license_obj)

        license_obj.flags.refresh_from_db()
        license_obj.balance.refresh_from_db()
        assert license_obj.flags.is_expired is True
        assert license_obj.flags.is_null is True
        assert license_obj.balance.balance_cif == Decimal("0.00")

    def test_update_all_import_items_available_value_updates_open_percent_and_marker_items(self):
        license_obj = _make_license("AVL01")

        with suspend_license_flag_recalc():
            open_item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=1,
                available_value=Decimal("0.00"),
            )
            percent_item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=2,
                condition_type="5%",
                available_value=Decimal("0.00"),
            )
            marker_item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=3,
                cif_fc=Decimal("0.01"),
                available_value=Decimal("0.00"),
            )

        license_obj.balance.balance_cif = Decimal("250.00")
        license_obj.balance.save(update_fields=["balance_cif"])

        with patch(
            "apps.license.services.condition_pool.compute_condition_pools",
            return_value={"5%": Decimal("100.00")},
        ):
            _update_all_import_items_available_value(license_obj)

        open_item.refresh_from_db()
        percent_item.refresh_from_db()
        marker_item.refresh_from_db()
        assert open_item.available_value == Decimal("250.00")
        assert percent_item.available_value == Decimal("100.00")
        assert marker_item.available_value == Decimal("0.01")

    def test_update_all_import_items_available_value_ignores_missing_license(self):
        _update_all_import_items_available_value(None)
        _update_all_import_items_available_value(LicenseDetailsModel(license_number="UNSAVED-AVL"))
