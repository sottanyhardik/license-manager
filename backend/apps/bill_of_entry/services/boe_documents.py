"""BOE document security helpers (owner decision D10).

* ``validate_boe_pdf`` — gate for an uploaded ICEGATE BOE PDF: configurable size
  limit (``settings.BOE_PDF_MAX_UPLOAD_MB``), ``%PDF-`` signature at offset 0,
  no HTML / script / executable content in the sniffable head, no active PDF
  content (JavaScript / Launch actions), page cap, and must open with pypdf
  (the library the BOE parser already uses — no new dependency).
* ``boe_copy_filename`` — user-facing download name
  ``BOE_<NUMBER>_<DD-MM-YYYY>.pdf``, sanitised to ``[A-Za-z0-9-]``. Storage paths
  are untouched; this is only the name presented to the user.
"""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

__all__ = ["validate_boe_pdf", "boe_copy_filename"]

PDF_SIGNATURE = b"%PDF-"
DEFAULT_MAX_UPLOAD_MB = 10
# Page cap: an ICEGATE BOE is a handful of pages; this bounds parser CPU/memory.
DEFAULT_MAX_PAGES = 50
# Browsers content-sniff the first 512 bytes; scan a generous head window.
_HEAD_SCAN_BYTES = 4096

# Markers that must never appear in the sniffable head of a "PDF" (polyglots).
_HTML_SCRIPT_MARKERS = (
    b"<html", b"<!doctype", b"<script", b"<body", b"<head", b"<iframe",
    b"<svg", b"<object", b"<embed", b"<meta", b"javascript:",
)
# Executable / archive magic numbers (checked at offset 0 for clarity of error).
_EXECUTABLE_MAGIC = (
    b"MZ",                # Windows PE
    b"\x7fELF",           # ELF
    b"\xcf\xfa\xed\xfe",  # Mach-O 64
    b"\xce\xfa\xed\xfe",  # Mach-O 32
    b"\xca\xfe\xba\xbe",  # Mach-O fat / Java class
    b"#!",                # shell script
    b"PK\x03\x04",        # zip / jar / office
)
# Active-content PDF action types. Detected STRUCTURALLY via pypdf (catalog,
# page and annotation actions) — a raw byte scan false-positives on real ICEGATE
# BOEs whose ASCII85 image streams happen to contain e.g. "/JS".
_ACTIVE_ACTION_TYPES = frozenset({"/JavaScript", "/Launch"})
_MAX_ACTION_CHAIN = 32

_SANITIZE_RX = re.compile(r"[^A-Za-z0-9-]+")


