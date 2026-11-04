"""Summary-card metrics and optional server-side pagination for the License Ledger."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError

from apps.license.services.license_ledger_metrics import build_ledger_metrics
from apps.license.services.licence_balance_report import OVER_ALLOCATED, OVER_UTILISED, REVIEW_REQUIRED, UNMAPPED_ITEM
from apps.license.services.licence_item_balance import RECONCILED
from apps.license.views.ledger import LicenseLedgerViewSet

METRICS_MODULE = "apps.license.services.license_ledger_metrics"


def _dfia(license_id, *, total_sale, balance, expiry=None):
    return {
        "license_id": license_id,
        "license_type": "DFIA",
        "expiry_date": expiry,
        "summary": {"total_sale": Decimal(total_sale), "current_balance": Decimal(balance)},
    }


def _report(original=None, available=None, over=False, status=RECONCILED):
    cif = {} if original is None else {
        "original": str(original), "available": str(available), "is_over_utilised": over,
    }
    return SimpleNamespace(summary_cif=cif, status=status)


class LedgerMetricsTests(TestCase):
    def test_sold_status_uses_the_canonical_rule_for_dfia(self):
        datasets = [
            _dfia(1, total_sale="0", balance="100"),      # not sold
            _dfia(2, total_sale="50", balance="0"),       # fully sold
            _dfia(3, total_sale="30", balance="70"),      # partially sold
        ]
        reports = {1: _report(100, 100), 2: _report(100, 100), 3: _report(100, 70)}
        with patch(f"{METRICS_MODULE}.build_licence_balance_reports", return_value=reports):
            metrics = build_ledger_metrics(datasets, today=date(2026, 11, 4))
        self.assertEqual(metrics["sold_licences"], 1)
        self.assertEqual(metrics["partially_sold_licences"], 1)
        self.assertEqual(metrics["total_licences"], 3)

    def test_cif_totals_are_taken_from_the_balance_engine_and_reconcile(self):
        datasets = [_dfia(1, total_sale="0", balance="0"), _dfia(2, total_sale="0", balance="0"),
                    _dfia(3, total_sale="0", balance="0")]
        reports = {
            1: _report(Decimal("1000"), Decimal("400")),
            2: _report(Decimal("500"), Decimal("-20"), over=True),
            3: _report(),  # no CIF figure: unavailable, never guessed
        }
        with patch(f"{METRICS_MODULE}.build_licence_balance_reports", return_value=reports):
            cif = build_ledger_metrics(datasets, today=date(2026, 11, 4))["cif"]
        self.assertEqual(cif["currency"], "USD")
        self.assertEqual(cif["licence_count"], 2)
        self.assertEqual(cif["unavailable_count"], 1)
        self.assertEqual(cif["original"], "1500.00")
        self.assertEqual(cif["available"], "380.00")
        # utilised = original − available, and original = utilised + available.
        self.assertEqual(cif["utilised"], "1120.00")
        self.assertEqual(Decimal(cif["utilised"]) + Decimal(cif["available"]), Decimal(cif["original"]))

    def test_over_utilisation_is_flagged_and_never_floored(self):
        datasets = [_dfia(1, total_sale="0", balance="0")]
        reports = {1: _report(Decimal("500"), Decimal("-20"), over=True, status=OVER_UTILISED)}
        with patch(f"{METRICS_MODULE}.build_licence_balance_reports", return_value=reports):
            metrics = build_ledger_metrics(datasets, today=date(2026, 11, 4))
        self.assertEqual(metrics["cif_over_utilised_licences"], 1)
        self.assertEqual(metrics["cif"]["available"], "-20.00")

    def test_review_required_is_never_counted_as_confirmed_over_utilisation(self):
        datasets = [_dfia(1, total_sale="0", balance="0")]
        # Negative pooled CIF flagged as over-utilised by the flag, but the engine status is REVIEW_REQUIRED.
        reports = {1: _report(Decimal("500"), Decimal("-20"), over=True, status=REVIEW_REQUIRED)}
        with patch(f"{METRICS_MODULE}.build_licence_balance_reports", return_value=reports):
            metrics = build_ledger_metrics(datasets, today=date(2026, 11, 4))
        self.assertEqual(metrics["cif_over_utilised_licences"], 0)
        self.assertEqual(metrics["review_required_licences"], 1)
        # The negative available is still shown, never floored.
        self.assertEqual(metrics["cif"]["available"], "-20.00")

    def test_other_cif_exceptions_are_counted_as_needing_review(self):
        datasets = [_dfia(1, total_sale="0", balance="0"), _dfia(2, total_sale="0", balance="0")]
        reports = {
            1: _report(Decimal("500"), Decimal("100"), status=OVER_ALLOCATED),
            2: _report(Decimal("500"), Decimal("100"), status=UNMAPPED_ITEM),
        }
        with patch(f"{METRICS_MODULE}.build_licence_balance_reports", return_value=reports):
            metrics = build_ledger_metrics(datasets, today=date(2026, 11, 4))
        # Not in any card before: now every non-confirmed exception is visible for review.
        self.assertEqual(metrics["review_required_licences"], 2)
        self.assertEqual(metrics["cif_over_utilised_licences"], 0)

    def test_expired_licences_are_counted_against_the_as_of_date(self):
        datasets = [
            _dfia(1, total_sale="0", balance="0", expiry=date(2026, 1, 1)),
            _dfia(2, total_sale="0", balance="0", expiry=date(2027, 1, 1)),
            _dfia(3, total_sale="0", balance="0", expiry=None),
        ]
        with patch(f"{METRICS_MODULE}.build_licence_balance_reports", return_value={}):
            metrics = build_ledger_metrics(datasets, today=date(2026, 11, 4))
        self.assertEqual(metrics["expired_licences"], 1)

    def test_a_datetime_expiry_is_compared_as_a_date(self):
        from datetime import datetime
        datasets = [_dfia(1, total_sale="0", balance="0", expiry=datetime(2026, 1, 1, 9, 30))]
        with patch(f"{METRICS_MODULE}.build_licence_balance_reports", return_value={}):
            metrics = build_ledger_metrics(datasets, today=date(2026, 11, 4))
        self.assertEqual(metrics["expired_licences"], 1)

    def test_incentive_over_utilisation_uses_the_ledger_balance_not_cif(self):
        datasets = [{
            "license_id": 999999, "license_type": "RODTEP", "expiry_date": None,
            "summary": {"total_sale": Decimal("10"), "current_balance": Decimal("-5")},
        }]
        with patch(f"{METRICS_MODULE}.build_licence_balance_reports") as engine:
            metrics = build_ledger_metrics(datasets, today=date(2026, 11, 4))
        engine.assert_not_called()  # incentive licences have no CIF
        # Negative INR ledger balance is reported separately, never as a CIF figure.
        self.assertEqual(metrics["incentive_negative_balance_licences"], 1)
        self.assertEqual(metrics["cif_over_utilised_licences"], 0)
        self.assertEqual(metrics["cif"]["licence_count"], 0)


class PaginationContractTests(SimpleTestCase):
    def _paginate(self, query, rows):
        request = RequestFactory().get("/api/license-ledger/license-wise/", query)
        request.query_params = request.GET
        return LicenseLedgerViewSet._paginate_collection(request, rows)

    def test_absent_params_return_the_complete_collection_unchanged(self):
        rows = [1, 2, 3]
        page, pagination = self._paginate({}, rows)
        self.assertEqual(page, rows)
        self.assertEqual(pagination["count"], 3)
        self.assertFalse(pagination["has_next"])
        self.assertFalse(pagination["paginated"])

    def test_pages_slice_in_order_and_report_totals(self):
        rows = list(range(1, 8))
        page, pagination = self._paginate({"page": "2", "page_size": "3"}, rows)
        self.assertEqual(page, [4, 5, 6])
        self.assertEqual(pagination, {"count": 7, "page": 2, "page_size": 3,
                                      "total_pages": 3, "has_next": True, "paginated": True})
        last, last_info = self._paginate({"page": "3", "page_size": "3"}, rows)
        self.assertEqual(last, [7])
        self.assertFalse(last_info["has_next"])

    def test_out_of_range_page_is_empty_not_an_error(self):
        page, pagination = self._paginate({"page": "9", "page_size": "3"}, [1, 2])
        self.assertEqual(page, [])
        self.assertEqual(pagination["count"], 2)

    def test_invalid_pagination_is_rejected(self):
        for query in ({"page": "0"}, {"page": "x"}, {"page_size": "0"}, {"page_size": "201"}):
            with self.subTest(query=query), self.assertRaises(ValidationError):
                self._paginate(query, [1])
