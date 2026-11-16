"""Query count of GET /api/licenses/ must be constant in page size (no per-row N+1)."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, NotificationNumber, SchemeCode
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel
from apps.license.models.core import LicenseTransferModel


class LicenseListQueryCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="qc_admin", password="x", email="qc@example.com")
        cls.company = CompanyModel.objects.create(iec="0123456789", name="QC Co")
        cls.scheme = SchemeCode.objects.create(code="QC-SCHEME")
        cls.notif = NotificationNumber.objects.create(code="QC-NOTIF")

    def _make(self, n):
        for i in range(n):
            lic = LicenseDetailsModel.objects.create(
                license_number=f"03{n}{i:06d}{LicenseDetailsModel.objects.count()}",
                license_date=date.today(),
                license_expiry_date=date.today() + timedelta(days=365),
                exporter=self.company,
                scheme_code=self.scheme,
                notification_number=self.notif,
            )
            LicenseExportItemModel.objects.create(license=lic, description="exp")
            LicenseTransferModel.objects.create(
                license=lic, from_company=self.company, to_company=self.company,
                transfer_status="done", transfer_date=date.today(),
            )

    def _count(self, page_size):
        cache.clear()
        client = APIClient()
        client.force_authenticate(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(f"/api/licenses/?page_size={page_size}&is_expired=all&is_null=all")
        self.assertEqual(resp.status_code, 200)
        return len(ctx), len(resp.json()["results"])

    def test_query_count_does_not_grow_with_rows(self):
        self._make(2)
        small, n_small = self._count(50)
        self._make(8)
        large, n_large = self._count(50)
        self.assertGreater(n_large, n_small)
        # Prefetch/select_related keep the count flat; allow tiny slack for
        # data-dependent branches (e.g. batch maps), never per-row growth.
        self.assertLessEqual(large, small + 2, f"{small} queries for {n_small} rows -> {large} for {n_large}")
        self.assertLess(large, 40)
