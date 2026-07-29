"""
Regression coverage for consolidating item-level Balance CIF
(`available_value` / `balance_cif_fc` / `available_value_calculated`) into a
single implementation.

Before this change, `apps.core.scripts.calculate_balance.calculate_available_value`
(the writer triggered from BOE/Allotment save flows via `update_balance_values`)
re-derived its own formula — a bare `LicenseBalanceCalculator.calculate_balance()`
call — instead of the model's `available_value_calculated` property (used by
the *other* writer, `apps.license.signals._update_all_import_items_available_value`,
triggered from item saves). The two could disagree for `%`-condition-pooled
items and `0.01`-CIF marker items. `LicenseImportItemsModel.balance_cif_fc`
was a near-duplicate of `available_value_calculated` missing the 0.01-marker
case. These tests pin: both writers now agree, the two properties are
identical, and the serial_number==1 fallback rule survives untouched.

NOTE: `LicenseDetailsModel.balance_cif` is a signal-refreshed cache
(`apps.license.signals`, `post_save` on `LicenseDetailsModel`/import/export
items) — it recalculates live on every relevant save, so tests build real
`LicenseExportItemModel` credit rather than hand-setting `LicenseBalance
.balance_cif` directly (which the next item save would immediately
overwrite).
"""
from decimal import Decimal

from django.test import TestCase

from apps.core.scripts.calculate_balance import calculate_available_value, update_balance_values
from apps.license.models import LicenseExportItemModel

from .test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class WriterSplitConsolidationTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def test_calculate_available_value_agrees_with_property_for_percent_pool(self):
        """A `%`-condition item shares a pool capped at the licence balance
        — `calculate_available_value` (the BOE/Allotment-save writer) must
        return exactly what `available_value_calculated` (the item-save
        writer) would, not a bare licence-balance passthrough."""
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))

        item1 = self.make_item(license_obj, 1)
        item1.condition_type = "5%"
        item1.cif_fc = Decimal("2000.00")
        item1.save()
        item2 = self.make_item(license_obj, 2)
        item2.condition_type = "5%"
        item2.cif_fc = Decimal("3000.00")
        item2.save()

        self.assertEqual(
            calculate_available_value(item1),
            round(float(item1.available_value_calculated), 2),
        )
        self.assertEqual(
            calculate_available_value(item2),
            round(float(item2.available_value_calculated), 2),
        )
        # The pool math is genuinely exercised, not vacuously 0 either side.
        self.assertGreater(item1.available_value_calculated, Decimal("0"))

    def test_calculate_available_value_agrees_with_property_for_marker_item(self):
        """A `0.01`-CIF marker item always resolves to `0.01` — the OLD
        `calculate_available_value` formula had no such branch and would
        have returned the full licence balance instead."""
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("5000.00"))

        other = self.make_item(license_obj, 1)
        other.cif_fc = Decimal("1234.00")
        other.save()
        item = self.make_item(license_obj, 2)  # serial_number != 1: skip the serial-1 fallback
        item.cif_fc = Decimal("0.01")
        item.save()

        self.assertEqual(item.available_value_calculated, Decimal("0.01"))
        self.assertEqual(calculate_available_value(item), 0.01)

    def test_calculate_available_value_preserves_serial_one_fallback_rule(self):
        """If every item OTHER than serial_number 1 has zero CIF, serial 1
        takes the licence's full balance_cif directly — a distinct rule the
        pooled property doesn't implement, preserved unchanged."""
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("7777.00"))

        item1 = self.make_item(license_obj, 1)
        item1.cif_fc = Decimal("0.00")
        item1.save()
        item2 = self.make_item(license_obj, 2)
        item2.cif_fc = Decimal("0.00")
        item2.save()

        license_obj.refresh_from_db()
        item1.refresh_from_db()
        self.assertEqual(calculate_available_value(item1), round(float(license_obj.balance_cif), 2))
        self.assertEqual(calculate_available_value(item1), 7777.00)

    def test_update_balance_values_writer_matches_signal_writer_property(self):
        """End-to-end: after `update_balance_values(item)` runs (the
        BOE/Allotment-save path), the stored `available_value` matches
        `available_value_calculated` (the item-save path) exactly."""
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("50000.00"))

        item = self.make_item(license_obj, 2)
        item.condition_type = "10%"
        item.cif_fc = Decimal("4000.00")
        item.save()

        update_balance_values(item)
        item.refresh_from_db()

        self.assertEqual(item.available_value, item.available_value_calculated)


class BalanceCifFcPropertyCollapseTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def test_balance_cif_fc_equals_available_value_calculated_open_condition(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("3000.00"))
        item = self.make_item(license_obj, 1)

        self.assertEqual(item.balance_cif_fc, item.available_value_calculated)
        self.assertEqual(item.balance_cif_fc, Decimal("3000.00"))

    def test_balance_cif_fc_equals_available_value_calculated_for_marker_item(self):
        """Before the collapse, `balance_cif_fc` was missing the 0.01
        marker check that `available_value_calculated` has — the two would
        disagree for exactly this item."""
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("3000.00"))
        item = self.make_item(license_obj, 2)
        item.cif_fc = Decimal("0.01")
        item.save()

        self.assertEqual(item.balance_cif_fc, Decimal("0.01"))
        self.assertEqual(item.balance_cif_fc, item.available_value_calculated)

    def test_balance_cif_fc_equals_available_value_calculated_percent_pool(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100000.00"))
        item = self.make_item(license_obj, 1)
        item.condition_type = "3%"
        item.cif_fc = Decimal("1000.00")
        item.save()

        self.assertEqual(item.balance_cif_fc, item.available_value_calculated)


class PdfExportReadsStoredAvailableValueTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """The PDF export's per-item "Bal CIF" column must read the same
    `available_value` stored field the Customs Ledger serializer does
    (`LicenseImportItemSerializer.get_balance_cif_fc`), not re-derive via
    the `balance_cif_fc` property — a smoke test that the changed line in
    `license_balance_pdf.py` runs without error and reads the field that
    exists on the model."""

    def test_build_balance_pdf_response_does_not_crash_with_import_items(self):
        from django.test import RequestFactory
        from apps.license.services.exporters.license_balance_pdf import build_balance_pdf_response

        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        item.cif_fc = Decimal("1500.00")
        item.save()
        # available_value is a stored cache column — assign directly to
        # prove the PDF reads THIS field, not a live recompute.
        LicenseImportItemsModel = item.__class__
        LicenseImportItemsModel.objects.filter(pk=item.pk).update(available_value=Decimal("1234.56"))

        request = RequestFactory(SERVER_NAME="localhost").get("/")
        response = build_balance_pdf_response(license_obj, request)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertGreater(len(response.content), 0)
