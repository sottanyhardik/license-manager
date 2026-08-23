"""
Regression tests for the nested `export_license` (and, symmetrically,
`import_license`) partial-update validation bug: `LicenseDetailsSerializer
.validate()` used to unconditionally require `description`/`net_quantity`
(export) or `hs_code`/`description`/`serial_number`/`unit` (import) on
every row in the array, even for a row that already exists and is only
being patched for an unrelated field (e.g. the License Overview page's
inline SION Norm editor, which PATCHes `export_license` as a list of bare
`{id}` rows plus one `{id, norm_class}` row — see `SionNormCard.tsx` /
`useLicenseSionNorm.ts`).

`LicenseWriteMixin.update()` already only `setattr`s keys present in each
row dict (verified separately), so the write path never needed full field
data for existing rows — only `validate()` was overly strict.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class ExportItemPartialUpdateTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def make_norm_class(self, code="E5", description="Biscuits"):
        head = HeadSIONNormsModel.objects.create(name=f"Head {code}")
        return SionNormClassModel.objects.create(head_norm=head, norm_class=code, description=description, is_active=True)

    def make_export_item(self, license_obj, **overrides):
        defaults = dict(
            license=license_obj,
            description="Widget A",
            net_quantity=Decimal("100.00"),
            unit="kg",
        )
        defaults.update(overrides)
        return LicenseExportItemModel.objects.create(**defaults)

    def test_update_sion_norm_without_touching_other_export_fields(self):
        """The exact real-world payload shape the Overview page's inline
        SION Norm editor sends: every existing row as a bare `{id}`, plus
        the target row also carrying `norm_class`. No `description`/
        `net_quantity` supplied for either row."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_export_item(license_obj, description="Original description", net_quantity=Decimal("42.00"))
        new_norm = self.make_norm_class()

        resp = self.client.patch(
            f"/api/licenses/{license_obj.id}/",
            {"export_license": [{"id": item.id, "norm_class": new_norm.id}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        item.refresh_from_db()
        self.assertEqual(item.norm_class_id, new_norm.id)
        # Untouched fields survive exactly as they were.
        self.assertEqual(item.description, "Original description")
        self.assertEqual(item.net_quantity, Decimal("42.00"))

    def test_update_one_export_item_among_several_leaves_siblings_untouched(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item1 = self.make_export_item(license_obj, description="Item 1", net_quantity=Decimal("10.00"))
        item2 = self.make_export_item(license_obj, description="Item 2", net_quantity=Decimal("20.00"))
        norm = self.make_norm_class()

        resp = self.client.patch(
            f"/api/licenses/{license_obj.id}/",
            {"export_license": [{"id": item1.id}, {"id": item2.id, "norm_class": norm.id}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(LicenseExportItemModel.objects.filter(license=license_obj).count(), 2)
        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertIsNone(item1.norm_class_id)
        self.assertEqual(item1.description, "Item 1")
        self.assertEqual(item2.norm_class_id, norm.id)
        self.assertEqual(item2.description, "Item 2")

    def test_adding_a_new_export_item_still_requires_description_and_net_quantity(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_export_item(license_obj)

        resp = self.client.patch(
            f"/api/licenses/{license_obj.id}/",
            {"export_license": [{"id": item.id}, {"description": "", "net_quantity": None}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 400, resp.data)
        errors = resp.data["export_license"]
        # First (existing) row: no errors (DRF renders the "no error" `None`
        # placeholder as an `ErrorDetail('None')` string, never a dict of
        # field errors). Second (new) row: both required.
        self.assertNotIsInstance(errors[0], dict)
        self.assertIn("description", errors[1])
        self.assertIn("net_quantity", errors[1])

    def test_adding_a_genuinely_new_export_item_with_full_data_succeeds(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_export_item(license_obj)

        resp = self.client.patch(
            f"/api/licenses/{license_obj.id}/",
            {"export_license": [
                {"id": item.id},
                {"description": "New Item", "net_quantity": "5.00", "unit": "kg"},
            ]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(LicenseExportItemModel.objects.filter(license=license_obj).count(), 2)
        new_item = LicenseExportItemModel.objects.filter(license=license_obj).exclude(id=item.id).get()
        self.assertEqual(new_item.description, "New Item")
        self.assertEqual(new_item.net_quantity, Decimal("5.00"))

    def test_omitting_an_existing_export_item_deletes_it(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item1 = self.make_export_item(license_obj, description="Keep me")
        item2 = self.make_export_item(license_obj, description="Delete me")

        resp = self.client.patch(
            f"/api/licenses/{license_obj.id}/",
            {"export_license": [{"id": item1.id}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        remaining = list(LicenseExportItemModel.objects.filter(license=license_obj))
        self.assertEqual([r.id for r in remaining], [item1.id])
        self.assertFalse(LicenseExportItemModel.objects.filter(id=item2.id).exists())

    def test_explicitly_blanking_description_on_an_existing_item_is_still_rejected(self):
        """An existing row that supplies `description` in the payload is
        still validated on that field — the exemption only skips fields the
        caller never mentioned, it doesn't allow clearing a required field
        with a blank value."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_export_item(license_obj)

        resp = self.client.patch(
            f"/api/licenses/{license_obj.id}/",
            {"export_license": [{"id": item.id, "description": "   "}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("description", resp.data["export_license"][0])


class ImportItemPartialUpdateTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """Same existing-row exemption, applied symmetrically to `import_license`
    (identical bug shape: `hs_code`/`description`/`serial_number`/`unit`
    were required on every row regardless of whether it already existed)."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def test_update_one_import_item_field_without_full_row_data(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Import Widget",
            quantity=Decimal("1000.000"),
            unit="kg",
        )

        resp = self.client.patch(
            f"/api/licenses/{license_obj.id}/",
            {"import_license": [{"id": item.id, "quantity": "2000.000"}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal("2000.000"))
        self.assertEqual(item.description, "Import Widget")

    def test_adding_a_new_import_item_still_requires_its_fields(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Import Widget",
            quantity=Decimal("1000.000"), unit="kg",
        )

        resp = self.client.patch(
            f"/api/licenses/{license_obj.id}/",
            {"import_license": [{"id": item.id}, {"description": ""}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 400, resp.data)
        errors = resp.data["import_license"]
        self.assertNotIsInstance(errors[0], dict)
        self.assertIn("hs_code", errors[1])
        self.assertIn("description", errors[1])
        self.assertIn("serial_number", errors[1])
        self.assertIn("unit", errors[1])
