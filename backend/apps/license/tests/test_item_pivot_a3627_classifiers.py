"""Item Pivot product categories for A3627 (RUTILE / BORAX) must not show as UNCLASSIFIED."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.core.constants import GE
from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, PurchaseStatus, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.views.item_pivot_report import ItemPivotReportView


class A3627PivotCategoryTests(TestCase):
    def setUp(self):
        company = CompanyModel.objects.create(iec="A3627PIV", name="A3627 Pivot Exporter")
        status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        head = HeadSIONNormsModel.objects.create(name="A3627 Head Norm")
        norm = SionNormClassModel.objects.create(head_norm=head, norm_class="A3627", is_active=True)
        self.license = LicenseDetailsModel.objects.create(
            license_number="A3627-PIVOT-001", license_date=date.today() - timedelta(days=1),
            license_expiry_date=date.today() + timedelta(days=30), exporter=company, purchase_status=status,
        )
        LicenseExportItemModel.objects.create(license=self.license, norm_class=norm, cif_fc=Decimal("1000"))

    def _item(self, serial, hsn, desc):
        code, _ = HSCodeModel.objects.get_or_create(hs_code=hsn)
        return LicenseImportItemsModel.objects.create(
            license=self.license, serial_number=serial, hs_code=code, description=desc,
            quantity=Decimal("100"), available_quantity=Decimal("100"), cif_fc=Decimal("100"),
        )

    def _categories(self):
        report = ItemPivotReportView().generate_report(min_balance=0, license_status="all")
        row = next(row for group in report["groups"] for row in group["licenses"] if row["license_id"] == self.license.id)
        return {cell.get("product_category") for cell in row["items"].values()}

    def test_rutile_and_borax_lines_are_classified_not_unclassified(self):
        self._item(1, "32061190", "RUTILE GRADE")
        self._item(2, "28401900", "BORAX ANHYDROUS")
        categories = self._categories()
        assert "RUTILE" in categories
        assert "BORAX" in categories
        assert "UNCLASSIFIED" not in categories
