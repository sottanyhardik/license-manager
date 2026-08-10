"""BL-LIFECYCLE-01 regression coverage for final SALE quantity consumption."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.balance_calculator import ItemBalanceCalculator
from apps.trade.models import LicenseTrade, LicenseTradeLine
from apps.trade.serializers import LicenseTradeSerializer


class SaleTradeQuantityConsumptionTests(TestCase):
    def setUp(self):
        self.company = CompanyModel.objects.create(name='Sale Qty Exporter', iec=str(uuid4().int)[:10])
        self.license = LicenseDetailsModel.objects.create(
            license_number='03' + str(uuid4().int)[:8],
            license_date=date(2025, 1, 1),
            license_expiry_date=date(2028, 1, 1),
            exporter=self.company,
        )
        self.item = LicenseImportItemsModel.objects.create(
            license=self.license,
            serial_number=1,
            description='Sale quantity item',
            quantity=Decimal('100.000'),
            available_quantity=Decimal('100.000'),
        )

    def _sale(self):
        return LicenseTrade.objects.create(direction=LicenseTrade.DIR_SALE, from_company=self.company)

    def _line(self, trade, qty):
        return LicenseTradeLine.objects.create(
            trade=trade,
            sr_number=self.item,
            mode=LicenseTradeLine.MODE_QTY,
            qty_kg=Decimal(qty),
        )

    def _boe_row(self, qty):
        boe = BillOfEntryModel.objects.create(
            company=self.company,
            bill_of_entry_number=str(uuid4().int)[:9],
            bill_of_entry_date=date(2026, 1, 1),
        )
        RowDetails.objects.create(
            bill_of_entry=boe,
            sr_number=self.item,
            transaction_type=DEBIT,
            qty=Decimal(qty),
            cif_fc=Decimal('0'),
            cif_inr=Decimal('0'),
        )
        return boe

    def test_direct_sale_consumes_item_quantity_and_updates_stored_balance(self):
        self._line(self._sale(), '30.000')

        self.item.refresh_from_db()
        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.item), Decimal('70.000'))
        self.assertEqual(self.item.available_quantity, Decimal('70.000'))

    def test_sale_with_boe_is_debited_once_by_the_boe(self):
        boe = self._boe_row('30.000')
        trade = self._sale()
        trade.boes.add(boe)
        self._line(trade, '30.000')

        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.item), Decimal('70.000'))

    def test_multiple_direct_sale_lines_consume_cumulatively(self):
        trade = self._sale()
        self._line(trade, '30.000')
        self._line(trade, '20.000')

        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.item), Decimal('50.000'))

    def test_later_boe_association_replaces_not_duplicates_direct_sale_debit(self):
        trade = self._sale()
        self._line(trade, '30.000')
        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.item), Decimal('70.000'))

        boe = self._boe_row('30.000')
        trade.boes.add(boe)
        self.item.refresh_from_db()

        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.item), Decimal('70.000'))
        self.assertEqual(self.item.available_quantity, Decimal('70.000'))

    def test_formal_invoice_boe_allocation_replaces_direct_sale_quantity(self):
        from apps.reconciliation.services.allocation_service import create_invoice_boe_allocation

        trade = self._sale()
        line = self._line(trade, '30.000')
        row_boe = self._boe_row('30.000')
        row = row_boe.item_details.get()
        create_invoice_boe_allocation(
            line, row, qty=Decimal('30.000'), cif_fc=Decimal('0'), cif_inr=Decimal('0'), user=None,
        )

        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.item), Decimal('70.000'))

    def test_direct_sale_quantity_over_available_is_rejected(self):
        serializer = LicenseTradeSerializer(data={
            'direction': LicenseTrade.DIR_SALE,
            'from_company': self.company.pk,
            'lines': [{
                'sr_number': self.item.pk,
                'mode': LicenseTradeLine.MODE_QTY,
                'qty_kg': '100.001',
            }],
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(ValidationError):
            serializer.save()
