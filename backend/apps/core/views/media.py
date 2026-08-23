"""Authenticated media/document downloads.

SECURITY (CRITICAL): historically nginx served the entire ``/media/`` tree
publicly (``location /media/`` with ``alias`` + ``Cache-Control: public``), so any
BOE PDF, licence copy, ledger file or generated transfer-letter — customs
documents and PII — was downloadable by anyone who could guess the URL (paths are
highly predictable, e.g. ``TL_<bill_of_entry_number>_<name>/``). That bypassed
every DRF permission class (IDOR at the web-server layer).

This view is the replacement: media is served only to an authenticated request.
Because the storage paths for licence copies, BOE PDFs and trade invoices are
themselves business-identifier-keyed and therefore predictable, authentication
alone isn't enough for those prefixes — ``get()`` also resolves the owning
record and re-applies the same read-role set the corresponding REST endpoint
(``LicensePermission`` / ``BillOfEntryPermission`` / ``TradePermission``)
enforces, so a role that the normal API blocks can't reach the document either.

In production nginx should serve the bytes efficiently via ``X-Accel-Redirect``
from an ``internal;`` location (zero bytes through Django); in development (no
nginx) Django streams the file directly. See ``nginx-protected-media.conf`` and
the activation runbook in ``docs/08-security.md``.
"""
import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import (
    BillOfEntryPermission,
    LicensePermission,
    TradePermission,
)


def _required_read_roles(rel_path):
    """Return the read-role set gating the business object that owns ``rel_path``.

    ``rel_path`` is the file's path relative to ``MEDIA_ROOT`` (forward slashes,
    no leading ``./``). Mirrors the role sets ``LicensePermission`` /
    ``BillOfEntryPermission`` / ``TradePermission`` already enforce for the
    matching REST endpoints, keyed off the same ``upload_to`` prefixes those
    models use:

    - ``licenses/...``          -> ``LicenseDocumentModel`` (licence copy / TL / other)
    - ``boe_copies/...``        -> ``BillOfEntryModel`` (ICEGATE BOE PDF)
    - ``trade/...``             -> ``LicenseTrade`` (purchase invoice copy)

    Returns ``None`` when ``rel_path`` doesn't fall under one of those
    prefixes (e.g. company branding assets) — those keep the original
    "any authenticated user" behavior, unchanged by this check. Returns an
    empty list (nobody but a superuser passes) when the prefix is one of the
    protected ones above but no owning row references this exact path — e.g.
    a stale file left behind after its record was deleted — since ownership,
    and therefore the correct role, can't be established.
    """
    if rel_path.startswith("licenses/"):
        from apps.license.models import LicenseDocumentModel

        if not LicenseDocumentModel.objects.filter(file=rel_path).exists():
            return []
        return LicensePermission.required_roles_for_read

    if rel_path.startswith("boe_copies/"):
        from apps.bill_of_entry.models import BillOfEntryModel

        if not BillOfEntryModel.objects.filter(boe_pdf_copy=rel_path).exists():
            return []
        return BillOfEntryPermission.required_roles_for_read

    if rel_path.startswith("trade/"):
        from apps.trade.models import LicenseTrade

        if not LicenseTrade.objects.filter(purchase_invoice_copy=rel_path).exists():
            return []
        return TradePermission.required_roles_for_read

    return None


class ProtectedMediaView(APIView):
    """Serve a file from ``MEDIA_ROOT`` only to authenticated users.

    Path is confined to ``MEDIA_ROOT`` (path-traversal attempts 404). Licence,
    BOE and trade documents additionally require the same read role the owning
    record's REST endpoint requires (see ``_required_read_roles``). When
    ``settings.MEDIA_X_ACCEL_REDIRECT`` is set (production), the response carries an
    ``X-Accel-Redirect`` to nginx's internal location; otherwise the file is
    streamed via ``FileResponse`` (development).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, path):
        media_root = os.path.realpath(settings.MEDIA_ROOT)
        full = os.path.realpath(os.path.join(media_root, path))

        # Confine strictly to MEDIA_ROOT — block ../ traversal and symlink escapes.
        if full != media_root and not full.startswith(media_root + os.sep):
            raise Http404()
        if not os.path.isfile(full):
            raise Http404()

        rel = os.path.relpath(full, media_root)

        required_roles = _required_read_roles(rel)
        if required_roles is not None:
            user = request.user
            if not (user.is_superuser or user.has_any_role(required_roles)):
                # 404 rather than 403: consistent with the traversal/missing-file
                # cases above and avoids confirming a confidential document's
                # existence to a caller who isn't allowed to see it.
                raise Http404()

        filename = os.path.basename(full)
        internal_prefix = getattr(settings, "MEDIA_X_ACCEL_REDIRECT", "")

        if internal_prefix:
            # Production: let nginx serve the bytes from its internal location.
            resp = HttpResponse(status=200)
            resp["X-Accel-Redirect"] = internal_prefix.rstrip("/") + "/" + rel
            # Let nginx infer content-type/length from the file it serves.
            del resp["Content-Type"]
            resp["Content-Disposition"] = f'inline; filename="{filename}"'
            return resp

        # Development / no reverse proxy: stream directly.
        return FileResponse(open(full, "rb"), as_attachment=False, filename=filename)
