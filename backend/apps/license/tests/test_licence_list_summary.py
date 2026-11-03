"""The licence list row's summary: status from the stored flags, the owner, and the canonical available CIF.

Built on the report fixture, so the figures come from real rows. The available CIF is checked
against the licence-balances detail endpoint, which is the figure the licence workspace shows.
"""

import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.license.models import LicenseDetailsModel, LicenseFlags, LicenseOwnership
from apps.license.services.licence_status import ACTIVE, EXPIRED, INACTIVE, licence_status
from apps.license.tests import test_licence_balance_report as base


class LicenceListSummaryTests(base.ReportFixture):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="ls-" + uuid.uuid4().hex[:6], password="x")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _row(self, licence, **params):
        response = self.api.get("/api/licenses/", {"search": licence.license_number, **params})
        self.assertEqual(response.status_code, 200)
        rows = [r for r in response.json()["results"] if r["id"] == licence.id]
        self.assertEqual(len(rows), 1, "the licence should be on the list page")
        return rows[0]

    def test_row_carries_the_summary_fields_from_the_database(self):
        row = self._row(self.licence)
        self.assertEqual(row["license_number"], self.licence.license_number)
        self.assertEqual(row["license_expiry_date"], self.licence.license_expiry_date.strftime("%d-%m-%Y"))
        self.assertEqual(row["exporter_name"], "Seller Co")
        self.assertIn("current_owner_name", row)
        self.assertIn("available_cif", row)
        self.assertEqual(row["licence_status_code"], ACTIVE)
        self.assertEqual(row["licence_status_label"], "Active")

    def test_available_cif_is_the_figure_the_licence_workspace_shows(self):
        trade, _ = self._sale(invoice="LS-1", cif="300", qty="300")
        self._boe("LS-B", cif="120", qty="120", trades=[trade])
        detail = self.api.get(f"/api/licence-balances/{self.licence.id}/").json()
        self.assertEqual(self._row(self.licence)["available_cif"], detail["cif"]["available"])

    def test_owner_name_comes_from_the_stored_ownership(self):
        LicenseOwnership.objects.update_or_create(license=self.licence, defaults={"current_owner": self.customer})
        self.assertEqual(self._row(self.licence)["current_owner_name"], "Customer One")

    def test_owner_is_null_when_no_ownership_is_recorded(self):
        self.assertIsNone(self._row(self.licence)["current_owner_name"])

    def test_expiry_date_in_the_past_gives_expired_status(self):
        LicenseDetailsModel.objects.filter(pk=self.licence.pk).update(license_expiry_date=date.today() - timedelta(days=1))
        row = self._row(self.licence, is_expired="True")
        self.assertEqual((row["licence_status_code"], row["licence_status_label"]), (EXPIRED, "Expired"))

    def test_inactive_flag_gives_inactive_status(self):
        LicenseFlags.objects.update_or_create(license=self.licence, defaults={"is_active": False})
        row = self._row(self.licence)
        self.assertEqual((row["licence_status_code"], row["licence_status_label"]), (INACTIVE, "Inactive"))

    def test_a_stale_expired_flag_does_not_override_the_expiry_date(self):
        # The expiry date is in the future. The denormalised flag is stale, and the date wins, as in `check-validity`.
        LicenseFlags.objects.update_or_create(license=self.licence, defaults={"is_expired": True, "is_active": True})
        fresh = LicenseDetailsModel.objects.get(pk=self.licence.pk)
        self.assertEqual(licence_status(fresh)[0], ACTIVE)

    def test_detail_endpoint_keeps_its_shape(self):
        detail = self.api.get(f"/api/licenses/{self.licence.id}/")
        self.assertEqual(detail.status_code, 200)
        for field in ("available_cif", "licence_status_code", "current_owner_name"):
            self.assertNotIn(field, detail.json())
