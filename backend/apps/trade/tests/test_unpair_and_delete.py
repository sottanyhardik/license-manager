# trade/tests/test_unpair_and_delete.py
"""Audited unpair-and-delete of one side of a Sale<->Purchase pair."""

import itertools
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.trade.services.trade_service import (
    PairDeletionError,
    copy_sale_to_purchase,
    unpair_and_delete_trade,
)

_iec_counter = itertools.count(1000)


def _unique_iec() -> str:
    return f"{next(_iec_counter):010d}"


class UnpairAndDeleteTests(TestCase):
    def setUp(self):
        from apps.core.models import CompanyModel
        from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
        from apps.trade.models import LicenseTrade, LicenseTradeLine
        self.seller = CompanyModel.objects.create(name='Labdhi Mercantile LLP', iec=_unique_iec())
        self.buyer = CompanyModel.objects.create(name='Labdhi Global LLP', iec=_unique_iec())
        self.license = LicenseDetailsModel.objects.create(
            license_number='0311049999', exporter=self.seller,
            license_date=date(2026, 8, 3), license_expiry_date=date(2027, 8, 3),
        )
        self.item = LicenseImportItemsModel.objects.create(license=self.license, serial_number=1, description='DFIA item')
        self.sale = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, from_company=self.seller, to_company=self.buyer,
            invoice_number='LGL/2026-27/0091', invoice_date=date(2026, 10, 5),
        )
        LicenseTradeLine.objects.create(
            trade=self.sale, sr_number=self.item, description='DFIA item', mode=LicenseTradeLine.MODE_CIF_INR,
            qty_kg=Decimal('2.0000'), cif_fc=Decimal('218076.00'), exc_rate=Decimal('1.0000'),
            cif_inr=Decimal('218076.00'), pct=Decimal('100.000'), amount_inr=Decimal('218076.00'),
        )
        _, self.purchase, _ = copy_sale_to_purchase(self.sale.id)

    def test_unpair_deletes_purchase_and_keeps_sale_standalone(self):
        from apps.trade.models import LicenseTrade, LicenseTradeLine, TradePairAudit
        purchase_id = self.purchase.id
        purchase_invoice = self.purchase.invoice_number
        total_before = self.sale.total_amount

        deleted_id, kept_id, audit_id = unpair_and_delete_trade(purchase_id)

        self.assertEqual((deleted_id, kept_id), (purchase_id, self.sale.id))
        self.assertFalse(LicenseTrade.objects.filter(pk=purchase_id).exists())
        self.sale.refresh_from_db()
        self.assertIsNone(self.sale.counterpart_id)
        self.assertIsNone(self.sale.transaction_pair_uuid)
        self.assertEqual(self.sale.total_amount, total_before)
        sale_line = LicenseTradeLine.objects.get(trade=self.sale)
        self.assertIsNone(sale_line.counterpart_line_id)
        self.assertIsNone(sale_line.transaction_pair_uuid)

        audit = TradePairAudit.objects.get(pk=audit_id)
        self.assertEqual(audit.action, 'UNPAIRED_DELETED')
        self.assertEqual(audit.source_trade_id, purchase_id)
        self.assertEqual(audit.counterpart_trade_id, self.sale.id)
        self.assertEqual(audit.detail['deleted']['invoice_number'], purchase_invoice)
        self.assertEqual(audit.detail['kept']['invoice_number'], 'LGL/2026-27/0091')

        # The original COPIED audit row survives the delete, with its FK nulled.
        copied = TradePairAudit.objects.get(action='COPIED')
        self.assertIsNone(copied.counterpart_id)
        self.assertEqual(copied.counterpart_trade_id, purchase_id)
        self.assertEqual(copied.source_id, self.sale.id)

    def test_unpair_deleting_the_sale_side_keeps_the_purchase(self):
        from apps.trade.models import LicenseTrade, LicenseTradeLine
        sale_id = self.sale.id

        deleted_id, kept_id, _ = unpair_and_delete_trade(sale_id)

        self.assertEqual((deleted_id, kept_id), (sale_id, self.purchase.id))
        self.assertFalse(LicenseTrade.objects.filter(pk=sale_id).exists())
        self.purchase.refresh_from_db()
        self.assertIsNone(self.purchase.counterpart_id)
        self.assertIsNone(self.purchase.copied_from_id)
        self.assertEqual(LicenseTradeLine.objects.filter(trade=self.purchase).count(), 1)

    def test_unpair_of_unpaired_trade_is_refused(self):
        from apps.trade.models import LicenseTrade
        standalone = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, from_company=self.seller, to_company=self.buyer,
            invoice_number='LGL/2026-27/0092', invoice_date=date(2026, 10, 6),
        )
        with self.assertRaises(PairDeletionError):
            unpair_and_delete_trade(standalone.id)
        self.assertTrue(LicenseTrade.objects.filter(pk=standalone.id).exists())

    def test_plain_delete_of_paired_trade_is_still_blocked(self):
        from django.db.models import ProtectedError
        from apps.trade.models import LicenseTrade
        # Django's PROTECT on LicenseTrade.counterpart fires during collection,
        # before the pre_delete ValidationError guard is reached.
        with self.assertRaises(ProtectedError):
            LicenseTrade.objects.get(pk=self.purchase.id).delete()
        self.assertTrue(LicenseTrade.objects.filter(pk=self.purchase.id).exists())


class UnpairAndDeleteEndpointTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.core.models import CompanyModel
        from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
        from apps.trade.models import LicenseTrade, LicenseTradeLine
        seller = CompanyModel.objects.create(name='Labdhi Mercantile LLP', iec=_unique_iec())
        buyer = CompanyModel.objects.create(name='Labdhi Global LLP', iec=_unique_iec())
        license_ = LicenseDetailsModel.objects.create(
            license_number='0311048888', exporter=seller,
            license_date=date(2026, 8, 3), license_expiry_date=date(2027, 8, 3),
        )
        item = LicenseImportItemsModel.objects.create(license=license_, serial_number=1, description='DFIA item')
        sale = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, from_company=seller, to_company=buyer,
            invoice_number='LGL/2026-27/0093', invoice_date=date(2026, 10, 7),
        )
        LicenseTradeLine.objects.create(
            trade=sale, sr_number=item, description='DFIA item', mode=LicenseTradeLine.MODE_CIF_INR,
            qty_kg=Decimal('1.0000'), cif_fc=Decimal('1000.00'), exc_rate=Decimal('1.0000'),
            cif_inr=Decimal('1000.00'), pct=Decimal('100.000'), amount_inr=Decimal('1000.00'),
        )
        _, self.purchase, _ = copy_sale_to_purchase(sale.id)
        self.sale = sale
        user = get_user_model().objects.create_superuser(
            username='pair-admin', email='pair-admin@example.com', password='x-test-only-1'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=user)

    def test_endpoint_deletes_trade_and_reports_kept_counterpart(self):
        from apps.trade.models import LicenseTrade
        purchase_id = self.purchase.id
        response = self.client.post(f'/api/trades/{purchase_id}/unpair-and-delete/')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['kept_counterpart_id'], self.sale.id)
        self.assertFalse(LicenseTrade.objects.filter(pk=purchase_id).exists())
        self.assertTrue(LicenseTrade.objects.filter(pk=self.sale.id).exists())

    def test_endpoint_refuses_unpaired_trade_with_400(self):
        from apps.trade.models import LicenseTrade
        # Unpair first so the sale is standalone, then the endpoint must refuse it.
        unpair_and_delete_trade(self.purchase.id)
        response = self.client.post(f'/api/trades/{self.sale.id}/unpair-and-delete/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(LicenseTrade.objects.filter(pk=self.sale.id).exists())
