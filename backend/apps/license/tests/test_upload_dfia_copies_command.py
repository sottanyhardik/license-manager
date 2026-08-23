from __future__ import annotations

from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.license.models import LicenseDetailsModel, LicenseDocumentModel


PDF_BYTES = b"%PDF-1.4\n% test pdf\n"


def write_pdf(folder, filename, content=PDF_BYTES):
    path = folder / filename
    path.write_bytes(content)
    return path


def test_upload_dfia_copies_rejects_blank_folder_path():
    with pytest.raises(CommandError, match="Folder path must not be blank"):
        call_command("upload_dfia_copies", "   ", "--dry-run")


def test_upload_dfia_copies_rejects_missing_folder(tmp_path):
    with pytest.raises(CommandError, match="Folder not found"):
        call_command("upload_dfia_copies", str(tmp_path / "missing"), "--dry-run")


def test_upload_dfia_copies_rejects_file_path(tmp_path):
    file_path = tmp_path / "not-a-folder"
    file_path.write_text("x", encoding="utf-8")

    with pytest.raises(CommandError, match="Path is not a directory"):
        call_command("upload_dfia_copies", str(file_path), "--dry-run")


def test_upload_dfia_copies_rejects_folder_without_pdfs(tmp_path):
    (tmp_path / "readme.txt").write_text("not a pdf", encoding="utf-8")

    with pytest.raises(CommandError, match="No PDF files found"):
        call_command("upload_dfia_copies", str(tmp_path), "--dry-run")


@pytest.mark.django_db
def test_upload_dfia_copies_live_mode_requires_confirm(tmp_path):
    LicenseDetailsModel.objects.create(license_number="DFIA-UP-001")
    write_pdf(tmp_path, "DFIA-UP-001.pdf")

    with pytest.raises(CommandError, match="Live uploads require --confirm"):
        call_command("upload_dfia_copies", str(tmp_path))


@pytest.mark.django_db
def test_upload_dfia_copies_rejects_invalid_pdf_signature_without_writes(tmp_path):
    LicenseDetailsModel.objects.create(license_number="DFIA-UP-002")
    write_pdf(tmp_path, "DFIA-UP-002.pdf", b"not a pdf")

    with pytest.raises(CommandError, match="validation failed"):
        call_command("upload_dfia_copies", str(tmp_path), "--dry-run", stdout=StringIO())

    assert LicenseDocumentModel.objects.count() == 0


@pytest.mark.django_db
def test_upload_dfia_copies_missing_license_blocks_all_writes(tmp_path):
    LicenseDetailsModel.objects.create(license_number="DFIA-UP-003")
    write_pdf(tmp_path, "DFIA-UP-003.pdf")
    write_pdf(tmp_path, "DFIA-UP-MISSING.pdf")

    with pytest.raises(CommandError, match="validation failed"):
        call_command("upload_dfia_copies", str(tmp_path), "--confirm", stdout=StringIO())

    assert LicenseDocumentModel.objects.count() == 0


@pytest.mark.django_db
def test_upload_dfia_copies_rejects_duplicate_files_for_same_license(tmp_path):
    LicenseDetailsModel.objects.create(license_number="DFIA-UP-DUP")
    write_pdf(tmp_path, "DFIA-UP-DUP.pdf")
    write_pdf(tmp_path, "DFIA-UP-DUP .pdf")

    with pytest.raises(CommandError, match="validation failed"):
        call_command("upload_dfia_copies", str(tmp_path), "--confirm", stdout=StringIO())

    assert LicenseDocumentModel.objects.count() == 0


@pytest.mark.django_db
def test_upload_dfia_copies_dry_run_does_not_write(tmp_path):
    LicenseDetailsModel.objects.create(license_number="DFIA-UP-004")
    write_pdf(tmp_path, "DFIA-UP-004.pdf")

    call_command("upload_dfia_copies", str(tmp_path), "--dry-run", stdout=StringIO())

    assert LicenseDocumentModel.objects.count() == 0


@pytest.mark.django_db
def test_upload_dfia_copies_uploads_with_formatted_license_match(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"
    license_obj = LicenseDetailsModel.objects.create(license_number="1234/567890")
    write_pdf(tmp_path, "1234567890.pdf")

    call_command("upload_dfia_copies", str(tmp_path), "--confirm", stdout=StringIO())

    doc = LicenseDocumentModel.objects.get(license=license_obj)
    assert doc.type == "LICENSE COPY"
    assert doc.file.name == "licenses/1234/567890/1234/567890_Copy.pdf"
    assert doc.file.storage.exists(doc.file.name)


@pytest.mark.django_db
def test_upload_dfia_copies_replaces_existing_copy_document(
    tmp_path,
    settings,
    django_capture_on_commit_callbacks,
):
    settings.MEDIA_ROOT = tmp_path / "media"
    license_obj = LicenseDetailsModel.objects.create(license_number="DFIA-UP-005")
    old_doc = LicenseDocumentModel.objects.create(license=license_obj, type="LICENSE COPY")
    old_doc.file.save("old.pdf", ContentFile(b"%PDF-1.4\nold\n"), save=True)
    old_file_name = old_doc.file.name
    write_pdf(tmp_path, "DFIA-UP-005.pdf", b"%PDF-1.4\nnew\n")

    with django_capture_on_commit_callbacks(execute=True):
        call_command("upload_dfia_copies", str(tmp_path), "--confirm", stdout=StringIO())

    docs = list(LicenseDocumentModel.objects.filter(license=license_obj))
    assert len(docs) == 1
    assert docs[0].pk != old_doc.pk
    assert docs[0].file.storage.exists(docs[0].file.name)
    assert not docs[0].file.storage.exists(old_file_name)


@pytest.mark.django_db
def test_upload_dfia_copies_rolls_back_database_on_upload_failure(
    tmp_path,
    settings,
    monkeypatch,
):
    settings.MEDIA_ROOT = tmp_path / "media"
    license_obj = LicenseDetailsModel.objects.create(license_number="DFIA-UP-006")
    old_doc = LicenseDocumentModel.objects.create(license=license_obj, type="LICENSE COPY")
    old_doc.file.save("old.pdf", ContentFile(b"%PDF-1.4\nold\n"), save=True)
    write_pdf(tmp_path, "DFIA-UP-006.pdf", b"%PDF-1.4\nnew\n")

    def fail_save(self, *args, **kwargs):
        raise RuntimeError("simulated file save failure")

    monkeypatch.setattr("django.db.models.fields.files.FieldFile.save", fail_save)

    with pytest.raises(CommandError, match="Error uploading"):
        call_command("upload_dfia_copies", str(tmp_path), "--confirm", stdout=StringIO())

    assert list(LicenseDocumentModel.objects.filter(license=license_obj)) == [old_doc]
    assert old_doc.file.storage.exists(old_doc.file.name)
