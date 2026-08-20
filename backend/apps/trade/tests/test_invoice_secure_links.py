from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import CompanyModel
from apps.trade.models import (
    InvoiceDocumentAccessToken,
    InvoiceDocumentAuditEvent,
    LicenseTrade,
)
from apps.trade.services.invoice_secure_links import issue_invoice_view_link


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def invoice_context(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    company = CompanyModel.objects.create(name="Ledger Buyer", iec="LEDGERBUY1")
    outsider = CompanyModel.objects.create(name="Other Company", iec="OTHERCOMP1")
    user = User.objects.create_user(
        username="invoice-viewer", email="invoice-viewer@example.com", password="x", company=company
    )
    group, _ = Group.objects.get_or_create(name="TRADE_VIEWER")
    user.groups.add(group)
    other_user = User.objects.create_user(
        username="outside-viewer", email="outside-viewer@example.com", password="x", company=outsider
    )
    other_user.groups.add(group)
    supplier = CompanyModel.objects.create(name="Supplier", iec="SUPPLIER1")
    trade = LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_PURCHASE,
        from_company=supplier,
        to_company=company,
        invoice_number="P-SECURE-1",
        invoice_date=timezone.now().date(),
    )
    storage_name = default_storage.save("trade/purchase_invoices/secure.pdf", ContentFile(b"%PDF-secure"))
    trade.purchase_invoice_copy = storage_name
    trade.save(update_fields=["purchase_invoice_copy"])
    return user, other_user, trade, storage_name


def _issue(ctx, **overrides):
    user, _, trade, storage_name = ctx
    values = {
        "trade": trade,
        "storage_name": storage_name,
        "document_type": InvoiceDocumentAccessToken.TYPE_PURCHASE_UPLOADED,
        "user": user,
    }
    values.update(overrides)
    return issue_invoice_view_link(**values)


def _consume(response):
    try:
        if getattr(response, "streaming", False):
            b"".join(response.streaming_content)
    finally:
        # FileResponse owns the storage handle until its response lifecycle is
        # closed.  Test clients do not do that automatically after consuming a
        # stream, unlike the production WSGI/ASGI server.
        response.close()


def test_raw_token_and_storage_path_are_never_persisted_or_exposed(invoice_context):
    result = _issue(invoice_context)
    token = result["secure_url"].rstrip("/").rsplit("/", 1)[-1]
    access = InvoiceDocumentAccessToken.objects.get()

    assert token not in access.token_hash
    assert len(access.token_hash) == 64
    assert access.storage_name not in result["secure_url"]
    assert f"/{access.trade_id}/" not in result["secure_url"]
    assert APIClient().get(result["secure_url"] + "tampered").status_code == 404
    access.refresh_from_db()
    assert access.view_count == 0


def test_two_successful_views_then_gone_and_audited(invoice_context):
    url = _issue(invoice_context)["secure_url"]
    client = APIClient()

    first = client.get(url)
    assert first.status_code == 200
    _consume(first)
    second = client.get(url)
    assert second.status_code == 200
    _consume(second)
    third = client.get(url)
    assert third.status_code == 410
    assert third.json() == {"detail": "Invoice Link Expired"}

    access = InvoiceDocumentAccessToken.objects.get()
    assert access.view_count == 2
    assert InvoiceDocumentAuditEvent.objects.filter(
        event=InvoiceDocumentAuditEvent.EVENT_PURCHASE_VIEWED
    ).count() == 2
    assert InvoiceDocumentAuditEvent.objects.filter(
        event=InvoiceDocumentAuditEvent.EVENT_EXPIRED
    ).exists()


def test_expired_or_missing_document_does_not_consume_view(invoice_context):
    result = _issue(invoice_context)
    access = InvoiceDocumentAccessToken.objects.get()
    access.expires_at = timezone.now() - timedelta(seconds=1)
    access.save(update_fields=["expires_at"])
    assert APIClient().get(result["secure_url"]).status_code == 410
    access.refresh_from_db()
    assert access.view_count == 0

    access.expires_at = timezone.now() + timedelta(minutes=1)
    access.storage_name = "trade/purchase_invoices/deleted.pdf"
    access.save(update_fields=["expires_at", "storage_name"])
    assert APIClient().get(result["secure_url"]).status_code == 404
    access.refresh_from_db()
    assert access.view_count == 0


def test_cross_company_issue_and_authenticated_replay_are_blocked(invoice_context):
    user, other_user, trade, storage_name = invoice_context
    with pytest.raises(Exception) as exc:
        issue_invoice_view_link(
            trade=trade,
            storage_name=storage_name,
            document_type=InvoiceDocumentAccessToken.TYPE_PURCHASE_UPLOADED,
            user=other_user,
        )
    assert "Cross-company" in str(exc.value)

    url = _issue(invoice_context)["secure_url"]
    client = APIClient()
    client.force_authenticate(other_user)
    assert client.get(url).status_code == 404
    assert InvoiceDocumentAccessToken.objects.get().view_count == 0
    assert InvoiceDocumentAuditEvent.objects.filter(
        event=InvoiceDocumentAuditEvent.EVENT_FORBIDDEN
    ).exists()


def test_changed_trade_company_invalidates_token_without_consuming(invoice_context):
    _, _, trade, _ = invoice_context
    url = _issue(invoice_context)["secure_url"]
    replacement = CompanyModel.objects.create(name="Replacement", iec="REPLACE01")
    trade.to_company = replacement
    trade.save(update_fields=["to_company"])

    assert APIClient().get(url).status_code == 404
    assert InvoiceDocumentAccessToken.objects.get().view_count == 0


def test_concurrent_second_view_has_one_success_and_one_gone(invoice_context):
    url = _issue(invoice_context)["secure_url"]
    first = APIClient().get(url)
    assert first.status_code == 200
    _consume(first)

    def request_once():
        response = APIClient().get(url)
        status = response.status_code
        _consume(response)
        return status

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda _: request_once(), range(2)))

    assert statuses == [200, 410]
    access = InvoiceDocumentAccessToken.objects.get()
    assert access.view_count == 2
