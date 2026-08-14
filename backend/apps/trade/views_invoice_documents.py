"""Secure bearer-token invoice document viewer."""

from __future__ import annotations

import mimetypes

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.trade.models import InvoiceDocumentAccessToken, InvoiceDocumentAuditEvent
from apps.trade.services.invoice_secure_links import (
    canonical_company_for_trade,
    document_matches_trade,
    token_digest,
)


def _audit(access, event, request, **metadata):
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    InvoiceDocumentAuditEvent.objects.create(
        event=event,
        trade=access.trade,
        access_token=access,
        user=user,
        metadata=metadata,
    )


def _gone():
    return JsonResponse({"detail": "Invoice Link Expired"}, status=410)


class InvoiceDocumentView(APIView):
    """Stream the protected file; exactly two successful responses per token."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        digest = token_digest(token)
        try:
            access = InvoiceDocumentAccessToken.objects.select_related(
                "trade", "authorized_company", "issued_to"
            ).get(token_hash=digest)
        except InvoiceDocumentAccessToken.DoesNotExist:
            # Do not disclose whether a guessed token resembles a real object.
            raise Http404()

        now = timezone.now()
        if access.expires_at <= now or access.view_count >= access.max_views:
            _audit(access, InvoiceDocumentAuditEvent.EVENT_EXPIRED, request, reason="expired_or_consumed")
            return _gone()

        canonical_company = canonical_company_for_trade(access.trade)
        if not canonical_company or canonical_company.id != access.authorized_company_id:
            _audit(access, InvoiceDocumentAuditEvent.EVENT_FORBIDDEN, request, reason="company_context_changed")
            raise Http404()

        if not document_matches_trade(
            trade=access.trade,
            document_type=access.document_type,
            storage_name=access.storage_name,
            document_version=access.document_version,
        ):
            _audit(access, InvoiceDocumentAuditEvent.EVENT_FORBIDDEN, request, reason="document_context_changed")
            raise Http404()

        # If an authenticated identity accompanies the bearer token it may not
        # substitute a different user/company.  Anonymous access remains valid
        # because the high-entropy, short-lived URL itself is the PDF/Excel-safe
        # capability (browsers cannot attach the SPA's Authorization header).
        user = request.user if getattr(request.user, "is_authenticated", False) else None
        if user and not user.is_superuser:
            if user.id != access.issued_to_id or user.company_id != access.authorized_company_id:
                _audit(access, InvoiceDocumentAuditEvent.EVENT_FORBIDDEN, request, reason="identity_mismatch")
                raise Http404()

        if not default_storage.exists(access.storage_name):
            # A missing/deleted object is not a successful view and consumes no use.
            raise Http404()
        file_handle = default_storage.open(access.storage_name, "rb")

        # The conditional UPDATE is the concurrency primitive.  At count=1,
        # two racing requests can open the file, but only one can claim view #2.
        with transaction.atomic():
            claimed = InvoiceDocumentAccessToken.objects.filter(
                pk=access.pk,
                expires_at__gt=now,
                view_count__lt=F("max_views"),
            ).update(view_count=F("view_count") + 1, last_viewed_at=now)
        if claimed != 1:
            file_handle.close()
            access.refresh_from_db(fields=["view_count", "expires_at"])
            _audit(access, InvoiceDocumentAuditEvent.EVENT_EXPIRED, request, reason="concurrent_limit")
            return _gone()

        event = (
            InvoiceDocumentAuditEvent.EVENT_PURCHASE_VIEWED
            if access.document_type == InvoiceDocumentAccessToken.TYPE_PURCHASE_UPLOADED
            else InvoiceDocumentAuditEvent.EVENT_SALE_VIEWED
        )
        _audit(access, event, request, signed=access.signed, document_version=access.document_version)
        content_type = mimetypes.guess_type(access.storage_name)[0] or "application/octet-stream"
        return FileResponse(file_handle, content_type=content_type, as_attachment=False)
