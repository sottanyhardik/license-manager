"""
Dashboard BOE and invoice sections: the single-section endpoint (`?section=`), role gates,
failure isolation, and invoice aggregation against real settlement states.
Contract: docs/09-module-implementation/dashboard.md §4.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.license.services import dashboard_summary as summary
from apps.trade.models import LicenseTrade, LicenseTradePayment

from .test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


def _scope(**kwargs):
    return summary.DashboardScope(as_of=date.today(), **kwargs)


class DashboardSectionMixin(LicenseBalanceLedgerFixtureMixin):
    def setUp(self):
        cache.clear()
        self.superuser = self.make_superuser()
        self.api = APIClient()
        self.api.force_authenticate(user=self.superuser)

    def tearDown(self):
        cache.clear()

    def user_with_roles(self, *role_codes):
        user = self.make_plain_user()
        for code in role_codes:
            user.groups.add(Group.objects.get_or_create(name=code)[0])
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def section(self, name, client=None, **params):
        return (client or self.api).get(reverse("license:dashboard"), {"section": name, **params})

    def make_trade(self, company, *, direction, total, paid=None, number=None, invoice_date=None, party=None):
        trade = LicenseTrade.objects.create(
            direction=direction,
            from_company=company if direction in (LicenseTrade.DIR_SALE, LicenseTrade.DIR_COMMISSION_SALE) else party,
            to_company=party if direction in (LicenseTrade.DIR_SALE, LicenseTrade.DIR_COMMISSION_SALE) else company,
            invoice_number=number or f"INV-{uuid.uuid4().hex[:8]}",
            invoice_date=invoice_date or date.today(),
        )
        LicenseTrade.objects.filter(pk=trade.pk).update(total_amount=Decimal(total))
        if paid is not None:
            LicenseTradePayment.objects.create(trade=trade, amount=Decimal(paid))
        return trade


class SingleSectionEndpointTests(DashboardSectionMixin, TestCase):
    def test_returns_meta_and_only_the_requested_section(self):
        body = self.section("boe_activity").json()

        self.assertEqual(set(body.keys()), {"meta", "boe_activity"})
        self.assertIsInstance(body["boe_activity"]["recent"], list)
        self.assertIsInstance(body["boe_activity"]["pending_mapping"], list)

    def test_full_payload_and_single_section_agree_for_the_same_data(self):
        company = self.make_company()
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="500.00", paid="200.00", party=self.make_company("Buyer"))

        full = self.api.get(reverse("license:dashboard")).json()
        single = self.section("invoice_activity").json()

        self.assertEqual(single["invoice_activity"], full["invoice_activity"])

    def test_unknown_section_is_rejected_with_400(self):
        response = self.section("not_a_section")

        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be requested on its own", response.json()["error"])

    def test_licence_sections_are_not_requestable_on_their_own(self):
        self.assertEqual(self.section("licence_portfolio").status_code, 400)

    def test_a_role_without_the_grant_gets_403_not_an_empty_section(self):
        client = self.user_with_roles("ALLOTMENT_VIEWER")

        response = self.section("invoice_activity", client=client)

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("invoice_activity", response.json())

    def test_a_builder_failure_is_a_section_error_and_the_response_is_200(self):
        with patch("apps.license.services.dashboard_summary.build_invoice_activity", side_effect=RuntimeError("boom")):
            response = self.section("invoice_activity")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["invoice_activity"], {"error": "Dashboard section 'invoice_activity' could not be loaded"})

    def test_single_section_responses_are_never_served_from_cache(self):
        self.section("boe_activity")
        second = self.section("boe_activity").json()

        self.assertFalse(second["meta"]["cached"])

    def test_scope_parameters_still_apply_to_a_single_section(self):
        other = self.make_company("Other")
        self.make_trade(other, direction=LicenseTrade.DIR_SALE, total="900.00", party=self.make_company("Buyer 2"))

        scoped = self.section("invoice_activity", company_id=self.make_company("Scoped").pk).json()

        self.assertEqual(scoped["meta"]["scope"]["company_name"], "Scoped")
        self.assertEqual(scoped["invoice_activity"]["total"], 0)


class BoeSectionTests(DashboardSectionMixin, TestCase):
    def test_boe_rows_are_a_plain_list_with_the_contract_fields_and_no_pagination_wrapper(self):
        company = self.make_company()
        self.make_boe(company, number="BOE-PLAIN-1")
        boe = self.section("boe_activity").json()["boe_activity"]

        self.assertNotIn("results", boe)
        row = boe["recent"][0]
        self.assertEqual(
            set(row.keys()),
            {"id", "bill_of_entry_number", "bill_of_entry_date", "company_name", "invoice_no",
             "modified_on", "allotment_links", "licence_items", "mapping_status"},
        )

    def test_a_boe_without_licence_rows_is_pending_licence_mapping(self):
        company = self.make_company()
        self.make_boe(company, number="BOE-UNMAPPED")
        boe = self.section("boe_activity").json()["boe_activity"]

        self.assertEqual(boe["pending_licence_mapping"], 1)
        self.assertEqual(boe["pending_mapping"][0]["mapping_status"], "pending_licence_mapping")

    def test_an_empty_boe_list_is_a_valid_empty_section(self):
        boe = self.section("boe_activity").json()["boe_activity"]

        self.assertEqual(boe["total"], 0)
        self.assertEqual(boe["recent"], [])
        self.assertEqual(boe["pending_mapping"], [])


class InvoiceAggregationTests(DashboardSectionMixin, TestCase):
    def test_each_settlement_state_is_counted_once_with_the_right_outstanding(self):
        company = self.make_company()
        buyer = self.make_company("Buyer")
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="1000.00", paid="1000.00", party=buyer)  # paid
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="1000.00", paid="400.00", party=buyer)   # partial
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="1000.00", party=buyer)                  # unpaid
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="1000.00", paid="1200.00", party=buyer)  # overpaid

        invoices = summary.build_invoice_activity(_scope(company=company))

        self.assertEqual(invoices["total"], 4)
        self.assertEqual((invoices["paid"], invoices["partially_paid"], invoices["unpaid"]), (2, 1, 1))
        self.assertEqual(invoices["open"], 2)
        self.assertEqual(invoices["outstanding_inr"], "1600.00", "overpayment must not net against other invoices")
        self.assertEqual(invoices["paid_inr"], "2600.00", "1000 + 400 + 0 + 1200 (overpaid settles all of its total)")
        self.assertEqual(invoices["total_amount_inr"], "4000.00")

    def test_sale_and_purchase_outstanding_are_split_by_direction(self):
        company = self.make_company()
        supplier = self.make_company("Supplier")
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="700.00", party=self.make_company("Buyer 3"))
        self.make_trade(company, direction=LicenseTrade.DIR_PURCHASE, total="300.00", paid="100.00", party=supplier)

        invoices = summary.build_invoice_activity(_scope(company=company))

        self.assertEqual(invoices["by_direction"]["sale"], {"total": 1, "outstanding_inr": "700.00"})
        self.assertEqual(invoices["by_direction"]["purchase"], {"total": 1, "outstanding_inr": "200.00"})

    def test_a_blank_invoice_number_is_not_an_invoice(self):
        company = self.make_company()
        LicenseTrade.objects.create(direction=LicenseTrade.DIR_SALE, from_company=company, invoice_number="")

        self.assertEqual(summary.build_invoice_activity(_scope(company=company))["total"], 0)

    def test_invoice_date_range_bounds_the_counts(self):
        company = self.make_company()
        buyer = self.make_company("Buyer 4")
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="100.00", party=buyer)
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="100.00", party=buyer,
                        invoice_date=date.today() - timedelta(days=400))

        invoices = summary.build_invoice_activity(_scope(company=company, date_from=date.today() - timedelta(days=30)))

        self.assertEqual(invoices["total"], 1)

    def test_an_empty_invoice_list_is_a_valid_empty_section(self):
        invoices = self.section("invoice_activity").json()["invoice_activity"]

        self.assertEqual(invoices["total"], 0)
        self.assertEqual(invoices["recent"], [])
        self.assertEqual(invoices["outstanding_inr"], "0.00")
        self.assertEqual(invoices["not_tracked"], ["draft", "pending", "confirmed", "posted"])

    def test_recent_rows_carry_the_customer_and_the_settlement_status(self):
        company = self.make_company()
        buyer = self.make_company("Named Buyer")
        self.make_trade(company, direction=LicenseTrade.DIR_SALE, total="250.00", paid="50.00", party=buyer)

        row = summary.build_invoice_activity(_scope(company=company))["recent"][0]

        self.assertEqual(row["party_name"], "Named Buyer")
        self.assertEqual(row["direction"], "sale")
        self.assertEqual(row["status"], "partially_paid")
        self.assertEqual(row["outstanding_inr"], "200.00")

    def test_invoice_roles_see_the_section_and_other_roles_do_not(self):
        self.make_trade(self.make_company(), direction=LicenseTrade.DIR_SALE, total="10.00")

        self.assertEqual(self.section("invoice_activity", client=self.user_with_roles("TRADE_VIEWER")).status_code, 200)
        self.assertEqual(self.section("invoice_activity", client=self.user_with_roles("BOE_VIEWER")).status_code, 403)
