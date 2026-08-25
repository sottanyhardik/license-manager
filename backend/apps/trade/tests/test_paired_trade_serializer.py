from datetime import date
from decimal import Decimal

import pytest

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.trade.serializers import LicenseTradeSerializer


@pytest.mark.django_db
class TestPairedTradeCifValidation:
    """A paired transfer must not be blocked by its source-row CIF ledger."""

    def _payload(self, *, source_row_id, seller_id, buyer_id, auto_create_paired):
        return {
            "direction": "PURCHASE",
            "license_type": "DFIA",
            "from_company": seller_id,
            "to_company": buyer_id,
            "invoice_number": "PAIR/2026-27/0001",
            "invoice_date": date(2026, 8, 25).isoformat(),
            "auto_create_paired": auto_create_paired,
            "lines": [{
                "sr_number": source_row_id,
                "mode": "QTY",
                "qty_kg": "2.000",
                "cif_fc": "101.00",
                "amount_inr": "2.00",
            }],
        }

    def test_auto_paired_request_bypasses_individual_source_cif_ceiling(self):
        seller = CompanyModel.objects.create(name="Pair seller", iec="0000000001")
        buyer = CompanyModel.objects.create(name="Pair buyer", iec="0000000002")
        licence = LicenseDetailsModel.objects.create(
            license_number="PAIR-CIF-ALLOW",
            individual_item_cif_override=True,
        )
        item = LicenseImportItemsModel.objects.create(
            license=licence,
            serial_number=1,
            quantity=Decimal("2.000"),
            available_quantity=Decimal("2.000"),
            cif_fc=Decimal("100.00"),
        )

        serializer = LicenseTradeSerializer(data=self._payload(
            source_row_id=item.pk, seller_id=seller.pk, buyer_id=buyer.pk,
            auto_create_paired=True,
        ))

        assert serializer.is_valid(), serializer.errors

    def test_standalone_request_keeps_individual_source_cif_ceiling(self):
        seller = CompanyModel.objects.create(name="Standalone seller", iec="0000000003")
        buyer = CompanyModel.objects.create(name="Standalone buyer", iec="0000000004")
        licence = LicenseDetailsModel.objects.create(
            license_number="PAIR-CIF-BLOCK",
            individual_item_cif_override=True,
        )
        item = LicenseImportItemsModel.objects.create(
            license=licence,
            serial_number=1,
            quantity=Decimal("2.000"),
            available_quantity=Decimal("2.000"),
            cif_fc=Decimal("100.00"),
        )

        serializer = LicenseTradeSerializer(data=self._payload(
            source_row_id=item.pk, seller_id=seller.pk, buyer_id=buyer.pk,
            auto_create_paired=False,
        ))

        assert not serializer.is_valid()
        assert "cif_fc" in serializer.errors["lines"][0]
