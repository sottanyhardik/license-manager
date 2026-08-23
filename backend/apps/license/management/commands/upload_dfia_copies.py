"""Upload DFIA copy PDF files to license document records."""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.license.models import LicenseDocumentModel, LicenseDetailsModel


DOCUMENT_TYPE = "LICENSE COPY"
PDF_SIGNATURE = b"%PDF"


class Command(BaseCommand):
    help = "Upload DFIA copy files to license documents"

    def add_arguments(self, parser):
        parser.add_argument(
            "folder_path",
            type=str,
            help="Path to the folder containing DFIA copy PDF files",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run without making any changes (test mode)",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm replacement of existing LICENSE COPY documents",
        )

    def handle(self, *args, **options):
        folder_path = self._resolve_folder_path(options["folder_path"])
        dry_run = options["dry_run"]
        confirm = options["confirm"]

        if not dry_run and not confirm:
            raise CommandError("Live uploads require --confirm")

        self._write_header(folder_path, dry_run)
        pdf_paths = self._collect_pdf_paths(folder_path)
        upload_plan, errors = self._build_upload_plan(pdf_paths)
        stats = self._initial_stats(pdf_paths)

        if errors:
            self._write_errors(errors)
            raise CommandError("DFIA copy upload validation failed; no documents were changed")

        self.stdout.write(self.style.SUCCESS(f"Found {len(upload_plan)} PDF files\n"))

        for upload in upload_plan:
            existing_docs = list(
                LicenseDocumentModel.objects.filter(
                    license=upload["license"],
                    type=DOCUMENT_TYPE,
                )
            )
            existing_count = len(existing_docs)
            stats["deleted"] += existing_count

            self.stdout.write(f"Processing: {upload['license_number']}")
            self.stdout.write(
                self.style.SUCCESS(f"  Found license: {upload['license'].license_number}")
            )
            if existing_count:
                self.stdout.write(
                    f"  Replacing {existing_count} existing {DOCUMENT_TYPE} document(s)"
                )

            if dry_run:
                self.stdout.write(f"  Would upload: {upload['path'].name}")
                stats["uploaded"] += 1
                stats["processed"] += 1
                self.stdout.write("")
                continue

            self._replace_document(upload["license"], upload["path"], existing_docs)
            stats["uploaded"] += 1
            stats["processed"] += 1
            self.stdout.write(self.style.SUCCESS(f"  Uploaded new {DOCUMENT_TYPE}"))
            self.stdout.write("")

        self._write_summary(stats, dry_run)

    def _resolve_folder_path(self, folder_path):
        folder_path = (folder_path or "").strip()
        if not folder_path:
            raise CommandError("Folder path must not be blank")

        path = Path(folder_path).expanduser()
        if not path.exists():
            raise CommandError(f"Folder not found: {path}")
        if not path.is_dir():
            raise CommandError(f"Path is not a directory: {path}")

        return path

    def _collect_pdf_paths(self, folder_path):
        pdf_paths = sorted(
            path for path in folder_path.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"
        )
        if not pdf_paths:
            raise CommandError("No PDF files found in folder")
        return pdf_paths

    def _build_upload_plan(self, pdf_paths):
        errors = []
        rows = []
        all_candidates = set()

        for pdf_path in pdf_paths:
            license_number = pdf_path.stem.strip()
            if not license_number:
                errors.append(f"{pdf_path.name}: License number cannot be blank")
                continue
            if pdf_path.stat().st_size == 0:
                errors.append(f"{pdf_path.name}: PDF file is empty")
                continue
            if not self._has_pdf_signature(pdf_path):
                errors.append(f"{pdf_path.name}: File does not start with a PDF signature")
                continue

            candidates = self._license_candidates(license_number)
            rows.append(
                {
                    "path": pdf_path,
                    "license_number": license_number,
                    "candidates": candidates,
                }
            )
            all_candidates.update(candidates)

        licenses_by_number = (
            LicenseDetailsModel.objects.in_bulk(all_candidates, field_name="license_number")
            if all_candidates
            else {}
        )
        seen_license_ids = set()
        upload_plan = []

        for row in rows:
            license_obj = self._resolve_license(row["candidates"], licenses_by_number)
            if license_obj is None:
                errors.append(f"{row['path'].name}: License not found for {row['license_number']}")
                continue
            if license_obj.pk in seen_license_ids:
                errors.append(
                    f"{row['path'].name}: Multiple files resolve to license "
                    f"{license_obj.license_number}"
                )
                continue

            seen_license_ids.add(license_obj.pk)
            upload_plan.append({**row, "license": license_obj})

        return upload_plan, errors

    def _has_pdf_signature(self, pdf_path):
        try:
            with pdf_path.open("rb") as handle:
                return handle.read(len(PDF_SIGNATURE)) == PDF_SIGNATURE
        except OSError as exc:
            raise CommandError(f"Could not read {pdf_path}: {exc}") from exc

    def _license_candidates(self, license_number):
        candidates = [license_number]
        if len(license_number) == 10:
            candidates.append(f"{license_number[:4]}/{license_number[4:]}")
        if "/" in license_number:
            candidates.append(license_number.replace("/", ""))
        return tuple(dict.fromkeys(candidates))

    def _resolve_license(self, candidates, licenses_by_number):
        for candidate in candidates:
            license_obj = licenses_by_number.get(candidate)
            if license_obj is not None:
                return license_obj
        return None

    def _replace_document(self, license_obj, pdf_path, existing_docs):
        new_doc = None
        try:
            with transaction.atomic():
                if existing_docs:
                    existing_ids = [doc.pk for doc in existing_docs]
                    LicenseDocumentModel.objects.filter(pk__in=existing_ids).delete()
                    for doc in existing_docs:
                        if doc.file.name:
                            transaction.on_commit(
                                lambda storage=doc.file.storage, name=doc.file.name: storage.delete(name)
                            )

                new_doc = LicenseDocumentModel(license=license_obj, type=DOCUMENT_TYPE)
                with pdf_path.open("rb") as handle:
                    new_doc.file.save(pdf_path.name, File(handle), save=True)
        except Exception as exc:
            if new_doc and new_doc.file.name:
                new_doc.file.storage.delete(new_doc.file.name)
            raise CommandError(f"Error uploading {pdf_path.name}: {exc}") from exc

    def _write_header(self, folder_path, dry_run):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.HTTP_INFO("DFIA Copy Upload Script"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Folder: {folder_path}")
        self.stdout.write(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will make changes)'}")
        self.stdout.write("=" * 60)
        self.stdout.write("")

    def _write_errors(self, errors):
        self.stdout.write(self.style.ERROR("Validation errors:"))
        for error in errors[:10]:
            self.stdout.write(f"  - {error}")
        if len(errors) > 10:
            self.stdout.write(f"  ... and {len(errors) - 10} more")

    def _initial_stats(self, pdf_paths):
        return {
            "total": len(pdf_paths),
            "processed": 0,
            "deleted": 0,
            "uploaded": 0,
        }

    def _write_summary(self, stats, dry_run):
        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.HTTP_INFO("Summary"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total files:           {stats['total']}")
        self.stdout.write(f"Processed:             {stats['processed']}")
        self.stdout.write(f"Documents deleted:     {stats['deleted']}")
        self.stdout.write(f"Documents uploaded:    {stats['uploaded']}")
        self.stdout.write("=" * 60)

        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING("This was a DRY RUN - no changes were made"))
            self.stdout.write("Run again with --confirm and without --dry-run to make actual changes")
        else:
            self.stdout.write(self.style.SUCCESS("Upload completed"))
