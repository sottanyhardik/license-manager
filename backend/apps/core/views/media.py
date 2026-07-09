"""Authenticated media/document downloads.

SECURITY (CRITICAL): historically nginx served the entire ``/media/`` tree
publicly (``location /media/`` with ``alias`` + ``Cache-Control: public``), so any
BOE PDF, licence copy, ledger file or generated transfer-letter — customs
documents and PII — was downloadable by anyone who could guess the URL (paths are
highly predictable, e.g. ``TL_<bill_of_entry_number>_<name>/``). That bypassed
every DRF permission class (IDOR at the web-server layer).

This view is the replacement: media is served only to an authenticated request.
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


class ProtectedMediaView(APIView):
    """Serve a file from ``MEDIA_ROOT`` only to authenticated users.

    Path is confined to ``MEDIA_ROOT`` (path-traversal attempts 404). When
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

        filename = os.path.basename(full)
        internal_prefix = getattr(settings, "MEDIA_X_ACCEL_REDIRECT", "")

        if internal_prefix:
            # Production: let nginx serve the bytes from its internal location.
            rel = os.path.relpath(full, media_root)
            resp = HttpResponse(status=200)
            resp["X-Accel-Redirect"] = internal_prefix.rstrip("/") + "/" + rel
            # Let nginx infer content-type/length from the file it serves.
            del resp["Content-Type"]
            resp["Content-Disposition"] = f'inline; filename="{filename}"'
            return resp

        # Development / no reverse proxy: stream directly.
        return FileResponse(open(full, "rb"), as_attachment=False, filename=filename)
