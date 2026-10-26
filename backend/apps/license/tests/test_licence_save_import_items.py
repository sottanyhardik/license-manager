"""A licence save applies the items the form sent for each import line.

Regression: the save only set items on a line that had none, so a correction
made on the edit page came back 200 and was silently dropped. The form sends
every line's items on each save, so a non-empty list that differs from the
stored links is now applied. An empty list still keeps the stored links.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class LicenseSaveImportItemsTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())
        head = HeadSIONNormsModel.objects.create(name="Save import items")
        norm = SionNormClassModel.objects.create(head_norm=head, norm_class="C969", description="Tractor", is_active=True)
        self.battery = ItemNameModel.objects.create(name="AUTOMOTIVE BATTERY", sion_norm_class=norm)
        self.seat = ItemNameModel.objects.create(name="SEAT ASSEMBLY", sion_norm_class=norm)
        self.licence = self.make_license(self.make_company())
        LicenseExportItemModel.objects.create(license=self.licence, norm_class=norm, cif_fc=Decimal("1000.00"))
        self.line = LicenseImportItemsModel.objects.create(
            license=self.licence, serial_number=1, description="Automotive Battery-8507", quantity=Decimal("1"),
        )
        self.line.items.set([self.seat])

    def patch_line_items(self, items):
        return self.client.patch(
            f"/api/licenses/{self.licence.id}/",
            {"import_license": [{"id": self.line.id, "items": items}]},
            format="json",
        )

    def test_form_correction_replaces_the_stored_link(self):
        resp = self.patch_line_items([self.battery.id])

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(self.line.items.values_list("id", flat=True)), [self.battery.id])

    def test_correction_is_not_relinked_by_auto_linking(self):
        self.patch_line_items([self.battery.id])

        self.assertEqual(list(self.line.items.values_list("id", flat=True)), [self.battery.id])

    def test_empty_items_keep_the_stored_link(self):
        resp = self.patch_line_items([])

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(self.line.items.values_list("id", flat=True)), [self.seat.id])
