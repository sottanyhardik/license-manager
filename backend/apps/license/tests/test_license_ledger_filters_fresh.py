from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.license_ledger_filters import (
    LicenseLedgerFilters,
    LICENSE_LEDGER_TYPE_VALUES,
    _apply_database_filters,
    build_filtered_license_ledger_data,
    normalize_license_type_filter,
)
from apps.trade.models import LicenseTrade, LicenseTradeLine


class _Ids:
    def __init__(self, values):
        self.values = values

    def values_list(self, *_args, **_kwargs):
        return list(self.values)


def _dataset(license_id, license_type, first_purchase_date=None):
    balances = {1: Decimal("5000"), 2: Decimal("3000"), 3: Decimal("1000")}
    return {
        "license_id": license_id,
        "license_number": f"LIC-{license_id}",
        "license_type": license_type,
        "license_date": date(2026, 1, license_id),
        "first_purchase_date": first_purchase_date,
        "summary": {"current_balance": balances[license_id]},
    }


class FreshLicenseLedgerFilterTests(SimpleTestCase):
    def test_license_type_contract_uses_model_choices(self):
        self.assertEqual(
            LICENSE_LEDGER_TYPE_VALUES,
            {"ALL", "DFIA", "ALL_INCENTIVE", "RODTEP", "ROSTL", "MEIS"},
        )

    def test_license_type_contract_normalizes_supported_values(self):
        expected = {
            None: "ALL",
            "": "ALL",
            "all": "ALL",
            "dfia": "DFIA",
            "all_incentive": "ALL_INCENTIVE",
            "INCENTIVE": "ALL_INCENTIVE",  # compatibility alias
            "rodtep": "RODTEP",
            "rostl": "ROSTL",
            "meis": "MEIS",
        }
        for supplied, canonical in expected.items():
            with self.subTest(supplied=supplied):
                self.assertEqual(normalize_license_type_filter(supplied), canonical)

    def test_invalid_license_type_is_rejected_instead_of_broadening_to_all(self):
        with self.assertRaises(ValidationError) as raised:
            LicenseLedgerFilters.from_query_params({"license_type": "AUTO"})
        self.assertIn("license_type", raised.exception.detail)

    def test_license_numbers_are_parsed_as_a_deduplicated_csv_list(self):
        filters = LicenseLedgerFilters.from_query_params({
            "license_numbers": " 3111004973,3111004966, 3111004973 ,,0311044946 ",
            "exclude_license_numbers": " 0311044676, 0311044676, 0311051203 ",
        })
        self.assertEqual(
            filters.license_numbers,
            ("3111004973", "3111004966", "0311044946"),
        )
        self.assertEqual(filters.exclude_license_numbers, ("0311044676", "0311051203"))

    def test_every_license_type_is_applied_at_queryset_level(self):
        all_dfia, all_incentive = _apply_database_filters(
            LicenseLedgerFilters(license_type="ALL"), None,
        )
        self.assertFalse(all_dfia.query.is_empty())
        self.assertFalse(all_incentive.query.is_empty())

        dfia, no_incentive = _apply_database_filters(
            LicenseLedgerFilters(license_type="DFIA"), None,
        )
        self.assertFalse(dfia.query.is_empty())
        self.assertTrue(no_incentive.query.is_empty())

        no_dfia, all_incentive = _apply_database_filters(
            LicenseLedgerFilters(license_type="ALL_INCENTIVE"), None,
        )
        self.assertTrue(no_dfia.query.is_empty())
        self.assertFalse(all_incentive.query.is_empty())

        for concrete_type in ("RODTEP", "ROSTL", "MEIS"):
            with self.subTest(concrete_type=concrete_type):
                no_dfia, incentive = _apply_database_filters(
                    LicenseLedgerFilters(license_type=concrete_type), None,
                )
                self.assertTrue(no_dfia.query.is_empty())
                self.assertIn(concrete_type, str(incentive.query))

    def test_new_contract_parses_every_filter(self):
        filters = LicenseLedgerFilters.from_query_params({
            "buying_company_id": "7", "license_type": "rodtep", "min_balance": "100.50",
            "search": "  exporter ", "ordering": "balance_value", "active_only": "true",
            "norm": "E1", "purchase_status": "GE", "purchase_bill": "with_purchase_bill",
            "purchase_date_from": "2025-12-01", "purchase_date_to": "2026-03-31",
        })
        self.assertEqual(filters.company_id, 7)
        self.assertEqual(filters.license_type, "RODTEP")
        self.assertEqual(filters.min_balance, Decimal("100.50"))
        self.assertEqual(filters.search, "exporter")
        self.assertEqual(filters.ordering, "balance_value")
        self.assertTrue(filters.active_only)
        self.assertEqual(filters.norm, "E1")
        self.assertEqual(filters.purchase_status, "GE")
        self.assertEqual(filters.purchase_bill, "WITH_PURCHASE_BILL")
        self.assertEqual(filters.purchase_date_from, date(2025, 12, 1))
        self.assertEqual(filters.purchase_date_to, date(2026, 3, 31))

    def test_combined_database_filters_compile_to_one_queryset_per_family(self):
        filters = LicenseLedgerFilters(
            company_id=7, license_type="DFIA", search="exporter", active_only=True,
            norm="E1", purchase_status="GE", purchase_bill="WITH_PURCHASE_BILL",
        )
        dfia, incentive = _apply_database_filters(filters, authorization_company_id=7)
        sql = str(dfia.query)
        self.assertIn("license_number", sql)
        self.assertIn("purchase_status", sql)
        self.assertIn("norm_class", sql)
        self.assertIn("EXISTS", sql.upper())
        self.assertTrue(incentive.query.is_empty())

    @patch("apps.license.services.license_ledger_filters.IncentiveLicense.objects.filter")
    @patch("apps.license.services.license_ledger_filters.CanonicalLedgerService.build_collection_summary", return_value={})
    @patch("apps.license.services.license_ledger_filters.CanonicalLedgerService.build_canonical_ledger_dataset", side_effect=_dataset)
    @patch("apps.license.services.license_ledger_filters.LicenseBalanceCalculator.calculate_financial_balance_for_licenses", return_value={1: Decimal("5000"), 2: Decimal("3000"), 3: Decimal("1000")})
    @patch("apps.license.services.license_ledger_filters.incentive_first_purchase_date_by_license", return_value={})
    @patch("apps.license.services.license_ledger_filters.first_purchase_date_by_license")
    @patch("apps.license.services.license_ledger_filters._apply_database_filters", return_value=(_Ids([1, 2, 3]), _Ids([])))
    def test_date_range_uses_global_first_purchase_before_range(
        self, _db_filters, first_dates, _incentive_dates, _live_balances, build_dataset, _summary, incentive_filter,
    ):
        first_dates.return_value = {
            1: date(2025, 12, 1),  # License A also has later Jan/Mar purchases.
            2: date(2026, 1, 15),
            3: date(2026, 3, 20),
        }
        incentive_filter.return_value.values_list.return_value = []

        january_to_march = build_filtered_license_ledger_data({
            "purchase_date_from": "2026-01-01", "purchase_date_to": "2026-03-31",
        })
        self.assertEqual([row["license_id"] for row in january_to_march["licenses"]], [3, 2])
        self.assertNotIn(1, [row["license_id"] for row in january_to_march["licenses"]])

        december = build_filtered_license_ledger_data({
            "purchase_date_from": "2025-12-01", "purchase_date_to": "2025-12-31",
        })
        self.assertEqual([row["license_id"] for row in december["licenses"]], [1])
        first_dates.assert_called_with([1, 2, 3])
        self.assertEqual(build_dataset.call_args.kwargs["first_purchase_date"], date(2025, 12, 1))

    @patch("apps.license.services.license_ledger_filters.IncentiveLicense.objects.filter")
    @patch("apps.license.services.license_ledger_filters.CanonicalLedgerService.build_collection_summary", return_value={})
    @patch("apps.license.services.license_ledger_filters.CanonicalLedgerService.build_canonical_ledger_dataset", side_effect=_dataset)
    @patch("apps.license.services.license_ledger_filters.LicenseBalanceCalculator.calculate_financial_balance_for_licenses", return_value={1: Decimal("5000"), 2: Decimal("3000"), 3: Decimal("1000")})
    @patch("apps.license.services.license_ledger_filters.incentive_first_purchase_date_by_license", return_value={})
    @patch("apps.license.services.license_ledger_filters.first_purchase_date_by_license", return_value={1: date(2025, 12, 1), 2: date(2026, 1, 15), 3: date(2026, 3, 20)})
    @patch("apps.license.services.license_ledger_filters._apply_database_filters", return_value=(_Ids([1, 2, 3]), _Ids([])))
    def test_min_balance_uses_canonical_summary_and_combines_with_date(
        self, _db_filters, _first_dates, _incentive_dates, _live_balances, _build_dataset, _summary, incentive_filter,
    ):
        incentive_filter.return_value.values_list.return_value = []
        result = build_filtered_license_ledger_data({
            "min_balance": "4000", "purchase_date_from": "2025-12-01", "purchase_date_to": "2026-03-31",
        })
        self.assertEqual([row["license_id"] for row in result["licenses"]], [1])


