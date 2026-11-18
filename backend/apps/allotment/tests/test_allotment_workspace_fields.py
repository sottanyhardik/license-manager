"""Read-only additions for the /allotments workspace:

* ``balanced_value`` — remaining allotment CIF (FC), the same ceiling
  ``allocate-items`` enforces (max(required_value − allotted_value, 0));
* ``activity-logs/?endpoint_prefix=`` — every audited call under one path
  (allocate / release history), still restricted to user managers.
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.tests.test_boe_api_contract import LOCMEM_CACHES, BoeApiFixtureMixin
from apps.core.models import ActivityLog


@override_settings(CACHES=LOCMEM_CACHES)
class BalancedValueTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        licence = self.make_license(self.company)
        self.item = self.make_item(licence)
        self.allotment = self.make_allotment(self.company, item=self.item, cif_fc=Decimal("300.00"))
        self.allotment.unit_value_per_unit = Decimal("100.00")  # required 10 × 100 = 1000.00
        self.allotment.save()
        self.client = self.client_for(self.make_role_user("ALLOTMENT_VIEWER"))

    def test_detail_and_list_expose_the_allocate_items_ceiling(self):
        detail = self.client.get(f"/api/allotments/{self.allotment.pk}/").data
        self.assertEqual(detail["balanced_value"], "700.00")
        self.assertEqual(detail["allotted_value"], "300.00")
        rows = self.client.get("/api/allotments/", {"page_size": 100, "is_boe": "all"}).data
        rows = rows.get("results", rows)
        row = next(r for r in rows if r["id"] == self.allotment.pk)
        self.assertEqual(row["balanced_value"], "700.00")

    def test_never_negative_when_over_allocated(self):
        AllotmentItems.objects.filter(allotment=self.allotment).update(cif_fc=Decimal("1500.00"))
        detail = self.client.get(f"/api/allotments/{self.allotment.pk}/").data
        self.assertEqual(detail["balanced_value"], "0.00")


@override_settings(CACHES=LOCMEM_CACHES)
class ActivityLogEndpointPrefixTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        for endpoint, action in (
            ("/api/allotment-actions/7/allocate-items/", ActivityLog.ACTION_CREATE),
            ("/api/allotment-actions/7/delete-item/31/", ActivityLog.ACTION_DELETE),
            ("/api/allotment-actions/70/allocate-items/", ActivityLog.ACTION_CREATE),
        ):
            ActivityLog.objects.create(username="ops", action=action, module="ALLOTMENT", endpoint=endpoint, method="POST", status_code=201)

    def test_prefix_matches_one_record_only(self):
        client = self.client_for(self.make_role_user("USER_MANAGER"))
        response = client.get("/api/masters/activity-logs/", {"endpoint_prefix": "/api/allotment-actions/7", "changes_only": 1})
        self.assertEqual(response.status_code, 200)
        rows = response.data if isinstance(response.data, list) else response.data.get("results", [])
        self.assertEqual(sorted(r["endpoint"] for r in rows), [
            "/api/allotment-actions/7/allocate-items/", "/api/allotment-actions/7/delete-item/31/",
        ])

    def test_audit_log_still_requires_user_manager(self):
        client = self.client_for(self.make_role_user("ALLOTMENT_MANAGER"), raise_request_exception=False)
        self.assertEqual(client.get("/api/masters/activity-logs/", {"endpoint_prefix": "/api/allotment-actions/7/"}).status_code, 403)
