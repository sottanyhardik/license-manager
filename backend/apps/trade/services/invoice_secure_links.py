"""Opaque, expiring, two-view links for invoice documents.

This module is transport/security only.  It deliberately does not decide how
purchase documents are resolved or how sale invoices are calculated/rendered.
The canonical invoice service supplies the already-selected storage object.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import TradePermission
from apps.trade.models import InvoiceDocumentAccessToken, LicenseTrade, TradeInvoiceDocument


DEFAULT_TTL_SECONDS = 15 * 60
MAX_SUCCESSFUL_VIEWS = 2
INVOICE_READ_ROLES = set(TradePermission.required_roles_for_read) | {
    "LICENSE_MANAGER", "LEDGER_MANAGER"
}


def token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def canonical_company_for_trade(trade: LicenseTrade):
    """Return the internal company whose ledger owns this invoice."""
    if trade.direction == LicenseTrade.DIR_PURCHASE:
        return trade.to_company
    if trade.direction == LicenseTrade.DIR_SALE:
        return trade.from_company
    return trade.to_company or trade.from_company


def _assert_can_issue(user) -> None:
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")
    if user.is_superuser:
        return
    if not user.has_any_role(INVOICE_READ_ROLES):
        raise PermissionDenied("Trade invoice access is not permitted.")


def document_matches_trade(*, trade, document_type, storage_name, document_version="") -> bool:
    """Fail closed unless the storage object is still owned by this trade."""
    if document_type == InvoiceDocumentAccessToken.TYPE_PURCHASE_UPLOADED:
        purchase_names = {
            field.name
            for field in (trade.purchase_invoice_copy,)
            if field
        }
        return bool(
            trade.direction == LicenseTrade.DIR_PURCHASE
            and storage_name in purchase_names
        )
    if document_type == InvoiceDocumentAccessToken.TYPE_SALE_GENERATED:
        return bool(
            trade.direction == LicenseTrade.DIR_SALE
            and TradeInvoiceDocument.objects.filter(
                trade=trade,
                file=storage_name,
                version_hash=document_version,
            ).exists()
        )
    return False


def issue_invoice_view_link(
    *,
    trade: LicenseTrade,
    storage_name: str,
    document_type: str,
    user,
    signed: bool = False,
    document_version: str = "",
    base_url: str = "",
    ttl_seconds: int | None = None,
) -> dict:
    """Issue a bearer link without persisting or returning a storage path.

    The raw random token exists only in the returned URL.  Callers should put
    this URL in the canonical invoice-document metadata shared by UI/PDF/Excel.
    """
    valid_types = dict(InvoiceDocumentAccessToken.DOCUMENT_TYPE_CHOICES)
    if document_type not in valid_types:
        raise ValidationError("Unsupported invoice document type.")
    if not storage_name:
        raise ValidationError("An invoice document is required.")
    if not document_matches_trade(
        trade=trade,
        document_type=document_type,
        storage_name=storage_name,
        document_version=document_version,
    ):
        raise ValidationError("Invoice document does not belong to this trade/version.")

    company = canonical_company_for_trade(trade)
    _assert_can_issue(user)

    lifetime = ttl_seconds
    if lifetime is None:
        lifetime = getattr(settings, "INVOICE_DOCUMENT_LINK_TTL_SECONDS", DEFAULT_TTL_SECONDS)
    if not isinstance(lifetime, int) or lifetime <= 0:
        raise ValidationError("Invoice document link lifetime must be positive.")

    raw = secrets.token_urlsafe(32)
    access = InvoiceDocumentAccessToken.objects.create(
        token_hash=token_digest(raw),
        trade=trade,
        document_type=document_type,
        storage_name=storage_name,
        document_version=document_version or "",
        signed=signed,
        issued_to=user,
        authorized_company=company,
        expires_at=timezone.now() + timedelta(seconds=lifetime),
        max_views=MAX_SUCCESSFUL_VIEWS,
    )
    relative = reverse("trade:invoice-document-view", kwargs={"token": raw})
    secure_url = urljoin(base_url.rstrip("/") + "/", relative.lstrip("/")) if base_url else relative
    return {
        "secure_url": secure_url,
        "expires_at": access.expires_at,
        "max_views": access.max_views,
    }
