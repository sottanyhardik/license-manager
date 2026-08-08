"""
Regression tests for ProtectedMediaView's per-document RBAC check.

Authentication alone used to gate ``GET /api/media/<path>``. Because licence
copies, BOE PDFs and trade purchase-invoice copies are stored at
business-identifier-keyed (predictable) paths, any authenticated user —
regardless of role — could fetch another team's confidential document
directly through the media endpoint even though the equivalent REST endpoint
(``LicensePermission`` / ``BillOfEntryPermission`` / ``TradePermission``)
would have blocked them.

These tests prove:
  - a role with no read access to a document type is blocked on both the
    normal REST endpoint AND the media endpoint for that document type;
  - the matching role set can still stream the same file (no regression);
  - a role that's valid for one document type but not another is blocked on
    the other's media path (cross-domain check);
  - paths outside the business-document prefixes this fix targets keep the
    original "any authenticated user" behavior (no unrelated regression);
  - a file left on disk with no owning row is blocked for everyone but a
    superuser (fails closed, not open).
"""
from datetime import date

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.bill_of_entry.models import BillOfEntryModel
from apps.core.models import CompanyModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseDocumentModel
from apps.trade.models import LicenseTrade

pytestmark = pytest.mark.django_db


def _make_user(username, roles=()):
    from apps.accounts.models import User

    user = User.objects.create_user(username=username, email=f"{username}@example.com", password="x")
    for role in roles:
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
    return user


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _write(media_root, rel_path, content=b"%PDF-1.4 fake\n"):
    full = media_root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)
    return rel_path


@pytest.fixture(autouse=True)
def dev_media(settings, tmp_path):
    # Force the direct-stream (no X-Accel-Redirect) branch and confine all
    # test fixtures to a throwaway tmp dir instead of the real MEDIA_ROOT.
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_X_ACCEL_REDIRECT = ""
    return tmp_path


class TestLicenseDocumentAccess:
    def _make_doc(self, media_root):
        license_obj = LicenseDetailsModel.objects.create(license_number="0510099999")
        rel = _write(media_root, "licenses/0510099999/0510099999 Copy.pdf")
        LicenseDocumentModel.objects.create(license=license_obj, type="LICENSE COPY", file=rel)
        return rel

    def test_role_without_license_access_is_blocked_like_the_rest_endpoint(self, dev_media):
        rel = self._make_doc(dev_media)
        user = _make_user("incentive_only", roles=["INCENTIVE_LICENSE_VIEWER"])
        client = _client_for(user)

        assert client.get("/api/licenses/").status_code == 403
        assert client.get(f"/api/media/{rel}").status_code == 404

    def test_license_viewer_can_still_download(self, dev_media):
        rel = self._make_doc(dev_media)
        user = _make_user("license_viewer", roles=["LICENSE_VIEWER"])
        client = _client_for(user)

        assert client.get(f"/api/media/{rel}").status_code == 200

    def test_superuser_can_always_download(self, dev_media):
        rel = self._make_doc(dev_media)
        from apps.accounts.models import User

        admin = User.objects.create_superuser(username="admin1", email="admin1@example.com", password="x")
        client = _client_for(admin)

        assert client.get(f"/api/media/{rel}").status_code == 200


class TestBillOfEntryDocumentAccess:
    def _make_doc(self, media_root):
        company = CompanyModel.objects.create(iec="IEC000123", name="Test Importer")
        port = PortModel.objects.create(name="Test Port", code="TPX1")
        rel = _write(media_root, "boe_copies/BOE-9001.pdf")
        BillOfEntryModel.objects.create(
            company=company, port=port, bill_of_entry_number="BOE-9001",
            boe_pdf_copy=rel,
        )
        return rel

    def test_license_only_role_cannot_reach_boe_pdf(self, dev_media):
        # LICENSE_VIEWER isn't in BillOfEntryPermission's read-role set —
        # cross-domain check that a licence-only role can't ride the media
        # endpoint into BOE documents.
        rel = self._make_doc(dev_media)
        user = _make_user("license_only", roles=["LICENSE_VIEWER"])
        client = _client_for(user)

        assert client.get(f"/api/media/{rel}").status_code == 404

    def test_boe_viewer_can_download(self, dev_media):
        rel = self._make_doc(dev_media)
        user = _make_user("boe_viewer", roles=["BOE_VIEWER"])
        client = _client_for(user)

        assert client.get(f"/api/media/{rel}").status_code == 200


class TestTradeDocumentAccess:
    def _make_doc(self, media_root):
        from_company = CompanyModel.objects.create(iec="IEC000456", name="From Co")
        to_company = CompanyModel.objects.create(iec="IEC000789", name="To Co")
        rel = _write(media_root, "trade/purchase_invoices/INV-001.pdf")
        LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            license_type="INCENTIVE",
            from_company=from_company,
            to_company=to_company,
            invoice_number="INV-001",
            invoice_date=date(2026, 1, 15),
            purchase_invoice_copy=rel,
        )
        return rel

    def test_license_only_role_cannot_reach_trade_invoice(self, dev_media):
        rel = self._make_doc(dev_media)
        user = _make_user("license_only2", roles=["LICENSE_VIEWER"])
        client = _client_for(user)

        assert client.get(f"/api/media/{rel}").status_code == 404

    def test_trade_viewer_can_download(self, dev_media):
        rel = self._make_doc(dev_media)
        user = _make_user("trade_viewer", roles=["TRADE_VIEWER"])
        client = _client_for(user)

        assert client.get(f"/api/media/{rel}").status_code == 200


