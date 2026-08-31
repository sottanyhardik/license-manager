from datetime import date
from decimal import Decimal
import json

import pytest

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.license_invoice_relations import (
    get_final_party_sales_invoices,
    get_main_purchase_invoices,
)
from apps.trade.models import LicenseTrade, LicenseTradeLine


@pytest.mark.django_db
class TestLicenseInvoiceRelations:
    def setup_method(self):
        self.seller = CompanyModel.objects.create(name="Seller Ltd", iec="9000000001")
        self.buyer = CompanyModel.objects.create(name="Buyer Ltd", iec="9000000002")
        self.licence = LicenseDetailsModel.objects.create(license_number="RELATION-001")
        self.item = LicenseImportItemsModel.objects.create(
            license=self.licence, serial_number=1, quantity=Decimal("10.000"), cif_fc=Decimal("100.00"),
        )

    def _trade(self, direction, number, **kwargs):
        trade = LicenseTrade.objects.create(
            direction=direction, from_company=self.seller, to_company=self.buyer,
            invoice_number=number, invoice_date=date(2026, 4, 1), **kwargs,
        )
        LicenseTradeLine.objects.create(trade=trade, sr_number=self.item, qty_kg=Decimal("1.000"))
        return trade

    def test_purchase_selection_uses_direct_line_and_explicit_interlink(self):
        main = self._trade(LicenseTrade.DIR_PURCHASE, "PUR/0007")
        paired = self._trade(LicenseTrade.DIR_PURCHASE, "PUR/0008", linked_trade=main)

        candidates = get_main_purchase_invoices(self.licence)

        by_id = {row["invoice_id"]: row for row in candidates}
        assert by_id[main.pk]["selection_result"] == "INCLUDED"
        assert by_id[main.pk]["invoice_number"] == "PUR/0007"
        assert by_id[paired.pk]["selection_result"] == "EXCLUDED"
        assert by_id[paired.pk]["is_interlinked"] is True

    def test_only_explicitly_classified_terminal_sales_are_included(self):
        final_sale = self._trade(
            LicenseTrade.DIR_SALE, "SALE/2026-27/0003",
            final_party_status=LicenseTrade.FINAL_PARTY_FINAL, final_party=self.buyer,
            final_party_resolution_note="Allotment settlement record AL-77",
            final_party_classification_provenance="AUTHORISED_RESOLUTION_AL-77",
        )
        intermediate = self._trade(
            LicenseTrade.DIR_SALE, "SALE/2026-27/0004",
            final_party_status=LicenseTrade.FINAL_PARTY_INTERMEDIATE,
        )
        unknown = self._trade(LicenseTrade.DIR_SALE, "SALE/2026-27/0005")

        candidates = get_final_party_sales_invoices(self.licence)
        by_id = {row["invoice_id"]: row for row in candidates}
        assert by_id[final_sale.pk]["selection_result"] == "INCLUDED"
        assert by_id[final_sale.pk]["is_final_party"] is True
        assert by_id[final_sale.pk]["final_party_name"] == "Buyer Ltd"
        assert by_id[final_sale.pk]["invoice_number"] == "SALE/2026-27/0003"
        assert by_id[intermediate.pk]["selection_result"] == "EXCLUDED"
        # A missing relationship/classification is not evidence that the
        # buyer is terminal.  This protects historic intermediate transfers.
        assert by_id[unknown.pk]["selection_result"] == "EXCLUDED"
        assert by_id[unknown.pk]["selection_reason"] == "final-party classification required"

    def test_final_party_classification_must_name_the_invoice_buyer(self):
        other_party = CompanyModel.objects.create(name="Other buyer", iec="9000000003")
        invalid = self._trade(
            LicenseTrade.DIR_SALE, "SALE/2026-27/0006",
            final_party_status=LicenseTrade.FINAL_PARTY_FINAL,
            final_party=other_party,
            final_party_classification_provenance="AUTHORISED_RESOLUTION_BAD",
        )

        candidate = {row["invoice_id"]: row for row in get_final_party_sales_invoices(self.licence)}[invalid.pk]
        assert candidate["selection_result"] == "EXCLUDED"
        assert candidate["selection_reason"] == "final-party classification does not match invoice buyer"

    def test_one_way_reverse_link_is_still_interlinked_and_never_terminal(self):
        apparent_terminal = self._trade(
            LicenseTrade.DIR_SALE, "SALE/2026-27/0007",
            final_party_status=LicenseTrade.FINAL_PARTY_FINAL,
            final_party=self.buyer,
            final_party_classification_provenance="AUTHORISED_RESOLUTION",
        )
        self._trade(LicenseTrade.DIR_SALE, "SALE/2026-27/0008", linked_trade=apparent_terminal)

        candidate = {row["invoice_id"]: row for row in get_final_party_sales_invoices(self.licence)}[apparent_terminal.pk]
        assert candidate["selection_result"] == "EXCLUDED"
        assert candidate["selection_reason"] == "explicit paired/copy relation"
        assert candidate["is_interlinked"] is True

    def test_candidates_are_json_safe_for_durable_package_manifest(self):
        purchase = self._trade(LicenseTrade.DIR_PURCHASE, "PUR/2026-27/0009")
        sale = self._trade(
            LicenseTrade.DIR_SALE, "SALE/2026-27/0010",
            final_party_status=LicenseTrade.FINAL_PARTY_FINAL,
            final_party=self.buyer,
            final_party_classification_provenance="AUTHORISED_RESOLUTION",
        )
        candidates = get_main_purchase_invoices(self.licence) + get_final_party_sales_invoices(self.licence)
        by_id = {candidate["invoice_id"]: candidate for candidate in candidates}
        assert by_id[purchase.pk]["invoice_date"] == "2026-04-01"
        assert by_id[sale.pk]["invoice_date"] == "2026-04-01"
        json.dumps({"purchase_candidates": candidates, "sales_candidates": candidates})
