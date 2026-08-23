"""
Regression tests: deleting a master-data Port/Company that is still
referenced by license, bill-of-entry, or allotment rows must be rejected
(ProtectedError / DRF ValidationError), never silently cascade-delete those
rows.

Covers the FK fields that were changed from on_delete=CASCADE to
on_delete=PROTECT:
    - LicenseDetailsModel.port
    - BillOfEntryModel.company / BillOfEntryModel.port
    - AllotmentModel.company / AllotmentModel.port / AllotmentModel.related_company

Also proves an *unreferenced* Port/Company can still be deleted normally,
and that deleting a referenced row leaves unrelated licenses/ports/companies
completely untouched.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel
from apps.core.models import CompanyModel, HeadSIONNormsModel, PortModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel
from apps.license.models.core import IncentiveLicense, LicenseExportItemModel

User = get_user_model()

PORTS_URL = "/api/masters/ports/"
COMPANIES_URL = "/api/masters/companies/"


def _make_license(number, port=None, **extra):
    return LicenseDetailsModel.objects.create(license_number=number, port=port, **extra)


@pytest.fixture
def superuser_client(db):
    user = User.objects.create_user(
        username="db01-regression-superuser",
        email="db01-regression-superuser@example.com",
        password="RegressionP@ss123",
    )
    user.is_superuser = True
    user.is_staff = True
    user.save(update_fields=["is_superuser", "is_staff"])
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.mark.django_db
class TestPortDeleteProtection(TestCase):
    def test_deleting_referenced_port_is_blocked_and_license_survives(self):
        port = PortModel.objects.create(name="Nhava Sheva Sea", code="INNSA1")
        license_obj = _make_license("PORT-PROT-01", port=port)

        with self.assertRaises(ProtectedError):
            port.delete()

        # Nothing was cascaded away.
        license_obj.refresh_from_db()
        assert license_obj.port_id == port.id
        assert PortModel.objects.filter(pk=port.id).exists()
        assert LicenseDetailsModel.objects.filter(pk=license_obj.id).exists()

    def test_deleting_referenced_port_via_boe_and_allotment_is_blocked(self):
        port = PortModel.objects.create(name="Chennai Sea", code="INMAA1")
        company = CompanyModel.objects.create(name="Test Importer Co", iec="IEC000001")
        boe = BillOfEntryModel.objects.create(
            company=company, port=port, bill_of_entry_number="BOE-001"
        )
        allotment = AllotmentModel.objects.create(
            company=company, port=port, item_name="Test Item"
        )

        with self.assertRaises(ProtectedError):
            port.delete()

        boe.refresh_from_db()
        allotment.refresh_from_db()
        assert boe.port_id == port.id
        assert allotment.port_id == port.id

    def test_unreferenced_port_can_still_be_deleted(self):
        port = PortModel.objects.create(name="Unused Port", code="INXXX1")
        port_id = port.id

        port.delete()

        assert not PortModel.objects.filter(pk=port_id).exists()

    def test_deleting_referenced_port_does_not_touch_unrelated_license(self):
        referenced_port = PortModel.objects.create(name="Kandla", code="INIXY1")
        other_port = PortModel.objects.create(name="Mundra", code="INMUN1")
        protected_license = _make_license("PORT-PROT-02", port=referenced_port)
        unrelated_license = _make_license("PORT-UNREL-01", port=other_port)

        with self.assertRaises(ProtectedError):
            referenced_port.delete()

        unrelated_license.refresh_from_db()
        assert unrelated_license.port_id == other_port.id
        assert PortModel.objects.filter(pk=other_port.id).exists()
        assert LicenseDetailsModel.objects.filter(pk=unrelated_license.id).exists()


@pytest.mark.django_db
class TestCompanyDeleteProtection(TestCase):
    def test_deleting_company_referenced_by_boe_is_blocked(self):
        company = CompanyModel.objects.create(name="Sigma Chemtrade", iec="IEC000002")
        boe = BillOfEntryModel.objects.create(
            company=company, bill_of_entry_number="BOE-100"
        )

        with self.assertRaises(ProtectedError):
            company.delete()

        boe.refresh_from_db()
        assert boe.company_id == company.id
        assert CompanyModel.objects.filter(pk=company.id).exists()

    def test_deleting_company_referenced_by_allotment_is_blocked(self):
        company = CompanyModel.objects.create(name="Referenced Co", iec="IEC000003")
        allotment = AllotmentModel.objects.create(company=company, item_name="Item A")

        with self.assertRaises(ProtectedError):
            company.delete()

        allotment.refresh_from_db()
        assert allotment.company_id == company.id

    def test_deleting_company_referenced_only_as_related_company_is_blocked(self):
        owner = CompanyModel.objects.create(name="Owner Co", iec="IEC000004")
        related = CompanyModel.objects.create(name="Related Co", iec="IEC000005")
        allotment = AllotmentModel.objects.create(
            company=owner, related_company=related, item_name="Item B"
        )

        with self.assertRaises(ProtectedError):
            related.delete()

        allotment.refresh_from_db()
        assert allotment.related_company_id == related.id
        # The unrelated owner company is untouched by the failed delete.
        assert CompanyModel.objects.filter(pk=owner.id).exists()

    def test_unreferenced_company_can_still_be_deleted(self):
        company = CompanyModel.objects.create(name="Never Used Co", iec="IEC000006")
        company_id = company.id

        company.delete()

        assert not CompanyModel.objects.filter(pk=company_id).exists()

    def test_deleting_referenced_company_does_not_touch_unrelated_company(self):
        referenced = CompanyModel.objects.create(name="Referenced Only", iec="IEC000007")
        unrelated = CompanyModel.objects.create(name="Totally Unrelated Co", iec="IEC000008")
        BillOfEntryModel.objects.create(
            company=referenced, bill_of_entry_number="BOE-200"
        )

        with self.assertRaises(ProtectedError):
            referenced.delete()

        assert CompanyModel.objects.filter(pk=unrelated.id).exists()

    def test_exporter_field_still_uses_set_null_and_archives_name(self):
        """Sibling FK (exporter) was already SET_NULL by design; this fix must
        not disturb that behavior."""
        company = CompanyModel.objects.create(name="Exporter Co", iec="IEC000009")
        license_obj = _make_license("EXPORTER-UNCHANGED-01")
        license_obj.exporter = company
        license_obj.save(update_fields=["exporter"])

        company.delete()

        license_obj.refresh_from_db()
        assert license_obj.exporter_id is None
        assert license_obj.archived_exporter_name == "Exporter Co"


@pytest.mark.django_db
class TestMasterViewSetApiDeleteProtection(TestCase):
    """End-to-end proof through the actual exposed DELETE endpoints
    (MasterViewSet.perform_destroy), not just the model layer: a referenced
    Port/Company must come back as an HTTP 400 ValidationError, never a 500
    or a completed 204 that quietly cascaded."""

    def setUp(self):
        user = User.objects.create_user(
            username="db01-api-superuser",
            email="db01-api-superuser@example.com",
            password="RegressionP@ss123",
        )
        user.is_superuser = True
        user.is_staff = True
        user.save(update_fields=["is_superuser", "is_staff"])
        token = RefreshToken.for_user(user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def test_delete_referenced_port_via_api_returns_400_not_500_or_204(self):
        port = PortModel.objects.create(name="API Referenced Port", code="INAPI01")
        license_obj = _make_license("API-PORT-PROT-01", port=port)

        response = self.client.delete(f"{PORTS_URL}{port.id}/")

        assert response.status_code == 400, response.content
        assert "detail" in response.json()
        assert "LicenseDetailsModel" in response.json()["detail"] or "license" in response.json()["detail"].lower()
        assert PortModel.objects.filter(pk=port.id).exists()
        license_obj.refresh_from_db()
        assert license_obj.port_id == port.id

    def test_delete_unreferenced_port_via_api_still_succeeds(self):
        port = PortModel.objects.create(name="API Unreferenced Port", code="INAPI02")

        response = self.client.delete(f"{PORTS_URL}{port.id}/")

        assert response.status_code == 204, response.content
        assert not PortModel.objects.filter(pk=port.id).exists()

    def test_delete_referenced_company_via_api_returns_400_not_500_or_204(self):
        company = CompanyModel.objects.create(name="API Referenced Co", iec="IECAPI001")
        boe = BillOfEntryModel.objects.create(company=company, bill_of_entry_number="BOE-API-01")

        response = self.client.delete(f"{COMPANIES_URL}{company.id}/")

        assert response.status_code == 400, response.content
        assert CompanyModel.objects.filter(pk=company.id).exists()
        boe.refresh_from_db()
        assert boe.company_id == company.id

    def test_delete_unreferenced_company_via_api_still_succeeds(self):
        company = CompanyModel.objects.create(name="API Unreferenced Co", iec="IECAPI002")

        response = self.client.delete(f"{COMPANIES_URL}{company.id}/")

        assert response.status_code == 204, response.content
        assert not CompanyModel.objects.filter(pk=company.id).exists()


@pytest.mark.django_db
class TestDeleteProtectionRegressionScope(TestCase):
    """Broader regression scope beyond the originally-cited port/company:
    prove the PROTECT behavior is uniform across many independent
    companies/ports, is insensitive to license issue date, and that the fix
    did NOT reach into sibling FKs (norm_class, IncentiveLicense) that were
    intentionally left untouched."""

    def test_protection_holds_across_several_independent_companies(self):
        """Each company below is unrelated to the others; deleting one
        referenced company must fail without disturbing any of the others,
        and a same-shaped but genuinely unused company must still delete."""
        referenced_companies = []
        for i in range(5):
            company = CompanyModel.objects.create(name=f"Scope Co {i}", iec=f"IECSC{i:03d}X")
            BillOfEntryModel.objects.create(company=company, bill_of_entry_number=f"BOE-SCOPE-{i}")
            referenced_companies.append(company)

        unused_company = CompanyModel.objects.create(name="Scope Unused Co", iec="IECSCOPEU1")

        for company in referenced_companies:
            with self.assertRaises(ProtectedError):
                company.delete()

        # None of the referenced companies were touched by any of the failed deletes.
        for company in referenced_companies:
            assert CompanyModel.objects.filter(pk=company.id).exists()

        # An unrelated, genuinely unreferenced company is unaffected by the
        # protection logic and can still be removed normally.
        unused_company.delete()
        assert not CompanyModel.objects.filter(pk=unused_company.id).exists()

    def test_protection_holds_regardless_of_license_issue_date(self):
        """The PROTECT constraint is date-agnostic: an old, a current, and a
        far-future licensed reference to the same port must all block the
        delete identically."""
        port = PortModel.objects.create(name="Scope Date Port", code="INSCOPD1")
        old_license = _make_license(
            "SCOPE-DATE-OLD", port=port, registration_date=date(2005, 4, 1)
        )
        current_license = _make_license(
            "SCOPE-DATE-CUR", port=port, registration_date=date(2026, 8, 7)
        )
        future_license = _make_license(
            "SCOPE-DATE-FUT", port=port, registration_date=date(2040, 1, 1)
        )

        with self.assertRaises(ProtectedError):
            port.delete()

        for lic in (old_license, current_license, future_license):
            lic.refresh_from_db()
            assert lic.port_id == port.id
        assert PortModel.objects.filter(pk=port.id).exists()

    def test_sibling_norm_class_fk_was_not_touched_by_this_fix(self):
        """LicenseExportItemModel.norm_class -> SionNormClassModel is a
        different, out-of-scope FK (not cited in DB-01) and was deliberately
        left as CASCADE. This pins that the PROTECT change was scoped only
        to the six Port/Company FKs and did not blanket-change every
        optional FK in the app."""
        head = HeadSIONNormsModel.objects.create(name="SCOPE-HEAD")
        norm = SionNormClassModel.objects.create(head_norm=head, norm_class="ZSCOPE01")
        license_obj = _make_license("SCOPE-NORM-01")
        LicenseExportItemModel.objects.create(license=license_obj, norm_class=norm)

        # Unaffected behavior: still cascades exactly as before this fix.
        norm.delete()

        assert not SionNormClassModel.objects.filter(pk=norm.id).exists()
        assert not LicenseExportItemModel.objects.filter(license=license_obj).exists()
        assert LicenseDetailsModel.objects.filter(pk=license_obj.id).exists()

    def test_incentive_license_company_and_port_fks_are_unaffected_out_of_scope(self):
        """IncentiveLicense (RODTEP/ROSTL/MEIS) is a different license_type
        family from the main LicenseDetailsModel and was not part of the
        DB-01 finding or fix -- its exporter/port_code FKs are still
        on_delete=CASCADE. This is a real coverage gap (same bug class,
        different model) but out of scope for this fix; pinned here so a
        future change to this FK is a deliberate decision, not silent."""
        company = CompanyModel.objects.create(name="Incentive Co", iec="IECINCV001")
        port = PortModel.objects.create(name="Incentive Port", code="ININCV01")
        incentive = IncentiveLicense.objects.create(
            license_type="RODTEP",
            license_number="INCV-REG-01",
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2028, 1, 1),
            exporter=company,
            port_code=port,
        )

        company.delete()

        assert not CompanyModel.objects.filter(pk=company.id).exists()
        assert not IncentiveLicense.objects.filter(pk=incentive.id).exists()

    def test_makemigrations_has_no_unapplied_model_changes(self):
        """Guards against model/migration drift: the on_delete=PROTECT
        change on the six FKs must be fully captured by the three migrations
        already generated for this fix (license/0017, bill_of_entry/0006,
        allotment/0004) -- makemigrations --check should find nothing left
        to generate."""
        # Returns exit code 1 (raises SystemExit) if there ARE pending
        # changes; 0 (no exception) if the migration state already matches
        # the models.
        call_command("makemigrations", "--check", "--dry-run", verbosity=0)