def _max_upload_bytes() -> int:
    raw = getattr(settings, "BOE_PDF_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)
    try:
        mb = int(raw)
    except (TypeError, ValueError):
        mb = DEFAULT_MAX_UPLOAD_MB
    if mb <= 0:
        mb = DEFAULT_MAX_UPLOAD_MB
    return mb * 1024 * 1024


def _max_pages() -> int:
    try:
        pages = int(getattr(settings, "BOE_PDF_MAX_PAGES", DEFAULT_MAX_PAGES))
    except (TypeError, ValueError):
        pages = DEFAULT_MAX_PAGES
    return pages if pages > 0 else DEFAULT_MAX_PAGES


def _file_size(uploaded_file) -> int:
    size = getattr(uploaded_file, "size", None)
    if isinstance(size, int):
        return size
    pos = uploaded_file.tell()
    uploaded_file.seek(0, 2)
    end = uploaded_file.tell()
    uploaded_file.seek(pos)
    return end


def has_pdf_signature(head: bytes) -> bool:
    """True when ``head`` starts with the ``%PDF-`` magic."""
    return bool(head) and head.startswith(PDF_SIGNATURE)


def _read_all(uploaded_file) -> bytes:
    uploaded_file.seek(0)
    data = uploaded_file.read()
    uploaded_file.seek(0)
    return data if isinstance(data, bytes) else bytes(data or b"")


def _check_head(head: bytes) -> None:
    if not head:
        raise ValidationError("The uploaded file is empty.", code="empty")
    for magic in _EXECUTABLE_MAGIC:
        if head.startswith(magic):
            raise ValidationError(
                "Executable or archive files are not allowed; upload a PDF.",
                code="executable",
            )
    if not has_pdf_signature(head):
        raise ValidationError("The uploaded file is not a PDF.", code="signature")
    lowered = head[:_HEAD_SCAN_BYTES].lower()
    if any(marker in lowered for marker in _HTML_SCRIPT_MARKERS):
        raise ValidationError(
            "The uploaded file contains HTML or script content and was rejected.",
            code="html",
        )


def _check_structure(data: bytes) -> None:
    import io

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        page_count = len(reader.pages)
    except Exception:  # noqa: BLE001 - any parser failure means malformed
        logger.info("BOE PDF rejected: pypdf could not open the document.", exc_info=True)
        raise ValidationError("The uploaded PDF is malformed or unreadable.", code="malformed")
    if page_count <= 0:
        raise ValidationError("The uploaded PDF has no pages.", code="malformed")
    if page_count > _max_pages():
        raise ValidationError(
            f"The uploaded PDF has too many pages (limit {_max_pages()}).",
            code="pages",
        )
    try:
        active = _has_active_content(reader)
    except Exception:  # noqa: BLE001 - unreadable object graph means malformed
        logger.info("BOE PDF rejected: action dictionaries unreadable.", exc_info=True)
        raise ValidationError("The uploaded PDF is malformed or unreadable.", code="malformed")
    if active:
        raise ValidationError(
            "PDFs with embedded JavaScript or launch actions are not allowed.",
            code="active_content",
        )


def _resolve(obj):
    return obj.get_object() if hasattr(obj, "get_object") else obj


def _is_active_action(action) -> bool:
    """True when an action dict (or its /Next chain) is JavaScript/Launch."""
    pending = [action]
    seen = 0
    while pending and seen < _MAX_ACTION_CHAIN:
        seen += 1
        current = _resolve(pending.pop())
        if isinstance(current, list):
            pending.extend(current)
            continue
        if not hasattr(current, "get"):
            continue
        if str(current.get("/S")) in _ACTIVE_ACTION_TYPES or "/JS" in current:
            return True
        nxt = current.get("/Next")
        if nxt is not None:
            pending.append(nxt)
    return False


def _additional_actions_active(holder) -> bool:
    aa = _resolve(holder.get("/AA")) if hasattr(holder, "get") else None
    if not hasattr(aa, "values"):
        return False
    return any(_is_active_action(v) for v in aa.values())


def _has_active_content(reader) -> bool:
    root = _resolve(reader.trailer.get("/Root"))
    if not hasattr(root, "get"):
        return False
    names = _resolve(root.get("/Names"))
    if hasattr(names, "get") and names.get("/JavaScript") is not None:
        return True
    open_action = root.get("/OpenAction")
    if open_action is not None and not isinstance(_resolve(open_action), list):
        if _is_active_action(open_action):
            return True
    if _additional_actions_active(root):
        return True
    for page in reader.pages:
        if _additional_actions_active(page):
            return True
        for annot in _resolve(page.get("/Annots")) or []:
            annot = _resolve(annot)
            if not hasattr(annot, "get"):
                continue
            if annot.get("/A") is not None and _is_active_action(annot.get("/A")):
                return True
            if _additional_actions_active(annot):
                return True
    return False


def validate_boe_pdf(uploaded_file) -> None:
    """Validate an uploaded BOE PDF; raise ``ValidationError`` on any problem.

    Leaves the file position at 0 so the caller can parse/store it afterwards.
    """
    if uploaded_file is None:
        raise ValidationError("No file uploaded.", code="required")
    limit = _max_upload_bytes()
    if _file_size(uploaded_file) > limit:
        raise ValidationError(
            f"The uploaded PDF exceeds the {limit // (1024 * 1024)} MB limit.",
            code="size",
        )
    data = _read_all(uploaded_file)
    if len(data) > limit:  # defensive: reported size may be wrong
        raise ValidationError(
            f"The uploaded PDF exceeds the {limit // (1024 * 1024)} MB limit.",
            code="size",
        )
    _check_head(data[:_HEAD_SCAN_BYTES])
    _check_structure(data)


def _sanitize(value: str) -> str:
    return _SANITIZE_RX.sub("-", value).strip("-")


def boe_copy_filename(boe) -> str:
    """Return ``BOE_<NUMBER>_<DD-MM-YYYY>.pdf`` for ``boe``.

    Raises ``ValueError`` when the BOE number or date is missing (or the number
    sanitises to nothing) — identifiers are never invented.
    """
    number = _sanitize(str(getattr(boe, "bill_of_entry_number", None) or "").strip())
    boe_date = getattr(boe, "bill_of_entry_date", None)
    if not number:
        raise ValueError("BOE number is required to build the copy filename.")
    if not boe_date or not hasattr(boe_date, "strftime"):
        raise ValueError("BOE date is required to build the copy filename.")
    return f"BOE_{number}_{boe_date.strftime('%d-%m-%Y')}.pdf"
