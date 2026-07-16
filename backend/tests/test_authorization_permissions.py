import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel


User = get_user_model()


class LicenseActionAuthorizationTests(TestCase):
    def test_license_transfer_update_requires_license_manager_role(self):
        user = User.objects.create_user(
            username="viewer-without-role",
            email="viewer@example.com",
            password="ViewerP@ssw0rd123",
        )
        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

        response = client.post(
            "/api/license-actions/update-license-transfer/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MasterDataAuthorizationTests(TestCase):
    def _authenticated_client(self, user):
        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    def test_authenticated_non_superuser_can_read_but_not_create_master_data(self):
        user = User.objects.create_user(
            username="master-viewer",
            email="master-viewer@example.com",
            password="ViewerP@ssw0rd123",
        )
        CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Visible Co")
        client = self._authenticated_client(user)

        list_response = client.get("/api/masters/companies/")
        create_response = client.post(
            "/api/masters/companies/",
            {
                "iec": str(uuid.uuid4().int)[:10],
                "name": "Blocked Co",
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(CompanyModel.objects.filter(name="Blocked Co").exists())

    def test_superuser_can_create_master_data(self):
        user = User.objects.create_superuser(
            username="master-admin",
            email="master-admin@example.com",
            password="AdminP@ssw0rd123",
        )
        client = self._authenticated_client(user)
        data = {
            "iec": str(uuid.uuid4().int)[:10],
            "name": "Allowed Co",
        }

        response = client.post("/api/masters/companies/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CompanyModel.objects.filter(name="Allowed Co").exists())


class BOEPdfParseAuthorizationTests(TestCase):
    def _client_with_role(self, role_name):
        user = User.objects.create_user(
            username=f"{role_name.lower()}-user",
            email=f"{role_name.lower()}@example.com",
            password="RoleP@ssw0rd123",
        )
        group, _ = Group.objects.get_or_create(name=role_name)
        user.groups.add(group)
        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    def test_boe_manager_can_reach_boe_pdf_parser(self):
        client = self._client_with_role("BOE_MANAGER")

        response = client.post("/api/bill-of-entries/parse-pdf/", {}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "No file uploaded. Send the PDF as multipart field 'file'.",
        )

    def test_allotment_manager_cannot_reach_boe_pdf_parser(self):
        client = self._client_with_role("ALLOTMENT_MANAGER")

        response = client.post("/api/bill-of-entries/parse-pdf/", {}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DirectReportAuthorizationTests(TestCase):
    report_urls = (
        "/api/reports/inventory-balance/",
        "/api/reports/expiring-licenses/",
        "/api/reports/active-licenses/",
        "/api/reports/item-pivot/",
        "/api/reports/item-report/",
    )

    def _authenticated_client(self, username="report-user", roles=()):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="ReportP@ssw0rd123",
        )
        for role_name in roles:
            group, _ = Group.objects.get_or_create(name=role_name)
            user.groups.add(group)

        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    def test_direct_report_urls_require_authentication(self):
        client = APIClient()

        for url in self.report_urls:
            with self.subTest(url=url):
                response = client.get(url)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_direct_report_urls_require_report_role(self):
        client = self._authenticated_client(username="not-report-authorized")

        for url in self.report_urls:
            with self.subTest(url=url):
                response = client.get(url)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_report_viewer_reaches_direct_report_view(self):
        client = self._authenticated_client(
            username="report-viewer",
            roles=("REPORT_VIEWER",),
        )

        response = client.get("/api/reports/inventory-balance/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"], "sion_norm parameter is required")


class TradeNestedAuthorizationTests(TestCase):
    trade_urls = (
        "/api/trades/",
        "/api/lines/",
        "/api/payments/",
    )

    def _authenticated_client(self, username="trade-user", roles=()):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="TradeP@ssw0rd123",
        )
        for role_name in roles:
            group, _ = Group.objects.get_or_create(name=role_name)
            user.groups.add(group)

        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    def test_trade_endpoints_require_trade_role(self):
        client = self._authenticated_client(username="not-trade-authorized")

        for url in self.trade_urls:
            with self.subTest(url=url):
                response = client.get(url)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_trade_viewer_can_read_trade_endpoints(self):
        client = self._authenticated_client(
            username="trade-viewer",
            roles=("TRADE_VIEWER",),
        )

        for url in self.trade_urls:
            with self.subTest(url=url):
                response = client.get(url)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
