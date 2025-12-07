"""
Django management command to upload DFIA copy files to license documents
- Deletes existing LICENSE COPY documents for each license
- Uploads new DFIA copy files
- Updates license documents in the database

Usage:
    python manage.py upload_dfia_copies /path/to/folder --dry-run
    python manage.py upload_dfia_copies /path/to/folder
"""

import os

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from license.models import LicenseDocumentModel, LicenseDetailsModel


class Command(BaseCommand):
    help = 'Upload DFIA copy files to license documents'

    def add_arguments(self, parser):
        parser.add_argument(
            'folder_path',
            type=str,
            help='Path to the folder containing DFIA copy PDF files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making any changes (test mode)'
        )

    def handle(self, *args, **options):
        folder_path = options['folder_path']
        dry_run = options['dry_run']

        self.stdout.write('=' * 60)
        self.stdout.write(self.style.HTTP_INFO('🔄 DFIA Copy Upload Script'))
        self.stdout.write('=' * 60)
        self.stdout.write(f"Folder: {folder_path}")
        self.stdout.write(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will make changes)'}")
        self.stdout.write('=' * 60)
        self.stdout.write('')

        # Validate folder exists
        if not os.path.exists(folder_path):
            raise CommandError(f'Folder not found: {folder_path}')

        if not os.path.isdir(folder_path):
            raise CommandError(f'Path is not a directory: {folder_path}')

        # Get all PDF files
        files = os.listdir(folder_path)
        pdf_files = [f for f in files if f.lower().endswith('.pdf')]

        if not pdf_files:
            raise CommandError('No PDF files found in folder')

        self.stdout.write(self.style.SUCCESS(f"Found {len(pdf_files)} PDF files\n"))

        # Statistics
        stats = {
            'total': len(pdf_files),
            'processed': 0,
            'license_not_found': 0,
            'deleted': 0,
            'uploaded': 0,
            'errors': 0
        }

        # Process each file
        for filename in sorted(pdf_files):
            # Extract license number from filename (remove .pdf extension)
            license_number = os.path.splitext(filename)[0]

            self.stdout.write(f"Processing: {license_number}")

            try:
                # Find license in database
                license_obj = self.find_license(license_number)

                if not license_obj:
                    self.stdout.write(self.style.ERROR(f"  ❌ License not found: {license_number}"))
                    stats['license_not_found'] += 1
                    continue

                self.stdout.write(self.style.SUCCESS(f"  ✓ Found license: {license_obj.license_number}"))

                # Delete existing LICENSE COPY documents
                existing_docs = LicenseDocumentModel.objects.filter(
                    license=license_obj,
                    type='LICENSE COPY'
                )

                existing_count = existing_docs.count()
                if existing_count > 0:
                    self.stdout.write(f"  → Deleting {existing_count} existing LICENSE COPY document(s)")
                    if not dry_run:
                        # Delete files from disk
                        for doc in existing_docs:
                            if doc.file and os.path.exists(doc.file.path):
                                try:
                                    os.remove(doc.file.path)
                                    self.stdout.write(f"    • Deleted file: {os.path.basename(doc.file.path)}")
                                except Exception as e:
                                    self.stdout.write(self.style.WARNING(f"    ⚠️  Could not delete file: {str(e)}"))
                        # Delete database records
                        deleted_count, _ = existing_docs.delete()
                        stats['deleted'] += deleted_count
                        self.stdout.write(self.style.SUCCESS(f"    ✓ Deleted {deleted_count} document(s)"))
                    else:
                        stats['deleted'] += existing_count

                # Upload new file
                file_path = os.path.join(folder_path, filename)

                if not dry_run:
                    with open(file_path, 'rb') as f:
                        doc = LicenseDocumentModel(
                            license=license_obj,
                            type='LICENSE COPY'
                        )
                        doc.file.save(filename, File(f), save=True)
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Uploaded new LICENSE COPY"))
                        stats['uploaded'] += 1
                else:
                    self.stdout.write(f"  → Would upload: {filename}")
                    stats['uploaded'] += 1

                stats['processed'] += 1
                self.stdout.write('')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ Error: {str(e)}"))
                stats['errors'] += 1
                if options['verbosity'] >= 2:
                    import traceback
                    traceback.print_exc()
                self.stdout.write('')

        # Print summary
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.HTTP_INFO('📊 Summary'))
        self.stdout.write('=' * 60)
        self.stdout.write(f"Total files:           {stats['total']}")
        self.stdout.write(f"Processed:             {stats['processed']}")
        self.stdout.write(f"License not found:     {stats['license_not_found']}")
        self.stdout.write(f"Documents deleted:     {stats['deleted']}")
        self.stdout.write(f"Documents uploaded:    {stats['uploaded']}")
        self.stdout.write(f"Errors:                {stats['errors']}")
        self.stdout.write('=' * 60)

        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('⚠️  This was a DRY RUN - no changes were made'))
            self.stdout.write('Run again without --dry-run to make actual changes')
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✅ Upload completed!'))

    def find_license(self, license_number):
        """
        Find license by number, trying different formats.
        """
        # Try exact match first
        try:
            return LicenseDetailsModel.objects.get(license_number=license_number)
        except LicenseDetailsModel.DoesNotExist:
            pass

        # Try with slashes in different positions
        if len(license_number) == 10:
            # Try XXXX/XXXXXX format
            formatted = f"{license_number[:4]}/{license_number[4:]}"
            try:
                license_obj = LicenseDetailsModel.objects.get(license_number=formatted)
                self.stdout.write(f"  → Found with format: {formatted}")
                return license_obj
            except LicenseDetailsModel.DoesNotExist:
                pass

        # Try removing slashes if filename has them
        if '/' in license_number:
            cleaned = license_number.replace('/', '')
            try:
                return LicenseDetailsModel.objects.get(license_number=cleaned)
            except LicenseDetailsModel.DoesNotExist:
                pass

        return None
