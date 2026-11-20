"""Query-budget characterization for the licence workspace endpoints.

AUDIT ARTEFACT (docs/modernization/backend-audit/09_LICENCE_WORKSPACE_PERF_AUDIT.md).
Every test PASSES on current code and pins the measured query count as an
upper bound.  They document scaling (1 row vs N rows); they do not assert that
the current behaviour is desirable.  Where an endpoint is known to be N+1 the
test asserts the *measured growth* so a future fix makes the test fail low
(tighten the bound then).  No production code is touched.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.trade.models import LicenseTrade, LicenseTradeLine, LicenseTradePayment

SMALL, LARGE = 1, 6


class WorkspaceFixture:
    """One licence carrying `n` import items, BOEs, allotments and trades."""

    @classmethod
    def make_user(cls):
        return get_user_model().objects.create_superuser(
            username=f"qb_{uuid.uuid4().hex[:8]}", password="x", email=f"{uuid.uuid4().hex[:6]}@example.com")

    @staticmethod
    def make_licence(n, company, other):
        lic = LicenseDetailsModel.objects.create(
            license_number="03" + str(uuid.uuid4().int)[:8],
            license_date=date.today(), license_expiry_date=date.today() + timedelta(days=365),
            exporter=company,
        )
        LicenseExportItemModel.objects.create(license=lic, description="exp", cif_fc=Decimal("100000"))
        for i in range(n):
            item = LicenseImportItemsModel.objects.create(
                license=lic, serial_number=i + 1, description=f"Item {i}",
                quantity=Decimal("1000"), available_quantity=Decimal("1000"), cif_fc=Decimal("1000"))
            boe = BillOfEntryModel.objects.create(
                company=company, bill_of_entry_number=str(uuid.uuid4().int)[:9],
                bill_of_entry_date=date.today() - timedelta(days=i), exchange_rate=Decimal("84.5"))
            RowDetails.objects.create(
                bill_of_entry=boe, sr_number=item, transaction_type=DEBIT,
                cif_fc=Decimal("10"), cif_inr=Decimal("845"), qty=Decimal("10"))
            alt = AllotmentModel.objects.create(company=company, item_name=f"Alt {i}", required_quantity=Decimal("5"))
            AllotmentItems.objects.create(
                item=item, allotment=alt, qty=Decimal("5"), cif_fc=Decimal("5"), cif_inr=Decimal("420"))
            for direction, frm, to in ((LicenseTrade.DIR_PURCHASE, other, company), (LicenseTrade.DIR_SALE, company, other)):
                trade = LicenseTrade.objects.create(
                    direction=direction, license_type="DFIA", from_company=frm, to_company=to,
                    invoice_number=f"INV-{uuid.uuid4().hex[:6]}", invoice_date=date.today(),
                    total_amount=Decimal("100"))
                LicenseTradeLine.objects.create(trade=trade, sr_number=item, cif_fc=Decimal("5"), amount_inr=Decimal("100"))
                LicenseTradePayment.objects.create(trade=trade, amount=Decimal("10"), date=date.today())
        return lic


class _Base(WorkspaceFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = cls.make_user()
        cls.company = CompanyModel.objects.create(iec="1234567890", name="Co")
        cls.other = CompanyModel.objects.create(iec="1234567891", name="Other")

    def count(self, url):
        cache.clear()
        client = APIClient()
        client.force_authenticate(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return len(ctx)

    def budget(self, path_tpl, small_cap, large_cap, *, flat=False):
        """Measure at SMALL and LARGE rows, assert upper bounds, print actuals."""
        small = self.make_licence(SMALL, self.company, self.other)
        large = self.make_licence(LARGE, self.company, self.other)
        q_small = self.count(path_tpl.format(id=small.id))
        q_large = self.count(path_tpl.format(id=large.id))
        print(f"BUDGET {path_tpl}: {SMALL} row={q_small}, {LARGE} rows={q_large}")
        self.assertLessEqual(q_small, small_cap, f"1-row cap {small_cap} exceeded: {q_small}")
        self.assertLessEqual(q_large, large_cap, f"{LARGE}-row cap {large_cap} exceeded: {q_large}")
        if flat:
            self.assertLessEqual(q_large, q_small + 1, "expected row-count independent query count")
        return q_small, q_large


class DetailEndpointBudgets(_Base):
    """Licence-scoped endpoints: 1 vs 6 import items / BOEs / allotments / 2 trades per item."""

    def test_retrieve_budget(self):
        # Proves: GET licenses/:id/ (also the ONLY source of documents) costs ~100 queries at
        # 1 row and grows ~2.8/row (plan_utilization_rows, aggregate_license_usage,
        # reconcile_license_plans, presentation service).  Pins the ceiling.
        self.budget("/api/licenses/{id}/", 106, 122)

    def test_overview_summary_budget(self):
        # Proves: overview-summary is row-count independent (flat) but fixed-cost ~47 queries,
        # almost all inside balance_snapshot.get_snapshot (not the 5 the docstring implies).
        self.budget("/api/licenses/{id}/overview-summary/", 50, 50, flat=True)

    def test_overview_items_budget(self):
        # Proves: legacy overview-items is 3 queries flat (good: stored columns only).
        self.budget("/api/licenses/{id}/overview-items/", 4, 4, flat=True)

    def test_overview_items_canonical_budget(self):
        # Proves: ?include_canonical=1 is N+1 (~3/row from project_effective_item_cif).
        self.budget("/api/licenses/{id}/overview-items/?include_canonical=1", 26, 42)

    def test_overview_boes_budget(self):
        # Proves: overview-boes is flat (grouped aggregate + one header query).
        self.budget("/api/licenses/{id}/overview-boes/", 5, 5, flat=True)

    def test_overview_allotments_budget(self):
        # Proves: overview-allotments is flat.
        self.budget("/api/licenses/{id}/overview-allotments/", 6, 6, flat=True)

    def test_overview_invoice_ledger_budget(self):
        # Proves: invoice ledger is N+1 on trades: LicenseTrade.paid_or_received runs
        # payments.aggregate() (ignores the prefetch) twice per trade (~2 q/trade).
        self.budget("/api/licenses/{id}/overview-invoice-ledger/", 10, 31)

    def test_overview_payment_ledgers_budget(self):
        # Proves: payment ledgers prefetch lines/payments/documents -> flat (no per-trade aggregate).
        self.budget("/api/licenses/{id}/overview-payment-ledgers/", 9, 9, flat=True)

    def test_balance_ledger_budget(self):
        # Proves: balance-ledger costs ~80 queries at 1 row and ~11 more per item/BOE/trade
        # (per-row allocation + invoice/BOE relationship builders).
        self.budget("/api/licenses/{id}/balance-ledger/", 86, 142)

    def test_plan_utilization_budget(self):
        # Proves: plan-utilization is ~32 fixed + ~1/row; the same function runs again inside retrieve().
        self.budget("/api/licenses/{id}/plan-utilization/", 35, 40)

    def test_ownership_data_budget(self):
        # Proves: ownership-data is flat at 2 queries.
        self.budget("/api/license-actions/{id}/ownership-data/", 3, 3, flat=True)


class ListEndpointBudgets(_Base):
    """BOE and allotment list endpoints, page_size=50, 1 vs 6 BOEs/allotments in the table."""

    def _list_budget(self, url, small_cap, large_cap):
        self.make_licence(SMALL, self.company, self.other)
        q_small = self.count(url)
        self.make_licence(LARGE - SMALL, self.company, self.other)
        q_large = self.count(url)
        print(f"BUDGET {url}: {SMALL} row={q_small}, {LARGE} rows={q_large}")
        self.assertLessEqual(q_small, small_cap)
        self.assertLessEqual(q_large, large_cap)

    def test_boe_list_budget(self):
        # Proves: BOE list is N+1 (~6 queries per BOE: get_authoritative_available_cif -> available_value_calculated SUMs).
        # 22 at 1 BOE, 51 at 6: the batched per-page invoice_status lookup (cb2abf5c) adds a flat +3 (was 19 / 48).
        # +1 query/row (57 at 6 rows): DEC-50 over-use guard in the per-row attributed balance (2026-11-20).
        self._list_budget("/api/bill-of-entries/?is_invoice=all&page_size=50", 23, 57)

    def test_boe_list_default_filter_budget(self):
        # Proves: the default is_invoice filter (no param) does not change the per-row cost.
        # +1 query/row (57 at 6 rows): DEC-50 over-use guard in the per-row attributed balance (2026-11-20).
        self._list_budget("/api/bill-of-entries/?page_size=50", 23, 57)

    def test_allotment_list_budget(self):
        # Proves: allotment list is flat (annotations + two prefetches).
        self._list_budget("/api/allotments/?is_boe=all&type=AT&is_allotted=all&page_size=50", 5, 5)

    def test_allotment_list_default_filters_budget(self):
        # Proves: default filters (is_boe=false, type=AT, is_allotted=true) stay flat.
        self._list_budget("/api/allotments/?page_size=50", 5, 5)
