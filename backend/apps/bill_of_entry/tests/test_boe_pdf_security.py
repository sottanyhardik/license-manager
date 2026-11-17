"""Security tests for BOE PDF handling (owner decisions D9 + D10).

D10 — ``validate_boe_pdf`` / ``boe_copy_filename`` and the BOE branch of
``ProtectedMediaView`` (safe Content-Disposition, nosniff, traversal-safe).
D9  — parse-pdf: ``create_company`` default false, CompanyPermission write role
AND the MDS write gate required, no raw exception text in responses.
"""
from __future__ import annotations

import io
from datetime import date
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject
from rest_framework.test import APIClient

from apps.bill_of_entry.models import BillOfEntryModel
from apps.bill_of_entry.services.boe_documents import boe_copy_filename, validate_boe_pdf
from apps.core.models import CompanyModel, PortModel

PARSE_URL = "/api/bill-of-entries/parse-pdf/"
PARSER_PATH = "apps.bill_of_entry.api.views_parse_pdf.parse_boe_pdf"


# ---------------------------------------------------------------- helpers
def _pdf_bytes(pages: int = 1, action: str | None = None) -> bytes:
    """Minimal valid PDF; ``action`` ('/JavaScript' | '/Launch') adds an OpenAction."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if action:
        act = DictionaryObject({NameObject("/S"): NameObject(action)})
        if action == "/JavaScript":
            act[NameObject("/JS")] = TextStringObject("app.alert('x');")
        else:
            act[NameObject("/F")] = TextStringObject("cmd.exe")
        writer._root_object[NameObject("/OpenAction")] = act
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _upload(data: bytes, name: str = "boe.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, data, content_type="application/pdf")


def _make_user(username, roles=(), superuser=False):
    from apps.accounts.models import User

    user = User.objects.create_user(
        username=username, email=f"{username}@example.com", password="x",
        is_superuser=superuser, is_staff=superuser,
    )
    for role in roles:
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
    return user


def _client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _consume(response):
    """Drain + close a FileResponse handle without firing request_finished."""
    if getattr(response, "streaming", False):
        try:
            for _chunk in response.streaming_content:
                pass
        finally:
            handle = getattr(response, "file_to_stream", None)
            if handle is not None:
                handle.close()


# ======================================================= D10 validate_boe_pdf
class TestValidateBoePdf:
    def test_valid_pdf_passes_and_rewinds(self):
        upload = _upload(_pdf_bytes())
        validate_boe_pdf(upload)
        assert upload.tell() == 0

    def test_missing_signature_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(b"hello world, not a pdf at all"))
        assert exc.value.code == "signature"

    def test_signature_must_be_at_offset_zero(self):
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(b"   " + _pdf_bytes()))
        assert exc.value.code == "signature"

    def test_empty_file_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(b""))
        assert exc.value.code == "empty"

    def test_size_limit_from_setting(self, settings):
        settings.BOE_PDF_MAX_UPLOAD_MB = 1
        data = _pdf_bytes() + b"%" + b"x" * (1024 * 1024)
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(data))
        assert exc.value.code == "size"

    def test_invalid_size_setting_falls_back_to_default(self, settings):
        settings.BOE_PDF_MAX_UPLOAD_MB = "not-a-number"
        validate_boe_pdf(_upload(_pdf_bytes()))  # default 10 MB → passes

    def test_page_cap(self, settings):
        settings.BOE_PDF_MAX_PAGES = 2
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(_pdf_bytes(pages=3)))
        assert exc.value.code == "pages"

    def test_html_disguised_as_pdf_rejected(self):
        data = b"%PDF-1.4\n<html><body><script>alert(1)</script></body></html>\n"
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(data, name="evil.pdf"))
        assert exc.value.code == "html"

    def test_pure_html_with_pdf_extension_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(b"<!DOCTYPE html><html></html>", name="evil.pdf"))
        assert exc.value.code == "signature"

    @pytest.mark.parametrize("magic", [b"MZ\x90\x00", b"\x7fELF\x02", b"#!/bin/sh\n", b"PK\x03\x04"])
    def test_executable_signatures_rejected(self, magic):
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(magic + b"\x00" * 64))
        assert exc.value.code == "executable"

    @pytest.mark.parametrize("action", ["/JavaScript", "/Launch"])
    def test_pdf_with_active_open_action_rejected(self, action):
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(_pdf_bytes(action=action)))
        assert exc.value.code == "active_content"

    def test_js_like_bytes_inside_streams_not_false_positive(self):
        # Real ICEGATE BOEs carry ASCII85 image data containing e.g. "/JS`";
        # only structural actions are rejected, not raw byte matches.
        data = _pdf_bytes() + b"\n% a23/JS`2j@pp /JavaScript /Launch\n"
        validate_boe_pdf(_upload(data))

    def test_malformed_pdf_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_boe_pdf(_upload(b"%PDF-1.4\ngarbage that is not a pdf body\n%%EOF"))
        assert exc.value.code == "malformed"

    def test_none_rejected(self):
        with pytest.raises(ValidationError):
            validate_boe_pdf(None)


# ======================================================= D10 boe_copy_filename
class TestBoeCopyFilename:
    def test_format(self):
        boe = SimpleNamespace(bill_of_entry_number="1234567", bill_of_entry_date=date(2026, 11, 15))
        assert boe_copy_filename(boe) == "BOE_1234567_15-11-2026.pdf"

    def test_sanitizes_number(self):
        boe = SimpleNamespace(
            bill_of_entry_number='../12 34/"x";\r\n', bill_of_entry_date=date(2026, 1, 2),
        )
        name = boe_copy_filename(boe)
        assert name == "BOE_12-34-x_02-01-2026.pdf"
        stem = name[len("BOE_"):-len(".pdf")]
        assert all(ch.isalnum() or ch in "-_" for ch in stem)

    @pytest.mark.parametrize("number,boe_date", [
        ("", date(2026, 1, 1)),
        (None, date(2026, 1, 1)),
        ("///", date(2026, 1, 1)),
        ("1234567", None),
    ])
    def test_missing_number_or_date_raises(self, number, boe_date):
        with pytest.raises(ValueError):
            boe_copy_filename(SimpleNamespace(bill_of_entry_number=number, bill_of_entry_date=boe_date))


# ======================================================= D10 media BOE branch
@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_X_ACCEL_REDIRECT = ""
    return tmp_path


def _write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return rel


@pytest.mark.django_db
class TestBoeMediaDownload:
    def _boe(self, rel, number="7654321", boe_date=date(2026, 11, 15)):
        company = CompanyModel.objects.create(iec="IEC0009991", name="Media Importer")
        port = PortModel.objects.create(name="Media Port", code="MPX1")
        return BillOfEntryModel.objects.create(
            company=company, port=port, bill_of_entry_number=number,
            bill_of_entry_date=boe_date, boe_pdf_copy=rel,
        )

    def test_genuine_pdf_inline_with_boe_filename_and_nosniff(self, media_root):
        rel = _write(media_root, "boe_copies/stored-uuid-name.pdf", _pdf_bytes())
        self._boe(rel)
        resp = _client_for(_make_user("bv1", ["BOE_VIEWER"])).get(f"/api/media/{rel}")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/pdf"
        assert resp["Content-Disposition"] == 'inline; filename="BOE_7654321_15-11-2026.pdf"'
        assert resp["X-Content-Type-Options"] == "nosniff"
        _consume(resp)

    def test_non_pdf_bytes_forced_to_attachment_octet_stream(self, media_root):
        rel = _write(media_root, "boe_copies/legacy.pdf", b"<html><script>alert(1)</script></html>")
        self._boe(rel)
        resp = _client_for(_make_user("bv2", ["BOE_VIEWER"])).get(f"/api/media/{rel}")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/octet-stream"
        assert resp["Content-Disposition"].startswith("attachment;")
        assert resp["X-Content-Type-Options"] == "nosniff"
        _consume(resp)

    def test_missing_date_falls_back_to_stored_basename(self, media_root):
        rel = _write(media_root, "boe_copies/2109376_BE_COPY.pdf", _pdf_bytes())
        self._boe(rel, boe_date=None)
        resp = _client_for(_make_user("bv3", ["BOE_VIEWER"])).get(f"/api/media/{rel}")
        assert resp.status_code == 200
        assert resp["Content-Disposition"] == 'inline; filename="2109376_BE_COPY.pdf"'
        _consume(resp)

    def test_x_accel_redirect_branch_sets_safe_headers(self, media_root, settings):
        settings.MEDIA_X_ACCEL_REDIRECT = "/protected-media/"
        rel = _write(media_root, "boe_copies/xa.pdf", _pdf_bytes())
        self._boe(rel)
        resp = _client_for(_make_user("bv4", ["BOE_VIEWER"])).get(f"/api/media/{rel}")
        assert resp.status_code == 200
        assert resp["X-Accel-Redirect"] == "/protected-media/boe_copies/xa.pdf"
        assert resp["Content-Disposition"] == 'inline; filename="BOE_7654321_15-11-2026.pdf"'
        assert resp["X-Content-Type-Options"] == "nosniff"

    def test_rbac_still_enforced_on_boe_branch(self, media_root):
        rel = _write(media_root, "boe_copies/rbac.pdf", _pdf_bytes())
        self._boe(rel)
        resp = _client_for(_make_user("lv", ["LICENSE_VIEWER"])).get(f"/api/media/{rel}")
        assert resp.status_code == 404

    @pytest.mark.parametrize("path", [
        "boe_copies/../../etc/passwd",
        "boe_copies/%2e%2e/%2e%2e/etc/passwd",
        "boe_copies/..%2f..%2fsecret.pdf",
    ])
    def test_traversal_blocked(self, media_root, path):
        # A file just outside MEDIA_ROOT must never be reachable.
        (media_root.parent / "secret.pdf").write_bytes(_pdf_bytes())
        resp = _client_for(_make_user("su_trav", superuser=True)).get(f"/api/media/{path}")
        assert resp.status_code == 404

    def test_symlink_escape_blocked(self, media_root):
        outside = media_root.parent / "outside.pdf"
        outside.write_bytes(_pdf_bytes())
        (media_root / "boe_copies").mkdir(parents=True, exist_ok=True)
        (media_root / "boe_copies" / "link.pdf").symlink_to(outside)
        resp = _client_for(_make_user("su_link", superuser=True)).get("/api/media/boe_copies/link.pdf")
        assert resp.status_code == 404

    def test_licence_branch_unchanged(self, media_root):
        # Non-BOE branches keep the original Content-Disposition behaviour.
        rel = _write(media_root, "misc/report.pdf", b"%PDF-1.4 fake\n")
        resp = _client_for(_make_user("any_auth")).get(f"/api/media/{rel}")
        assert resp.status_code == 200
        assert resp["Content-Disposition"] == 'inline; filename="report.pdf"'
        _consume(resp)


# ======================================================= D9 parse-pdf
PARSED = {
    "be_number": "8888001",
    "be_date": "2026-11-15",
    "iec": "0999888777",
    "buyer_name": "NEW PARSED IMPORTER PRIVATE LIMITED",
    "buyer_address": "1 Test Road",
    "port_code": None,
    "invoice_no": None,
    "licences": [],
}


@pytest.mark.django_db
class TestParsePdfSecurity:
    def _post(self, user, data=None, content=None):
        payload = {"file": _upload(content if content is not None else _pdf_bytes())}
        payload.update(data or {})
        return _client_for(user).post(PARSE_URL, payload, format="multipart")

    def test_create_company_defaults_to_false(self):
        user = _make_user("um_default", ["BOE_MANAGER", "USER_MANAGER"])
        with mock.patch(PARSER_PATH, return_value=dict(PARSED)):
            resp = self._post(user)
        assert resp.status_code == 200
        assert resp.data["company_created"] is False
        assert resp.data["matched_company_id"] is None
        assert resp.data["company_creation_skipped_reason"] == "not_requested"
        assert resp.data["unmatched_company"] == {
            "iec": "0999888777", "name": PARSED["buyer_name"], "address": "1 Test Road",
        }
        assert resp.data["prefill"]["company_name"] == PARSED["buyer_name"]
        assert not CompanyModel.objects.filter(iec="0999888777").exists()

    def test_create_requires_company_write_role(self):
        user = _make_user("boe_only", ["BOE_MANAGER"])
        with mock.patch(PARSER_PATH, return_value=dict(PARSED)):
            resp = self._post(user, {"create_company": "true"})
        assert resp.status_code == 200
        assert resp.data["company_created"] is False
        assert resp.data["company_creation_skipped_reason"] == "no_company_write_permission"
        assert not CompanyModel.objects.filter(iec="0999888777").exists()

    def test_create_allowed_with_write_role_and_mds_off(self, settings):
        settings.MDS_ENABLED = False
        user = _make_user("um_ok", ["BOE_MANAGER", "USER_MANAGER"])
        with mock.patch(PARSER_PATH, return_value=dict(PARSED)):
            resp = self._post(user, {"create_company": "true"})
        assert resp.status_code == 200
        assert resp.data["company_created"] is True
        assert resp.data["company_creation_skipped_reason"] is None
        assert resp.data["unmatched_company"] is None
        company = CompanyModel.objects.get(iec="0999888777")
        assert resp.data["matched_company_id"] == company.id

    def test_create_blocked_when_mds_owns_company_writes(self, settings):
        settings.MDS_ENABLED = True
        settings.MDS_MODELS = {"core.CompanyModel": {}}
        user = _make_user("su_mds", superuser=True, roles=["BOE_MANAGER"])
        with mock.patch(PARSER_PATH, return_value=dict(PARSED)):
            resp = self._post(user, {"create_company": "true"})
        assert resp.status_code == 200
        assert resp.data["company_created"] is False
        assert resp.data["company_creation_skipped_reason"] == "company_master_managed_by_mds"
        assert not CompanyModel.objects.filter(iec="0999888777").exists()

    def test_existing_company_matched_regardless_of_flag(self):
        existing = CompanyModel.objects.create(iec="0999888777", name="Existing Co")
        user = _make_user("boe_match", ["BOE_MANAGER"])
        with mock.patch(PARSER_PATH, return_value=dict(PARSED)):
            resp = self._post(user)
        assert resp.data["matched_company_id"] == existing.id
        assert resp.data["company_creation_skipped_reason"] is None
        assert resp.data["unmatched_company"] is None

    def test_parser_exception_not_echoed(self):
        user = _make_user("boe_exc", ["BOE_MANAGER"])
        secret = "Traceback: /srv/app/secret/path.py line 42 SECRET-INTERNAL"
        with mock.patch(PARSER_PATH, side_effect=RuntimeError(secret)), \
                mock.patch("apps.bill_of_entry.api.views_parse_pdf.logger") as log:
            resp = self._post(user)
        assert resp.status_code == 400
        assert set(resp.data) == {"detail"}
        assert "SECRET-INTERNAL" not in str(resp.data)
        assert resp.data["detail"].startswith("Failed to parse PDF.")
        log.exception.assert_called_once()

    def test_html_disguised_upload_rejected_before_parsing(self):
        user = _make_user("boe_html", ["BOE_MANAGER"])
        with mock.patch(PARSER_PATH) as parser:
            resp = self._post(user, content=b"%PDF-1.4\n<html><script>x</script></html>")
        assert resp.status_code == 400
        assert "detail" in resp.data
        parser.assert_not_called()

    def test_oversized_upload_rejected(self, settings):
        settings.BOE_PDF_MAX_UPLOAD_MB = 1
        user = _make_user("boe_big", ["BOE_MANAGER"])
        with mock.patch(PARSER_PATH) as parser:
            resp = self._post(user, content=_pdf_bytes() + b"%" + b"x" * (1024 * 1024))
        assert resp.status_code == 400
        assert "MB limit" in resp.data["detail"]
        parser.assert_not_called()

    def test_no_file_message_unchanged(self):
        user = _make_user("boe_nofile", ["BOE_MANAGER"])
        resp = _client_for(user).post(PARSE_URL, {}, format="multipart")
        assert resp.status_code == 400
        assert resp.data["detail"] == "No file uploaded. Send the PDF as multipart field 'file'."
