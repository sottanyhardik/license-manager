"""Licence-list Null DFIA filter, dashboard counts, and the default-filter contract.

Mechanisms under test, which are DIFFERENT and must stay separate:

1. LIVE list filter (views/license.py `apply_advanced_filters`): `is_null` and
   `flags__is_null` classify a licence from its live financial balance. Threshold 200.
2. STORED flag (`LicenseFlags.is_null`, set by signals.py / validation_service.py):
   documented as "Null DFIA = balance < $500". The dashboard counts this stored flag.

Threshold decision A (200 or 500) is NOT approved. The boundary tests below pin the
CURRENT live-list behaviour and are labelled as characterization. Stored-flag tests
document the current mechanism and do not endorse it.

Server default contract: `default_filters` declares `flags__is_null=False`, but the
server-side lookup reads `default_filters.get('is_null')`, which never matches, so the
default is applied by the UI only. test_server_applies_no_null_default_when_unspecified
pins that behaviour; changing it changes the list API contract (decision B/C).
"""
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

LIVE_LIST_THRESHOLD = Decimal("200")
BOUNDARY_BALANCES = ["0.00", "199.00", "200.00", "201.00", "499.00", "500.00", "501.00"]


class LicenseDefaultActiveFilterTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        cache.clear()  # the dashboard response is cached per role
        self.client = APIClient()
        user = self.make_plain_user()
        user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])
        self.client.force_authenticate(user=user)
        self.company = self.make_company("Default Filter Co")

    def _licence_with_balance(self, balance):
        """A licence whose live financial balance is `balance` (no BOE debit)."""
        license_obj = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal(balance))
        LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Widget A",
            quantity=Decimal("1000.000"),
            cif_fc=Decimal(balance),
        )
        return license_obj

    def _ids(self, **params):
        response = self.client.get("/api/licenses/", {"page_size": 200, **params})
        self.assertEqual(response.status_code, 200, response.data)
        return {row["id"] for row in response.data["results"]}

    # --- Live list filter: boundaries (characterization of threshold 200) ---

    def test_live_list_null_filter_boundaries_around_threshold_200(self):
        licences = {bal: self._licence_with_balance(bal) for bal in BOUNDARY_BALANCES}
        null_ids = self._ids(is_null="true")
        non_null_ids = self._ids(is_null="false")
        for bal, licence in licences.items():
            expected_null = Decimal(bal) < LIVE_LIST_THRESHOLD
            self.assertEqual(
                licence.id in null_ids, expected_null,
                f"balance {bal}: is_null=true membership should be {expected_null} (threshold 200, pending decision A)",
            )
            self.assertEqual(
                licence.id in non_null_ids, not expected_null,
                f"balance {bal}: is_null=false membership should be {not expected_null}",
            )

    def test_both_parameter_names_behave_identically(self):
        null_licence = self._licence_with_balance("0.00")
        healthy = self._licence_with_balance("1000.00")
        for name in ("is_null", "flags__is_null"):
            with self.subTest(parameter=name):
                self.assertIn(null_licence.id, self._ids(**{name: "true"}))
                self.assertNotIn(healthy.id, self._ids(**{name: "true"}))
                self.assertIn(healthy.id, self._ids(**{name: "false"}))
                self.assertNotIn(null_licence.id, self._ids(**{name: "false"}))

    def test_is_null_all_disables_the_null_filter(self):
        null_licence = self._licence_with_balance("0.00")
        healthy = self._licence_with_balance("1000.00")
        ids = self._ids(is_null="all")
        self.assertIn(null_licence.id, ids)
        self.assertIn(healthy.id, ids)

    # --- Server default contract and the UI default combination ---

    def test_server_applies_no_null_default_when_unspecified(self):
        """CHARACTERIZATION. An unfiltered request returns the zero-balance licence.
        Existing tests (license_validity_api, license_list_balance_consistency) rely on
        this unfiltered list. Changing it requires decision B/C."""
        null_licence = self._licence_with_balance("0.00")
        self.assertIn(null_licence.id, self._ids())

    def test_ui_default_combination_excludes_zero_balance_and_keeps_healthy(self):
        null_licence = self._licence_with_balance("0.00")
        healthy = self._licence_with_balance("1000.00")
        ids = self._ids(is_expired="False", flags__is_null="False")
        self.assertNotIn(null_licence.id, ids)
        self.assertIn(healthy.id, ids)

    def test_expired_licence_is_excluded_by_is_expired_false(self):
        from datetime import date, timedelta
        expired = self._licence_with_balance("1000.00")
        expired.license_expiry_date = date.today() - timedelta(days=5)
        expired.save(update_fields=["license_expiry_date"])
        healthy = self._licence_with_balance("1000.00")
        ids = self._ids(is_expired="False")
        self.assertNotIn(expired.id, ids)
        self.assertIn(healthy.id, ids)

    def test_missing_flags_row_does_not_break_live_classification(self):
        from apps.license.models import LicenseFlags
        healthy = self._licence_with_balance("1000.00")
        LicenseFlags.objects.filter(license=healthy).delete()
        response = self.client.get("/api/licenses/", {"page_size": 200, "is_null": "false"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(healthy.id, {row["id"] for row in response.data["results"]})

    # --- Stored-flag mechanism: dashboard counts (characterization of the defect) ---

    def test_dashboard_active_count_uses_stored_flag_not_live_balance(self):
        """DEFECT CHARACTERIZATION. A licence with live balance 1000 but a stored
        flags.is_null=True is listed as active by the live list but NOT counted as
        active by the dashboard. Remediation requires decision A/B/C."""
        healthy = self._licence_with_balance("1000.00")
        healthy.flags.is_null = True
        healthy.flags.save(update_fields=["is_null"])
        cache.clear()

        self.assertIn(healthy.id, self._ids(is_null="false"))
        dashboard = self.client.get("/api/dashboard/")
        self.assertEqual(dashboard.status_code, 200, dashboard.data)
        stats = dashboard.data["license_stats"]
        # The dashboard active count is exactly the stored-flag query ...
        stored_active = LicenseDetailsModel.objects.filter(
            flags__is_expired=False, flags__is_null=False,
        ).count()
        self.assertEqual(stats["active"], stored_active)
        # ... so the healthy licence (live balance 1000) is NOT counted as active,
        # while the live list classifies it as non-null.
        self.assertFalse(
            LicenseDetailsModel.objects.filter(id=healthy.id, flags__is_null=False).exists()
        )
        self.assertIn(healthy.id, self._ids(is_null="false"))
