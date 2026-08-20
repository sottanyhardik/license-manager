# trade/tests/test_trade_service.py
"""
Unit tests for trade/services/trade_service.py.

These tests hit the service layer directly — no HTTP request, no DRF Response.
The DB is exercised only for link_trades and get_prefilled_invoice_number;
parse_date_strict is pure Python and needs no DB.
"""

import itertools
from datetime import date
from decimal import Decimal

from django.test import TestCase

# IEC codes must be unique across all test company creates (CompanyModel.iec is
# unique=True, not null/blank).  Use a module-level counter so each helper call
# produces a distinct 10-character string regardless of test ordering.
_iec_counter = itertools.count(1)


def _unique_iec() -> str:
    return f"{next(_iec_counter):010d}"

from apps.trade.services.trade_service import (
    parse_date_strict,
    get_prefilled_invoice_number,
    build_trade_summary,
    link_trades,
    stamp_boe_invoice_from_trade,
    PartnerTradeNotFound,
    copy_sale_to_purchase,
    copy_purchase_to_sale,
)


class CounterpartCopyTests(TestCase):
    def setUp(self):
        from apps.core.models import CompanyModel
        from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
        from apps.trade.models import LicenseTrade, LicenseTradeLine
        self.seller = CompanyModel.objects.create(name='Labdhi Mercantile LLP', iec=_unique_iec())
        self.buyer = CompanyModel.objects.create(name='Labdhi Global LLP', iec=_unique_iec())
        self.license = LicenseDetailsModel.objects.create(
            license_number='0311049585', exporter=self.seller,
            license_date=date(2026, 8, 3), license_expiry_date=date(2027, 8, 3),
        )
        self.item = LicenseImportItemsModel.objects.create(license=self.license, serial_number=1, description='DFIA item')
        self.sale = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, from_company=self.seller, to_company=self.buyer,
            invoice_number='LML/2026-27/0023', invoice_date=date(2026, 8, 3),
        )
        LicenseTradeLine.objects.create(
            trade=self.sale, sr_number=self.item, description='DFIA item', mode=LicenseTradeLine.MODE_CIF_INR,
            qty_kg=Decimal('2.0000'), cif_fc=Decimal('218076.00'), exc_rate=Decimal('1.0000'),
            cif_inr=Decimal('218076.00'), pct=Decimal('100.000'), amount_inr=Decimal('218076.00'),
        )

    def test_sale_to_purchase_is_idempotent_and_reciprocal(self):
        source, purchase, created = copy_sale_to_purchase(self.sale.id)
        self.assertTrue(created)
        self.assertEqual(purchase.direction, 'PURCHASE')
        self.assertEqual(purchase.from_company_id, self.seller.id)
        self.assertEqual(purchase.to_company_id, self.buyer.id)
        self.assertEqual(purchase.total_amount, Decimal('218076.00'))
        self.assertEqual(purchase.lines.count(), 1)
        source.refresh_from_db(); purchase.refresh_from_db()
        self.assertEqual(source.counterpart_id, purchase.id)
        self.assertEqual(purchase.counterpart_id, source.id)
        _, repeated, created_again = copy_sale_to_purchase(self.sale.id)
        self.assertFalse(created_again)
        self.assertEqual(repeated.id, purchase.id)

    def test_purchase_to_sale_returns_existing_pair(self):
        _, purchase, _ = copy_sale_to_purchase(self.sale.id)
        source, sale, created = copy_purchase_to_sale(purchase.id)
        self.assertFalse(created)
        self.assertEqual(source.id, purchase.id)
        self.assertEqual(sale.id, self.sale.id)

    def test_deleting_one_paired_line_deletes_the_counterpart_without_protect_loop(self):
        _, purchase, _ = copy_sale_to_purchase(self.sale.id)
        source_line = self.sale.lines.get()
        counterpart_line_id = purchase.lines.get().id

        source_line.delete()

        from apps.trade.models import LicenseTradeLine
        self.assertFalse(LicenseTradeLine.objects.filter(pk=source_line.pk).exists())
        self.assertFalse(LicenseTradeLine.objects.filter(pk=counterpart_line_id).exists())


# ---------------------------------------------------------------------------
# parse_date_strict
# ---------------------------------------------------------------------------

