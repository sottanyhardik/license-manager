from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.models import LicenseDetailsModel


class IndividualItemCifOverrideActionTests(TestCase):
    def setUp(self):
        self.licence = LicenseDetailsModel.objects.create(license_number="CIF-OVERRIDE-001")
        self.manager = get_user_model().objects.create_user(
            username="individual-cif-manager", password="testpass123!"
        )
        group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
        self.manager.groups.add(group)
        self.client = APIClient()
        self.client.force_authenticate(self.manager)
        self.url = f"/api/licenses/{self.licence.pk}/individual-item-cif-override/"

    def test_accepts_only_literal_nullable_json_booleans(self):
        for value in (True, False, None):
            response = self.client.patch(self.url, {"individual_item_cif_override": value}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.licence.refresh_from_db()
            self.assertIs(self.licence.individual_item_cif_override, value)

        for value in ("true", "false", 1, 0):
            response = self.client.patch(self.url, {"individual_item_cif_override": value}, format="json")
            self.assertEqual(response.status_code, 400, response.data)

    def test_rejects_unrelated_fields_and_requires_license_manager(self):
        response = self.client.patch(
            self.url,
            {"individual_item_cif_override": True, "license_number": "tamper"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

        viewer = get_user_model().objects.create_user(username="individual-cif-viewer", password="testpass123!")
        self.client.force_authenticate(viewer)
        response = self.client.patch(self.url, {"individual_item_cif_override": True}, format="json")
        self.assertEqual(response.status_code, 403, response.data)
