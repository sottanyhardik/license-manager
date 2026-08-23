"""Pure contract tests for the canonical Financial Ledger export DTO."""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.license.services.canonical_ledger_service import CanonicalLedgerService


class FinancialLedgerExportDTOTests(SimpleTestCase):
    @staticmethod
    def _dataset(identifier, norm, purchase, sale, *, company_id=881):
        purchase, sale = Decimal(purchase), Decimal(sale)
        return {
            "license_id": identifier,
            "license_number": f"L-{identifier}",
            "license_type": "DFIA",
            "license_date": date(2025, 1, identifier),
            "first_purchase_date": date(2025, 2, identifier),
            "sion_norms": norm,
            "has_purchase_bill": purchase > 0,
            "summary": {"current_balance": Decimal("10.00"), "balance_currency": "USD"},
            "license_wise_companies": [{
                "company_id": company_id, "company_name": f"Company {company_id}",
                "purchase_total": purchase, "sale_total": sale,
                "current_balance": Decimal("10.00"),
                "profit_loss": sale - purchase,
                "profit_state": "PROFIT" if sale > purchase else "LOSS",
            }],
        }

    def test_company_groups_publish_renderer_ready_financial_values(self):
        dataset = {
            "license_id": 1,
            "license_number": "0310833996",
            "license_type": "DFIA",
            "license_date": date(2025, 1, 1),
            "first_purchase_date": date(2025, 2, 1),
            "sion_norms": "E5",
            "has_purchase_bill": True,
            "summary": {"current_balance": Decimal("28.77"), "balance_currency": "USD"},
            "license_wise_companies": [{
                "company_id": 881,
                "company_name": "LABDHI GLOBAL LLP",
                "purchase_total": Decimal("4583719.00"),
                "sale_total": Decimal("6524056.00"),
                "current_balance": Decimal("28.77"),
                "profit_loss": Decimal("1940337.00"),
                "profit_state": "PROFIT",
            }],
        }

        groups = CanonicalLedgerService.build_collection_company_groups([dataset])

        self.assertEqual(len(groups), 1)
        group = groups[0]
        row = group["licenses"][0]
        self.assertEqual(row["purchase_bill_inr"], Decimal("4583719.00"))
        self.assertEqual(row["sale_bill_inr"], Decimal("6524056.00"))
        self.assertEqual(row["profit_loss_inr"], Decimal("1940337.00"))
        self.assertEqual(row["current_balance"], Decimal("28.77"))
        self.assertEqual(row["sion_norms"], "E5")
        self.assertEqual(group["total_profit_loss_inr"], Decimal("1940337.00"))

    def test_group_profit_is_signed_sale_bill_minus_purchase_bill(self):
        group = {
            "company_id": 881,
            "company_name": "LABDHI GLOBAL LLP",
            "purchase_total": Decimal("1700076.00"),
            "sale_total": Decimal("1519243.00"),
            "current_balance": Decimal("149999.96"),
            "profit_loss": Decimal("-180833.00"),
            "profit_state": "LOSS",
        }
        dataset = {
            "license_id": 2, "license_number": "0311055282", "license_type": "DFIA",
            "license_date": None, "first_purchase_date": None, "sion_norms": "",
            "has_purchase_bill": True,
            "summary": {"current_balance": Decimal("149999.96"), "balance_currency": "USD"},
            "license_wise_companies": [group],
        }
        row = CanonicalLedgerService.build_collection_company_groups([dataset])[0]["licenses"][0]
        self.assertEqual(row["profit_loss_inr"], row["sale_bill_inr"] - row["purchase_bill_inr"])
        self.assertEqual(row["profit_state"], "LOSS")

    def test_company_sion_groups_are_natural_ordered_and_reconcile(self):
        datasets = [
            self._dataset(1, "E132", "10", "20"),
            self._dataset(2, "E5", "30", "50"),
            self._dataset(3, "E1", "5", "8"),
            self._dataset(4, "PP", "7", "3"),
            self._dataset(5, "", "2", "2"),
        ]
        company = CanonicalLedgerService.build_collection_company_groups(datasets)[0]

        self.assertEqual(
            [group["sion_label"] for group in company["sion_groups"]],
            ["E1", "E5", "E132", "PP", "N/A / EMPTY"],
        )
        self.assertEqual(sum(group["license_count"] for group in company["sion_groups"]), 5)
        self.assertEqual(
            sum(group["total_purchase_bill_inr"] for group in company["sion_groups"]),
            company["total_purchase_bill_inr"],
        )
        self.assertEqual(
            sum(group["total_profit_loss_inr"] for group in company["sion_groups"]),
            company["total_profit_loss_inr"],
        )

    def test_multi_sion_license_uses_one_composite_group_without_duplicate_amounts(self):
        dataset = self._dataset(1, "E132, E5, E5", "100", "140")
        company = CanonicalLedgerService.build_collection_company_groups([dataset])[0]

        self.assertEqual(len(company["sion_groups"]), 1)
        group = company["sion_groups"][0]
        self.assertEqual(group["sion_norm"], "E5, E132")
        self.assertEqual(group["license_count"], 1)
        self.assertEqual(group["total_purchase_bill_inr"], Decimal("100.00"))
        self.assertEqual(group["total_sale_bill_inr"], Decimal("140.00"))
        self.assertEqual(len(group["licenses"]), 1)

    def test_grand_total_reconciles_company_groups(self):
        groups = CanonicalLedgerService.build_collection_company_groups([
            self._dataset(1, "E1", "10", "15", company_id=1),
            self._dataset(2, "E5", "20", "18", company_id=2),
        ])
        total = CanonicalLedgerService.build_collection_grand_total(groups)

        self.assertEqual(total["license_count"], 2)
        self.assertEqual(total["total_purchase_bill_inr"], Decimal("30.00"))
        self.assertEqual(total["total_sale_bill_inr"], Decimal("33.00"))
        self.assertEqual(total["total_profit_loss_inr"], Decimal("3.00"))
