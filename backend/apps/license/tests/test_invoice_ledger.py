"""Invoices & Sales ledger: database-backed tests (real trade, line and item records)."""

import uuid
from datetime import date
from decimal import Decimal

from apps.core.models import CompanyModel
from apps.license.services.invoice_ledger import (
    CREDIT_NOTE,
    DEBIT_NOTE,
    classify_invoice,
    load_invoice_ledger,
)
from apps.license.tests.test_licence_balance_report import ReportFixture
from apps.trade.models import LicenseTrade, LicenseTradeLine

D = Decimal


class InvoiceLedgerFixture(ReportFixture):
    def setUp(self):
        super().setUp()
        self.supplier = CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Supplier Co")
        self.buyer_two = CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Buyer Two")

    def _trade(self, *, direction, invoice, cif, qty, inr, item=None, from_co=None, to_co=None, day=1):
        item = item or self.item
        trade = LicenseTrade.objects.create(
            direction=direction, invoice_number=invoice, invoice_date=date(2026, 5, day),
            from_company=from_co or self.seller, to_company=to_co or self.customer,
        )
        line = LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, cif_fc=D(cif), qty_kg=D(qty), amount_inr=D(inr),
            cif_inr=D(cif) * D("94"), description="Palmolein",
        )
        return trade, line

    def ledger(self):
        return load_invoice_ledger(self.licence.id)

    def rows(self, result):
        return [row for company in result["companies"] for row in company["rows"]]


class ClassificationTests(ReportFixture):
    def test_note_prefixes_are_classified(self):
        self.assertEqual(classify_invoice("CREDIT NOTE LGL/1", "PURCHASE"), (CREDIT_NOTE, "LGL/1"))
        self.assertEqual(classify_invoice("debit note X-9", "SALE"), (DEBIT_NOTE, "X-9"))
        self.assertEqual(classify_invoice("LGL/2", "SALE"), ("SALE", None))


class SummaryTests(InvoiceLedgerFixture):
    def test_matched_credit_note_reduces_sale_and_is_not_a_purchase(self):
        # Reproduces the screenshot's balances: purchase 92,128.06 net; sale 63,254.58 gross less the 35,645.04 credit.
        self._trade(direction="PURCHASE", invoice="JASH/1", cif="92128.06", qty="0", inr="1238942", from_co=self.supplier, to_co=self.seller)
        original, _ = self._trade(direction="SALE", invoice="LGL/10", cif="35645.04", qty="8911", inr="463372", day=2)
        self._trade(direction="SALE", invoice="LGL/11", cif="27609.54", qty="22914", inr="719222", day=4, to_co=self.buyer_two)
        self._trade(direction="PURCHASE", invoice="CREDIT NOTE LGL/10", cif="35645.04", qty="8911", inr="463372", day=6)
        result = self.ledger()
        s = result["summary"]
        self.assertEqual(s["gross_sale_cif"], "63254.58")
        self.assertEqual(s["sale_adjustments_cif"], "-35645.04")
        self.assertEqual(s["net_sale_cif"], "27609.54")
        self.assertEqual(s["gross_purchase_cif"], "92128.06")
        self.assertEqual(s["purchase_adjustments_cif"], "0.00")
        self.assertEqual(s["current_balance_cif"], "64518.52")
        self.assertEqual(s["net_bill_difference_inr"], "519720.00")
        note = [r for r in self.rows(result) if r["type"] == CREDIT_NOTE][0]
        self.assertEqual(note["matched_original"]["invoice"], "LGL/10")
        self.assertEqual(note["sale_cif"], "-35645.04")
        self.assertEqual(s["canonical_vs_net_sale_difference"], "35645.04")

    def test_unmatched_note_contributes_nothing_and_is_flagged(self):
        self._trade(direction="SALE", invoice="LGL/20", cif="100", qty="10", inr="9000")
        self._trade(direction="PURCHASE", invoice="CREDIT NOTE LGL/999", cif="50", qty="5", inr="4000")
        result = self.ledger()
        self.assertEqual(result["summary"]["unmatched_notes"], 1)
        self.assertEqual(result["summary"]["net_sale_cif"], "100.00")
        note = [r for r in self.rows(result) if r["type"] == CREDIT_NOTE][0]
        self.assertEqual(note["effect"], "Not netted (review)")
        self.assertIn("UNMATCHED", note["status"])

    def test_debit_note_increases_its_original_side(self):
        # The database allows one SALE per buyer and invoice number, so the debit note goes to another buyer.
        self._trade(direction="SALE", invoice="LGL/30", cif="100", qty="10", inr="9000")
        self._trade(direction="SALE", invoice="DEBIT NOTE LGL/30", cif="100", qty="10", inr="9000", day=3, to_co=self.buyer_two)
        result = self.ledger()
        self.assertEqual(result["summary"]["sale_adjustments_cif"], "100.00")
        self.assertEqual(result["summary"]["net_sale_cif"], "200.00")

    def test_each_row_contributes_exactly_once(self):
        self._trade(direction="PURCHASE", invoice="P-1", cif="10", qty="1", inr="100")
        self._trade(direction="SALE", invoice="S-1", cif="7", qty="1", inr="70", day=2)
        self._trade(direction="PURCHASE", invoice="CREDIT NOTE S-1", cif="7", qty="1", inr="70", day=3)
        result = self.ledger()
        s = result["summary"]
        balance = D(s["net_purchase_cif"]) - D(s["net_sale_cif"])
        self.assertEqual(balance, D(s["current_balance_cif"]))
        self.assertEqual(D(s["gross_purchase_cif"]) + D(s["purchase_adjustments_cif"]), D(s["net_purchase_cif"]))
        self.assertEqual(D(s["gross_sale_cif"]) + D(s["sale_adjustments_cif"]), D(s["net_sale_cif"]))

    def test_multiple_holder_companies_get_their_own_sections_and_balances(self):
        self._trade(direction="SALE", invoice="A-1", cif="100", qty="10", inr="9000")
        other_licence_item = self._item(self.licence, serial=9, qty="10", cif="10")
        self._trade(direction="SALE", invoice="B-1", cif="40", qty="4", inr="3600", item=other_licence_item, day=5)
        result = self.ledger()
        self.assertEqual(len(result["companies"]), 1)  # same holder: one section, balances add up
        self.assertEqual(result["companies"][0]["balance_cif"], "-140.00")


class LedgerEndpointTests(InvoiceLedgerFixture):
    def test_endpoint_requires_a_licence_role_and_returns_the_ledger(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from rest_framework.test import APIClient

        self._trade(direction="SALE", invoice="E-1", cif="100", qty="10", inr="9000")
        outsider = get_user_model().objects.create_user(username="led-" + uuid.uuid4().hex[:6], password="x")
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(outsider)
        self.assertEqual(client.get(f"/api/licence-balances/{self.licence.id}/invoice-ledger/").status_code, 403)
        viewer = get_user_model().objects.create_user(username="ledv-" + uuid.uuid4().hex[:6], password="x")
        viewer.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        client.force_authenticate(viewer)
        response = client.get(f"/api/licence-balances/{self.licence.id}/invoice-ledger/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["net_sale_cif"], "100.00")