@pytest.mark.django_db
def test_company_filter_uses_purchase_buyer_not_sale_or_exporter(
    test_company, test_company_2, test_license, test_port,
):
    """Mixed company roles cannot admit a licence owned by another buyer."""
    wrong_item = test_license.import_license.first()
    LicenseTradeLine.objects.create(
        trade=LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE, license_type="DFIA",
            from_company=test_company, to_company=test_company_2,
            invoice_number="BUY-GLOBAL", invoice_date=date(2026, 1, 1),
        ),
        sr_number=wrong_item, amount_inr=Decimal("100"), cif_fc=Decimal("100"),
    )
    # The selected company is exporter and SALE owner, but is not the buyer.
    LicenseTradeLine.objects.create(
        trade=LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, license_type="DFIA",
            from_company=test_company, to_company=test_company_2,
            invoice_number="SALE-MERCANTILE", invoice_date=date(2026, 2, 1),
        ),
        sr_number=wrong_item, amount_inr=Decimal("50"), cif_fc=Decimal("50"),
    )

    correct_license = LicenseDetailsModel.objects.create(
        license_number="BUYER-RELATION-TEST", license_date=date(2026, 1, 1),
        license_expiry_date=date(2027, 1, 1), exporter=test_company_2, port=test_port,
    )
    correct_item = LicenseImportItemsModel.objects.create(
        license=correct_license, serial_number=1, description="Correct buyer item",
        quantity=Decimal("100"), available_quantity=Decimal("100"),
        cif_fc=Decimal("100"), cif_inr=Decimal("8000"),
    )
    LicenseTradeLine.objects.create(
        trade=LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE, license_type="DFIA",
            from_company=test_company_2, to_company=test_company,
            invoice_number="BUY-MERCANTILE", invoice_date=date(2026, 1, 2),
        ),
        sr_number=correct_item, amount_inr=Decimal("100"), cif_fc=Decimal("100"),
    )
    # Reverse mixed relationship: sale/exporter is another company.
    LicenseTradeLine.objects.create(
        trade=LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, license_type="DFIA",
            from_company=test_company_2, to_company=test_company,
            invoice_number="SALE-GLOBAL", invoice_date=date(2026, 2, 2),
        ),
        sr_number=correct_item, amount_inr=Decimal("50"), cif_fc=Decimal("50"),
    )

    dfia, _ = _apply_database_filters(
        LicenseLedgerFilters(company_id=test_company.id), authorization_company_id=None,
    )
    returned_ids = set(dfia.values_list("id", flat=True))
    assert correct_license.id in returned_ids
    assert test_license.id not in returned_ids


@pytest.mark.django_db
def test_summary_api_rejects_invalid_license_type(authenticated_client):
    response = authenticated_client.get(
        reverse("license:license-ledger-summary"),
        {"license_type": "NOT_A_LICENSE_TYPE"},
    )
    assert response.status_code == 400
    assert "license_type" in response.json()