class ParseDateStrictTests(TestCase):
    """Tests for parse_date_strict — pure Python, no DB."""

    def test_valid_iso_date(self):
        result = parse_date_strict("2025-06-15")
        self.assertEqual(result, date(2025, 6, 15))

    def test_none_returns_none(self):
        self.assertIsNone(parse_date_strict(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_date_strict(""))

    def test_invalid_format_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            parse_date_strict("15-06-2025")
        self.assertIn("YYYY-MM-DD", str(ctx.exception))

    def test_garbage_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_date_strict("not-a-date")

    def test_partial_date_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_date_strict("2025-06")


# ---------------------------------------------------------------------------
# get_prefilled_invoice_number
# ---------------------------------------------------------------------------

class GetPrefilledInvoiceNumberTests(TestCase):
    """Tests for get_prefilled_invoice_number — requires DB (company lookup)."""

    def _make_company(self, name):
        from apps.core.models import CompanyModel
        return CompanyModel.objects.create(name=name, iec=_unique_iec())

    def test_invalid_direction_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            get_prefilled_invoice_number(
                direction="EXPORT",
                company_id=999,
            )
        self.assertIn("EXPORT", str(ctx.exception))

    def test_missing_company_raises_does_not_exist(self):
        from apps.core.models import CompanyModel
        with self.assertRaises(CompanyModel.DoesNotExist):
            get_prefilled_invoice_number(
                direction="SALE",
                company_id=999999,
            )

    def test_sale_returns_formatted_number(self):
        company = self._make_company("Labdhi Mercantile LLP")
        result = get_prefilled_invoice_number(
            direction="SALE",
            company_id=company.pk,
            invoice_date=date(2025, 6, 1),
        )
        # PREFIX = LML (first letter of each word), FY = 2025-26
        self.assertTrue(result.startswith("LML/2025-26/"))
        # Should end in 4-digit padded sequence
        seq_part = result.split("/")[-1]
        self.assertEqual(len(seq_part), 4)
        self.assertTrue(seq_part.isdigit())

    def test_purchase_result_has_p_prefix(self):
        company = self._make_company("Labdhi Mercantile LLP")
        result = get_prefilled_invoice_number(
            direction="PURCHASE",
            company_id=company.pk,
            invoice_date=date(2025, 6, 1),
        )
        self.assertTrue(result.startswith("P-LML/2025-26/"))

    def test_commission_sale_has_com_prefix(self):
        company = self._make_company("Labdhi Mercantile LLP")
        result = get_prefilled_invoice_number(
            direction="COMMISSION_SALE",
            company_id=company.pk,
            invoice_date=date(2025, 6, 1),
        )
        self.assertTrue(result.startswith("COM-LML/2025-26/"))

    def test_commission_purchase_has_com_p_prefix(self):
        company = self._make_company("Labdhi Mercantile LLP")
        result = get_prefilled_invoice_number(
            direction="COMMISSION_PURCHASE",
            company_id=company.pk,
            invoice_date=date(2025, 6, 1),
        )
        self.assertTrue(result.startswith("COM-P-LML/2025-26/"))

    def test_sequence_increments(self):
        """Second call for the same FY/company returns a higher sequence number."""
        from apps.core.models import CompanyModel
        from apps.trade.models import LicenseTrade
        company = self._make_company("Seq Test Co")

        # Pre-create a partner company so the CheckConstraint (from_company != to_company) passes
        other = CompanyModel.objects.create(name="Other Seq Co", iec=_unique_iec())

        # Pre-create one invoice in the same series
        LicenseTrade.objects.create(
            direction="SALE",
            from_company=company,
            to_company=other,
            invoice_number="STC/2025-26/0001",
            invoice_date=date(2025, 6, 1),
        )

        result = get_prefilled_invoice_number(
            direction="SALE",
            company_id=company.pk,
            invoice_date=date(2025, 6, 1),
        )
        self.assertTrue(result.endswith("/0002"), f"Expected /0002, got {result}")


# ---------------------------------------------------------------------------
# build_trade_summary
# ---------------------------------------------------------------------------

class BuildTradeSummaryTests(TestCase):
    """Tests for build_trade_summary — requires DB (payments/lines count)."""

    def _make_trade(self):
        from apps.core.models import CompanyModel
        from apps.trade.models import LicenseTrade
        c1 = CompanyModel.objects.create(name="Alpha Corp", iec=_unique_iec())
        c2 = CompanyModel.objects.create(name="Beta Ltd", iec=_unique_iec())
        return LicenseTrade.objects.create(
            direction="PURCHASE",
            from_company=c1,
            to_company=c2,
            invoice_number="TEST/2025-26/0001",
            invoice_date=date(2025, 6, 1),
        )

    def test_summary_contains_expected_keys(self):
        trade = self._make_trade()
        summary = build_trade_summary(trade)
        expected_keys = {
            "id", "direction", "invoice_number", "invoice_date",
            "subtotal_amount", "roundoff", "total_amount",
            "paid_or_received", "due_amount", "lines_count", "payments_count",
        }
        self.assertEqual(set(summary.keys()), expected_keys)

    def test_summary_values_match_model(self):
        trade = self._make_trade()
        summary = build_trade_summary(trade)
        self.assertEqual(summary["id"], trade.id)
        self.assertEqual(summary["direction"], "PURCHASE")
        self.assertEqual(summary["invoice_number"], "TEST/2025-26/0001")
        self.assertEqual(summary["lines_count"], 0)
        self.assertEqual(summary["payments_count"], 0)

    def test_numeric_fields_are_strings(self):
        """Decimal amounts must be serialised to strings (not float) by the service."""
        trade = self._make_trade()
        summary = build_trade_summary(trade)
        for key in ("subtotal_amount", "roundoff", "total_amount",
                    "paid_or_received", "due_amount"):
            self.assertIsInstance(summary[key], str, f"{key} should be str")


# ---------------------------------------------------------------------------
# link_trades
# ---------------------------------------------------------------------------

class LinkTradesTests(TestCase):
    """Tests for link_trades — DB required."""

    def _make_trade(self, inv, direction="SALE"):
        from apps.core.models import CompanyModel
        from apps.trade.models import LicenseTrade
        c = CompanyModel.objects.create(name=f"Co for {inv}", iec=_unique_iec())
        return LicenseTrade.objects.create(
            direction=direction,
            from_company=c,
            invoice_number=inv,
            invoice_date=date(2025, 6, 1),
        )

    def test_link_two_trades(self):
        from apps.trade.models import LicenseTrade
        t1 = self._make_trade("INV-001")
        t2 = self._make_trade("INV-002")

        updated = link_trades(trade_pk=t1.pk, partner_pk=t2.pk)

        self.assertEqual(updated.linked_trade_id, t2.pk)
        t2.refresh_from_db()
        self.assertEqual(t2.linked_trade_id, t1.pk)

    def test_unlink_trades(self):
        from apps.trade.models import LicenseTrade
        t1 = self._make_trade("INV-003")
        t2 = self._make_trade("INV-004")

        # Link first
        link_trades(trade_pk=t1.pk, partner_pk=t2.pk)

        # Now unlink
        updated = link_trades(trade_pk=t1.pk, partner_pk=None)

        self.assertIsNone(updated.linked_trade_id)
        t2.refresh_from_db()
        self.assertIsNone(t2.linked_trade_id)

    def test_self_link_raises_value_error(self):
        t1 = self._make_trade("INV-005")
        with self.assertRaises(ValueError) as ctx:
            link_trades(trade_pk=t1.pk, partner_pk=t1.pk)
        self.assertIn("itself", str(ctx.exception))

    def test_missing_partner_raises_partner_not_found(self):
        t1 = self._make_trade("INV-006")
        with self.assertRaises(PartnerTradeNotFound):
            link_trades(trade_pk=t1.pk, partner_pk=999999)

    def test_relinking_clears_old_partner(self):
        """If t1 was already linked to t2, linking t1 to t3 should clear t2's back-link."""
        from apps.trade.models import LicenseTrade
        t1 = self._make_trade("INV-007")
        t2 = self._make_trade("INV-008")
        t3 = self._make_trade("INV-009")

        link_trades(trade_pk=t1.pk, partner_pk=t2.pk)
        link_trades(trade_pk=t1.pk, partner_pk=t3.pk)

        t2.refresh_from_db()
        self.assertIsNone(t2.linked_trade_id)
        t3.refresh_from_db()
        self.assertEqual(t3.linked_trade_id, t1.pk)


# ---------------------------------------------------------------------------
# stamp_boe_invoice_from_trade — hidden-BOE guard regression
#
# A genuinely-hidden (previous-owner) BOE must never have its invoice_no
# silently overwritten by attaching it to an unrelated trade for invoicing
# purposes -- that would un-hide it with no audit trail and inflate the
# license's live balance. Only the audited hide_boe/restore_boe workflow may
# change hidden state. These fixtures are deliberately independent of any
# other test's company/license/BOE so they exercise the general rule, not
# just one specific license.
# ---------------------------------------------------------------------------

class StampBoeInvoiceFromTradeHiddenGuardTests(TestCase):
    def _make_company(self, name="Stamp Test Co"):
        from apps.core.models import CompanyModel
        return CompanyModel.objects.create(iec=_unique_iec(), name=name)

    def _make_license(self, company, license_number=None):
        from apps.license.models import LicenseDetailsModel
        return LicenseDetailsModel.objects.create(
            license_number=license_number or f"03{next(_iec_counter):08d}",
            license_date=date(2024, 1, 1),
            license_expiry_date=date(2027, 1, 1),
            exporter=company,
        )

    def _make_item(self, license_obj, serial_number=1):
        from apps.license.models import LicenseImportItemsModel
        return LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=serial_number,
            description=f"Stamp Test Item {serial_number}",
            quantity=Decimal("1000.000"),
            available_quantity=Decimal("1000.000"),
        )

    def _make_export_item(self, license_obj, cif_fc):
        from apps.license.models import LicenseExportItemModel
        return LicenseExportItemModel.objects.create(license=license_obj, cif_fc=cif_fc)

    def _make_boe(self, company, invoice_no=""):
        from apps.bill_of_entry.models import BillOfEntryModel
        return BillOfEntryModel.objects.create(
            company=company,
            bill_of_entry_number=str(next(_iec_counter)),
            bill_of_entry_date=date(2026, 5, 1),
            exchange_rate=Decimal("84.50"),
            invoice_no=invoice_no,
        )

    def _make_debit_row(self, boe, item, cif_fc, qty=Decimal("10.000")):
        from apps.bill_of_entry.models import RowDetails
        from apps.core.constants import DEBIT
        return RowDetails.objects.create(
            bill_of_entry=boe,
            sr_number=item,
            transaction_type=DEBIT,
            cif_inr=cif_fc * Decimal("84.5"),
            cif_fc=cif_fc,
            qty=qty,
        )

    def _make_sale_trade(self, company, invoice_number, invoice_date_=date(2026, 6, 1)):
        from apps.trade.models import LicenseTrade
        return LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE,
            from_company=company,
            invoice_number=invoice_number,
            invoice_date=invoice_date_,
        )

    def test_genuinely_hidden_boe_is_not_restamped(self):
        """Attaching a genuinely-hidden BOE to an unrelated Sale trade for
        invoicing must not overwrite invoice_no, must not un-hide it, and
        must not move the license's live balance."""
        from apps.bill_of_entry.models import genuinely_hidden_boe_ids
        from apps.bill_of_entry.services.boe_service import hide_boe
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        from apps.reconciliation.models import ReconciliationLog

        company = self._make_company("Hidden Guard Co")
        license_obj = self._make_license(company)
        item = self._make_item(license_obj)
        self._make_export_item(license_obj, cif_fc=Decimal("50000.00"))

        boe = self._make_boe(company, invoice_no="LGL/2026-27/0099")
        self._make_debit_row(boe, item, cif_fc=Decimal("5000.00"), qty=Decimal("50.000"))

        hide_result = hide_boe(boe, user=None, reason="Previous owner utilisation")
        self.assertTrue(hide_result["is_hidden"])
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "OTH")

        license_obj.refresh_from_db()
        balance_before = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
        log_count_before = ReconciliationLog.objects.count()

        # Attach to an unrelated Sale trade purely for invoicing.
        trade = self._make_sale_trade(company, invoice_number="PUR/2026-27/9999")
        trade.boes.add(boe)
        stamp_boe_invoice_from_trade(trade, boe)

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "OTH", "hidden BOE's invoice_no must not be overwritten")
        self.assertIn(boe.id, genuinely_hidden_boe_ids(boe_ids=[boe.id]),
                      "BOE must remain genuinely hidden after being linked to a trade")

        license_obj.refresh_from_db()
        balance_after = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
        self.assertEqual(balance_after, balance_before,
                          "linking a hidden BOE to a trade must not move the live balance")

        # stamp_boe_invoice_from_trade itself must not write any audit trail
        # (only the link view's own ACTION_LINK log, if any, is expected).
        self.assertEqual(
            ReconciliationLog.objects.exclude(action=ReconciliationLog.ACTION_LINK).count(),
            log_count_before,
        )

    def test_non_hidden_boe_is_still_stamped_normally(self):
        """Baseline: the fix must not regress ordinary (non-hidden) linking."""
        company = self._make_company("Normal Stamp Co")
        license_obj = self._make_license(company)
        item = self._make_item(license_obj)
        boe = self._make_boe(company, invoice_no="")
        self._make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        trade = self._make_sale_trade(company, invoice_number="PUR/2026-27/0001",
                                       invoice_date_=date(2026, 6, 15))
        trade.boes.add(boe)
        stamp_boe_invoice_from_trade(trade, boe)

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "PUR/2026-27/0001")
        self.assertEqual(boe.invoice_date, date(2026, 6, 15))

    def test_coincidental_oth_invoice_no_without_hide_log_is_still_stamped(self):
        """`invoice_no == 'OTH'` alone is legacy free-text data on ~35-40% of
        real BOEs, NOT a hidden marker, unless a HIDE_BOE log backs it up
        (see genuinely_hidden_boe_ids). The guard must not over-fire and
        block stamping for these — that would be a new, opposite bug."""
        company = self._make_company("Coincidental OTH Co")
        license_obj = self._make_license(company)
        item = self._make_item(license_obj)
        boe = self._make_boe(company, invoice_no="OTH")  # legacy data, never hidden via hide_boe
        self._make_debit_row(boe, item, cif_fc=Decimal("2000.00"))

        trade = self._make_sale_trade(company, invoice_number="PUR/2026-27/0002")
        trade.boes.add(boe)
        stamp_boe_invoice_from_trade(trade, boe)

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "PUR/2026-27/0002",
                          "an 'OTH' BOE with no genuine hide log must be stamped like any other")

    def test_restored_boe_is_stamped_normally_afterwards(self):
        """Once a BOE is restored (audited path), it is no longer genuinely
        hidden and must go back to normal stamping behaviour."""
        from apps.bill_of_entry.services.boe_service import hide_boe, restore_boe

        company = self._make_company("Restore Then Stamp Co")
        license_obj = self._make_license(company)
        item = self._make_item(license_obj)
        boe = self._make_boe(company, invoice_no="LGL/2026-27/0050")
        self._make_debit_row(boe, item, cif_fc=Decimal("3000.00"))

        hide_boe(boe, user=None, reason="Previous owner")
        restore_boe(boe, user=None, reason="Restored in error")
        boe.refresh_from_db()
        self.assertNotEqual(boe.invoice_no, "OTH")

        trade = self._make_sale_trade(company, invoice_number="PUR/2026-27/0003")
        trade.boes.add(boe)
        stamp_boe_invoice_from_trade(trade, boe)

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "PUR/2026-27/0003")

    def test_trade_without_invoice_number_is_noop_regardless_of_hidden_state(self):
        """Pre-existing early-return behaviour (empty trade.invoice_number)
        must be unaffected by the new guard, hidden or not."""
        from apps.bill_of_entry.services.boe_service import hide_boe

        company = self._make_company("No Invoice Number Co")
        license_obj = self._make_license(company)
        item = self._make_item(license_obj)
        boe = self._make_boe(company, invoice_no="LGL/2026-27/0060")
        self._make_debit_row(boe, item, cif_fc=Decimal("1500.00"))
        hide_boe(boe, user=None, reason="Previous owner")
        boe.refresh_from_db()
        original_invoice_no = boe.invoice_no

        trade = self._make_sale_trade(company, invoice_number="")
        trade.boes.add(boe)
        stamp_boe_invoice_from_trade(trade, boe)

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, original_invoice_no)

    def test_serializer_update_call_site_does_not_unhide_boe(self):
        """The second live call site (LicenseTradeSerializer.update()'s
        per-BOE re-stamp loop) must share the same guard -- both call sites
        route through the same stamp_boe_invoice_from_trade, so fixing it
        once closes both."""
        from apps.bill_of_entry.models import genuinely_hidden_boe_ids
        from apps.bill_of_entry.services.boe_service import hide_boe
        from apps.trade.serializers import LicenseTradeSerializer

        company = self._make_company("Serializer Guard Co")
        license_obj = self._make_license(company)
        item = self._make_item(license_obj)
        boe = self._make_boe(company, invoice_no="LGL/2026-27/0070")
        self._make_debit_row(boe, item, cif_fc=Decimal("4000.00"))
        hide_boe(boe, user=None, reason="Previous owner")
        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "OTH")

        trade = self._make_sale_trade(company, invoice_number="PUR/2026-27/0004")

        LicenseTradeSerializer().update(trade, {"boes": [boe]})

        boe.refresh_from_db()
        self.assertEqual(boe.invoice_no, "OTH",
                          "LicenseTradeSerializer.update() must not unhide a genuinely-hidden BOE")
        self.assertIn(boe.id, genuinely_hidden_boe_ids(boe_ids=[boe.id]))
