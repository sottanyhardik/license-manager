"""BOE list: header totals / FK reads must be batched per page, not per BOE."""
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin


class BoeListQueryCountTests(ReconciliationFixtureMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="boe_qc", password="x", email="b@example.com")
        self.company = self.make_company()
        self.port = self.make_port()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def _make(self, n):
        from decimal import Decimal
        for _ in range(n):
            boe = self.make_boe(self.company, port=self.port)
            self.make_debit_row(boe, self.item, Decimal("10.00"))

    def _capture(self):
        cache.clear()
        client = APIClient()
        client.force_authenticate(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get("/api/bill-of-entries/?page_size=50")
        self.assertEqual(resp.status_code, 200)
        return [q["sql"] for q in ctx.captured_queries], resp.json()["results"]

    def test_header_totals_and_fk_reads_are_batched(self):
        self._make(6)
        sqls, results = self._capture()
        self.assertEqual(len(results), 6)
        per_boe_sum = [s for s in sqls if "SUM(" in s and re.search(r'"bill_of_entry_rowdetails"\."bill_of_entry_id" = \d+', s)]
        self.assertEqual(per_boe_sum, [], "per-BOE SUM over rowdetails must be batched")
        item_by_id = [s for s in sqls if 'FROM "license_licenseimportitemsmodel"' in s and 'WHERE "license_licenseimportitemsmodel"."id" =' in s]
        self.assertEqual(item_by_id, [], "sr_number must be prefetched, not fetched per row")
        license_by_id = [s for s in sqls if s.startswith('SELECT "license_licensedetailsmodel"') and 'WHERE "license_licensedetailsmodel"."id" =' in s]
        self.assertEqual(license_by_id, [], "license must be prefetched, not fetched per row")

    def test_totals_values_match_row_sums(self):
        self._make(3)
        _, results = self._capture()
        for r in results:
            self.assertEqual(str(r["total_fc"]), "10.00")
            self.assertEqual(str(r["total_quantity"]), "100.000")
