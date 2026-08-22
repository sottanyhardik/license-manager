import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.permissions import CompanyPermission
from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel, PortModel
from apps.core.serializers.models import CompanySerializer


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
        # Uses PortModel (still gated by the blanket MasterDataPermission)
        # rather than CompanyModel — companies carry banking/PAN/GST fields
        # and are scoped by CompanyPermission instead; see
        # CompanyPermissionAuthorizationTests below.
        user = User.objects.create_user(
            username="master-viewer",
            email="master-viewer@example.com",
            password="ViewerP@ssw0rd123",
        )
        PortModel.objects.create(code=str(uuid.uuid4().int)[:6], name="Visible Port")
        client = self._authenticated_client(user)

        list_response = client.get("/api/masters/ports/")
        create_response = client.post(
            "/api/masters/ports/",
            {
                "code": str(uuid.uuid4().int)[:6],
                "name": "Blocked Port",
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(PortModel.objects.filter(name="Blocked Port").exists())

    def test_other_master_data_entities_remain_unaffected_by_company_scoping(self):
        # HS codes and item names (unlike companies) carry no banking/PAN/GST
        # data and must remain reachable by any authenticated user, exactly
        # as before the CompanyPermission change — proving the fix is scoped
        # to CompanyViewSet only and did not tighten (or loosen) any other
        # master-data endpoint.
        user = User.objects.create_user(
            username="master-viewer-2",
            email="master-viewer-2@example.com",
            password="ViewerP@ssw0rd123",
        )
        HSCodeModel.objects.create(hs_code=str(uuid.uuid4().int)[:8])
        ItemNameModel.objects.create(name=f"Visible Item {uuid.uuid4()}")
        client = self._authenticated_client(user)

        hs_list_response = client.get("/api/masters/hs-codes/")
        hs_create_response = client.post(
            "/api/masters/hs-codes/",
            {"hs_code": str(uuid.uuid4().int)[:8]},
            format="json",
        )
        item_list_response = client.get("/api/masters/item-names/")

        self.assertEqual(hs_list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(hs_create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(item_list_response.status_code, status.HTTP_200_OK)

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


class CompanyPermissionAuthorizationTests(TestCase):
    """
    CompanyViewSet (`/api/masters/companies/`) carries banking/PAN/GST
    fields, so — unlike the other master-data endpoints — it must not be
    reachable by every authenticated user regardless of role.
    """

    def _client_with_roles(self, username, roles=()):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="RoleP@ssw0rd123",
        )
        for role_name in roles:
            group, _ = Group.objects.get_or_create(name=role_name)
            user.groups.add(group)
        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    def test_authenticated_user_with_no_business_role_is_blocked(self):
        CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="Roleless-Blocked Co",
            bank_account_number="1234567890",
            pan="ABCDE1234F",
        )
        client = self._client_with_roles("no-role-user")

        list_response = client.get("/api/masters/companies/")

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_with_trade_viewer_role_can_read_company_data(self):
        company = CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="Trade-Visible Co",
        )
        client = self._client_with_roles("trade-viewer-user", roles=["TRADE_VIEWER"])

        list_response = client.get("/api/masters/companies/")
        detail_response = client.get(f"/api/masters/companies/{company.id}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

    def test_user_with_unrelated_role_cannot_read_company_data(self):
        CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Unrelated-Blocked Co")
        client = self._client_with_roles("user-manager-user", roles=["USER_MANAGER"])

        list_response = client.get("/api/masters/companies/")

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_role_scoped_user_still_cannot_write_company_data(self):
        client = self._client_with_roles("trade-manager-user", roles=["TRADE_MANAGER"])

        response = client.post(
            "/api/masters/companies/",
            {"iec": str(uuid.uuid4().int)[:10], "name": "Should Not Be Created"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(CompanyModel.objects.filter(name="Should Not Be Created").exists())

    def test_report_viewer_role_no_longer_receives_banking_fields_in_response(self):
        # SEC-02 follow-up: REPORT_VIEWER (along with the other 8 roles in
        # `_narrowed_roles`) was left in `required_roles_for_read` because it
        # has a legitimate non-banking reason to look up a company (e.g.
        # report/allotment filters), but it has no business need to see
        # banking/PAN/GST data. `CompanySerializer.to_representation` now
        # trims those fields for every role except
        # `CompanyPermission.full_access_roles_for_sensitive_fields`. This
        # replaces the previous version of this test, which documented the
        # gap as still-open; the gap is now closed.
        CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="Report-Viewer-Visible Co",
            bank_account_number="9876543210",
            pan="ZYXWV9876Q",
        )
        client = self._client_with_roles("report-viewer-only", roles=["REPORT_VIEWER"])

        response = client.get("/api/masters/companies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        rows = body["results"] if isinstance(body, dict) and "results" in body else body
        row = next(r for r in rows if r["name"] == "Report-Viewer-Visible Co")
        # Non-sensitive fields (name/address/etc.) are still present...
        self.assertEqual(row["name"], "Report-Viewer-Visible Co")
        # ...but every sensitive field has been trimmed from the payload.
        for field in CompanySerializer.SENSITIVE_FIELDS:
            self.assertNotIn(field, row)

    @property
    def _narrowed_roles(self):
        full_access = set(CompanyPermission.full_access_roles_for_sensitive_fields)
        return [
            role for role in CompanyPermission.required_roles_for_read
            if role not in full_access
        ]

    def test_full_access_roles_receive_every_sensitive_field_unchanged(self):
        # The 4 roles approved to keep full access must see every sensitive
        # field, byte-for-byte identical to pre-fix behavior.
        company = CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="Full-Access-Visible Co",
            pan="ABCDE1234F",
            gst_number="22ABCDE1234F1Z5",
            bank_account_number="1111222233",
            bank_name="Test Bank",
            ifsc_code="TEST0123456",
            account_type="SAVINGS",
        )

        for role_name in CompanyPermission.full_access_roles_for_sensitive_fields:
            with self.subTest(role=role_name):
                client = self._client_with_roles(f"full-access-{role_name.lower()}", roles=[role_name])

                response = client.get(f"/api/masters/companies/{company.id}/")

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                row = response.json()
                self.assertEqual(row["pan"], "ABCDE1234F")
                self.assertEqual(row["gst_number"], "22ABCDE1234F1Z5")
                self.assertEqual(row["bank_account_number"], "1111222233")
                self.assertEqual(row["bank_name"], "Test Bank")
                self.assertEqual(row["ifsc_code"], "TEST0123456")
                self.assertEqual(row["account_type"], "SAVINGS")

    def test_narrowed_roles_do_not_receive_any_sensitive_field(self):
        # The 9 roles that keep read access for non-sensitive lookups
        # (dropdowns/filters/master-data listing) must not receive any of
        # the 6 sensitive fields, and the request must not error.
        company = CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="Narrowed-Visible Co",
            pan="ABCDE1234F",
            gst_number="22ABCDE1234F1Z5",
            bank_account_number="1111222233",
            bank_name="Test Bank",
            ifsc_code="TEST0123456",
            account_type="SAVINGS",
        )

        for role_name in self._narrowed_roles:
            with self.subTest(role=role_name):
                client = self._client_with_roles(f"narrowed-{role_name.lower()}", roles=[role_name])

                list_response = client.get("/api/masters/companies/")
                detail_response = client.get(f"/api/masters/companies/{company.id}/")

                self.assertEqual(list_response.status_code, status.HTTP_200_OK)
                self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

                list_body = list_response.json()
                rows = list_body["results"] if isinstance(list_body, dict) and "results" in list_body else list_body
                list_row = next(r for r in rows if r["name"] == "Narrowed-Visible Co")
                detail_row = detail_response.json()

                for field in CompanySerializer.SENSITIVE_FIELDS:
                    self.assertNotIn(field, list_row)
                    self.assertNotIn(field, detail_row)

                # Non-sensitive master data is unaffected.
                self.assertEqual(list_row["name"], "Narrowed-Visible Co")
                self.assertEqual(detail_row["name"], "Narrowed-Visible Co")

    def test_superuser_always_receives_full_fields(self):
        # Superusers bypass CompanyPermission's role gate entirely and must
        # always see every sensitive field, regardless of group membership.
        company = CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="Superuser-Visible Co",
            pan="ABCDE1234F",
            gst_number="22ABCDE1234F1Z5",
            bank_account_number="1111222233",
            bank_name="Test Bank",
            ifsc_code="TEST0123456",
            account_type="SAVINGS",
        )
        superuser = User.objects.create_superuser(
            username="company-superuser",
            email="company-superuser@example.com",
            password="AdminP@ssw0rd123",
        )
        token = RefreshToken.for_user(superuser)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

        response = client.get(f"/api/masters/companies/{company.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.json()
        self.assertEqual(row["pan"], "ABCDE1234F")
        self.assertEqual(row["gst_number"], "22ABCDE1234F1Z5")
        self.assertEqual(row["bank_account_number"], "1111222233")
        self.assertEqual(row["bank_name"], "Test Bank")
        self.assertEqual(row["ifsc_code"], "TEST0123456")
        self.assertEqual(row["account_type"], "SAVINGS")

    def test_narrowed_role_list_metadata_does_not_crash_with_missing_columns(self):
        # CompanyViewSet's list_display metadata still names "pan"/
        # "gst_number" as columns (apps/core/views/views.py); for narrowed
        # roles those keys are simply absent from each row now. Confirms
        # the frontend-facing metadata degrades gracefully (no 500, no
        # serializer error) rather than trimming list_display itself.
        CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="Metadata-Check Co",
            pan="ABCDE1234F",
            gst_number="22ABCDE1234F1Z5",
        )
        client = self._client_with_roles("metadata-check-user", roles=["LICENSE_VIEWER"])

        response = client.get("/api/masters/companies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("pan", body["list_display"])
        self.assertIn("gst_number", body["list_display"])
        row = next(r for r in body["results"] if r["name"] == "Metadata-Check Co")
        self.assertNotIn("pan", row)
        self.assertNotIn("gst_number", row)

    def test_unauthenticated_request_is_denied(self):
        CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name="Unauth-Blocked Co")
        client = APIClient()

        response = client.get("/api/masters/companies/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_every_documented_legitimate_role_can_read_multiple_companies(self):
        # Regresses the fix against every role it claims to preserve access
        # for (not just TRADE_VIEWER), and against more than one company
        # record, so the scoping is proven role-by-role and not dependent on
        # which single company/role pair happens to be exercised.
        companies = [
            CompanyModel.objects.create(iec=str(uuid.uuid4().int)[:10], name=f"Multi Co {i}")
            for i in range(3)
        ]
        expected_ids = {c.id for c in companies}

        for role_name in CompanyPermission.required_roles_for_read:
            with self.subTest(role=role_name):
                client = self._client_with_roles(f"role-{role_name.lower()}", roles=[role_name])

                list_response = client.get("/api/masters/companies/")

                self.assertEqual(list_response.status_code, status.HTTP_200_OK)
                returned_ids = {row["id"] for row in list_response.json()["results"]} \
                    if isinstance(list_response.json(), dict) and "results" in list_response.json() \
                    else {row["id"] for row in list_response.json()}
                self.assertTrue(expected_ids.issubset(returned_ids))

    def test_every_documented_legitimate_role_is_still_blocked_from_writing(self):
        # required_roles_for_write is empty, so write access must stay
        # superuser-only for every one of the read-authorized roles too —
        # confirms the fix did not accidentally grant write access anywhere.
        for role_name in CompanyPermission.required_roles_for_read:
            with self.subTest(role=role_name):
                client = self._client_with_roles(
                    f"writer-{role_name.lower()}", roles=[role_name]
                )
                unique_name = f"Should Not Be Created {role_name}"

                response = client.post(
                    "/api/masters/companies/",
                    {"iec": str(uuid.uuid4().int)[:10], "name": unique_name},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertFalse(CompanyModel.objects.filter(name=unique_name).exists())


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

                # JWT authentication advertises a Bearer challenge, so an
                # unauthenticated request is correctly a 401. The following
                # test retains the distinct authenticated-but-forbidden 403
                # assertion.
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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