class TestUnaffectedAndOrphanPaths:
    def test_prefix_outside_business_docs_keeps_authenticated_only_access(self, dev_media):
        # e.g. company branding assets — out of scope for this fix, must
        # keep the original "any authenticated user" behavior unchanged.
        rel = _write(dev_media, "entity_logos/logo.png", content=b"\x89PNG\r\n")
        user = _make_user("no_roles_at_all", roles=[])
        client = _client_for(user)

        assert client.get(f"/api/media/{rel}").status_code == 200

    def test_orphaned_file_under_protected_prefix_is_blocked(self, dev_media):
        # File left on disk with no owning LicenseDocumentModel row (e.g. the
        # row was deleted, or an upload glitch never linked one). No role can
        # establish ownership, so this must fail closed, not open.
        rel = _write(dev_media, "licenses/9999999999/9999999999 Copy.pdf")
        user = _make_user("license_manager_orphan", roles=["LICENSE_MANAGER"])
        client = _client_for(user)

        assert client.get(f"/api/media/{rel}").status_code == 404


class TestRegressionScopeBeyondTheOriginalLicense:
    """SEC-01 regression sweep: the fix's role lookup only keys off the file's
    exact stored path (via an owning-row lookup), never off which company,
    licence norm/type, or date the owning record happens to have. These tests
    prove the gate behaves identically across companies, norm/license types
    and date ranges — i.e. the fix isn't accidentally narrow to the one
    licence (0510099999) used in the original finding/exploit repro.
    """

    def test_unaffected_companies_both_gated_the_same_way(self, dev_media):
        # Two licences owned by two different exporter companies. A role
        # without LicensePermission read access must be blocked on *both*;
        # a role with it must be let through on *both* — access must not
        # depend on which company owns the underlying licence.
        exporter_a = CompanyModel.objects.create(iec="IEC0AAA001", name="Exporter A Pvt Ltd")
        exporter_b = CompanyModel.objects.create(iec="IEC0BBB002", name="Exporter B Pvt Ltd")

        license_a = LicenseDetailsModel.objects.create(license_number="0510011111", exporter=exporter_a)
        license_b = LicenseDetailsModel.objects.create(license_number="0510022222", exporter=exporter_b)

        rel_a = _write(dev_media, "licenses/0510011111/0510011111 Copy.pdf")
        rel_b = _write(dev_media, "licenses/0510022222/0510022222 Copy.pdf")
        LicenseDocumentModel.objects.create(license=license_a, type="LICENSE COPY", file=rel_a)
        LicenseDocumentModel.objects.create(license=license_b, type="LICENSE COPY", file=rel_b)

        blocked_user = _make_user("cross_company_blocked", roles=["INCENTIVE_LICENSE_VIEWER"])
        blocked_client = _client_for(blocked_user)
        assert blocked_client.get(f"/api/media/{rel_a}").status_code == 404
        assert blocked_client.get(f"/api/media/{rel_b}").status_code == 404

        allowed_user = _make_user("cross_company_allowed", roles=["LICENSE_VIEWER"])
        allowed_client = _client_for(allowed_user)
        assert allowed_client.get(f"/api/media/{rel_a}").status_code == 200
        assert allowed_client.get(f"/api/media/{rel_b}").status_code == 200

    def test_unaffected_license_document_types_all_gated_the_same_way(self, dev_media):
        # LicenseDocumentModel.type varies (LICENSE COPY / TRANSFER LETTER /
        # OTHER) independently of the role check, which only resolves the
        # owning LicenseDetailsModel and never inspects `type`.
        license_obj = LicenseDetailsModel.objects.create(license_number="0510033333")
        rel_copy = _write(dev_media, "licenses/0510033333/copy.pdf")
        rel_tl = _write(dev_media, "licenses/0510033333/transfer_letter.pdf")
        rel_other = _write(dev_media, "licenses/0510033333/other.pdf")
        LicenseDocumentModel.objects.create(license=license_obj, type="LICENSE COPY", file=rel_copy)
        LicenseDocumentModel.objects.create(license=license_obj, type="TRANSFER LETTER", file=rel_tl)
        LicenseDocumentModel.objects.create(license=license_obj, type="OTHER", file=rel_other)

        blocked_user = _make_user("doc_type_blocked", roles=["INCENTIVE_LICENSE_VIEWER"])
        blocked_client = _client_for(blocked_user)
        for rel in (rel_copy, rel_tl, rel_other):
            assert blocked_client.get(f"/api/media/{rel}").status_code == 404

        allowed_user = _make_user("doc_type_allowed", roles=["LICENSE_VIEWER"])
        allowed_client = _client_for(allowed_user)
        for rel in (rel_copy, rel_tl, rel_other):
            assert allowed_client.get(f"/api/media/{rel}").status_code == 200

    def test_unaffected_trade_license_types_dfia_and_incentive_gated_the_same_way(self, dev_media):
        # LicenseTrade.license_type (DFIA vs INCENTIVE) is a different axis
        # from the role check, which only resolves ownership via the file
        # field, not license_type.
        from_company = CompanyModel.objects.create(iec="IEC0CCC003", name="From Co Norms")
        to_company = CompanyModel.objects.create(iec="IEC0DDD004", name="To Co Norms")

        rel_dfia = _write(dev_media, "trade/purchase_invoices/INV-DFIA-001.pdf")
        rel_incentive = _write(dev_media, "trade/purchase_invoices/INV-INC-001.pdf")
        LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            license_type=LicenseTrade.LICENSE_TYPE_DFIA,
            from_company=from_company,
            to_company=to_company,
            invoice_number="INV-DFIA-001",
            invoice_date=date(2020, 4, 1),
            purchase_invoice_copy=rel_dfia,
        )
        LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            license_type=LicenseTrade.LICENSE_TYPE_INCENTIVE,
            from_company=from_company,
            to_company=to_company,
            invoice_number="INV-INC-001",
            invoice_date=date(2026, 1, 15),
            purchase_invoice_copy=rel_incentive,
        )

        blocked_user = _make_user("trade_norm_blocked", roles=["LICENSE_VIEWER"])
        blocked_client = _client_for(blocked_user)
        assert blocked_client.get(f"/api/media/{rel_dfia}").status_code == 404
        assert blocked_client.get(f"/api/media/{rel_incentive}").status_code == 404

        allowed_user = _make_user("trade_norm_allowed", roles=["TRADE_VIEWER"])
        allowed_client = _client_for(allowed_user)
        assert allowed_client.get(f"/api/media/{rel_dfia}").status_code == 200
        assert allowed_client.get(f"/api/media/{rel_incentive}").status_code == 200

    def test_unaffected_date_ranges_old_and_future_boes_gated_the_same_way(self, dev_media):
        # BillOfEntryModel.bill_of_entry_date spans a very old date and a
        # future-dated one; the role check never looks at the date, only at
        # the owning row resolved via boe_pdf_copy.
        company = CompanyModel.objects.create(iec="IEC0EEE005", name="Date Range Importer")
        port = PortModel.objects.create(name="Date Range Port", code="DRP1")

        rel_old = _write(dev_media, "boe_copies/BOE-OLD-2001.pdf")
        rel_future = _write(dev_media, "boe_copies/BOE-FUTURE-2099.pdf")
        BillOfEntryModel.objects.create(
            company=company, port=port, bill_of_entry_number="BOE-OLD-2001",
            bill_of_entry_date=date(2001, 1, 1), boe_pdf_copy=rel_old,
        )
        BillOfEntryModel.objects.create(
            company=company, port=port, bill_of_entry_number="BOE-FUTURE-2099",
            bill_of_entry_date=date(2099, 12, 31), boe_pdf_copy=rel_future,
        )

        blocked_user = _make_user("boe_date_blocked", roles=["LICENSE_VIEWER"])
        blocked_client = _client_for(blocked_user)
        assert blocked_client.get(f"/api/media/{rel_old}").status_code == 404
        assert blocked_client.get(f"/api/media/{rel_future}").status_code == 404

        allowed_user = _make_user("boe_date_allowed", roles=["BOE_VIEWER"])
        allowed_client = _client_for(allowed_user)
        assert allowed_client.get(f"/api/media/{rel_old}").status_code == 200
        assert allowed_client.get(f"/api/media/{rel_future}").status_code == 200

    def test_unaffected_license_date_ranges_gated_the_same_way(self, dev_media):
        # LicenseDetailsModel.license_date spans an old and a recent licence;
        # the role check must be indifferent to it.
        old_license = LicenseDetailsModel.objects.create(
            license_number="0510044444", license_date=date(2010, 6, 1),
        )
        recent_license = LicenseDetailsModel.objects.create(
            license_number="0510055555", license_date=date(2026, 7, 1),
        )
        rel_old = _write(dev_media, "licenses/0510044444/0510044444 Copy.pdf")
        rel_recent = _write(dev_media, "licenses/0510055555/0510055555 Copy.pdf")
        LicenseDocumentModel.objects.create(license=old_license, type="LICENSE COPY", file=rel_old)
        LicenseDocumentModel.objects.create(license=recent_license, type="LICENSE COPY", file=rel_recent)

        blocked_user = _make_user("license_date_blocked", roles=["INCENTIVE_LICENSE_VIEWER"])
        blocked_client = _client_for(blocked_user)
        assert blocked_client.get(f"/api/media/{rel_old}").status_code == 404
        assert blocked_client.get(f"/api/media/{rel_recent}").status_code == 404

        allowed_user = _make_user("license_date_allowed", roles=["LICENSE_VIEWER"])
        allowed_client = _client_for(allowed_user)
        assert allowed_client.get(f"/api/media/{rel_old}").status_code == 200
        assert allowed_client.get(f"/api/media/{rel_recent}").status_code == 200
