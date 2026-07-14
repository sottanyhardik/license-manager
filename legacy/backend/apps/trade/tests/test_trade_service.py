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
    PartnerTradeNotFound,
)


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
