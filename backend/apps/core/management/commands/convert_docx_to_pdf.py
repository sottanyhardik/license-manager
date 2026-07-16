from pathlib import Path

from django.core.management.base import BaseCommand

from apps.allotment.scripts.aro import convert_docx_to_pdf


class Command(BaseCommand):
    help = "Convert all DOCX files in the specified folder to PDF and delete the original DOCX files"

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            default='my_docx_folder',
            help='Folder path containing DOCX files to convert'
        )
        parser.add_argument(
            '--keep-docx',
            action='store_true',
            help='Keep original DOCX files after conversion (do not delete them)'
        )

    def handle(self, *args, **options):
        folder_path = Path(options['path'])
        keep_docx = options['keep_docx']

        if not folder_path.exists() or not folder_path.is_dir():
            self.stdout.write(self.style.ERROR(f"❌ Folder '{folder_path}' does not exist."))
            return

        docx_files = sorted(path for path in folder_path.iterdir() if path.is_file() and path.suffix.lower() == '.docx')
        if not docx_files:
            self.stdout.write(self.style.WARNING(f"⚠️ No DOCX files found in '{folder_path}'."))
            return

        self.stdout.write(f"📝 Converting {len(docx_files)} DOCX files to PDF in '{folder_path}'...")

        success_count = 0
        failed_count = 0
        deleted = 0

        for docx_file in docx_files:
            docx_path = docx_file
            pdf_path = docx_file.with_suffix('.pdf')

            self.stdout.write(f"  Converting: {docx_file.name}...")

            try:
                if convert_docx_to_pdf(str(docx_path), str(pdf_path)):
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f"    ✅ Converted: {docx_file.name}"))

                    # Delete DOCX file if conversion successful and --keep-docx not specified
                    if not keep_docx:
                        try:
                            docx_path.unlink()
                            deleted += 1
                            self.stdout.write(f"    🗑️  Deleted: {docx_file.name}")
                        except Exception as del_err:
                            self.stdout.write(self.style.WARNING(f"    ⚠️  Failed to delete '{docx_file.name}': {del_err}"))
                else:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f"    ❌ Failed: {docx_file.name}"))

            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f"    ❌ Error converting '{docx_file.name}': {e}"))

        # Summary
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS(f"✅ Successfully converted: {success_count}/{len(docx_files)}"))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f"❌ Failed conversions: {failed_count}/{len(docx_files)}"))
        if not keep_docx:
            self.stdout.write(self.style.SUCCESS(f"🗑️  Deleted DOCX files: {deleted}/{success_count}"))
        else:
            self.stdout.write(self.style.WARNING(f"📁 Original DOCX files kept (--keep-docx flag used)"))
        self.stdout.write("="*80)


# Usage:
# python manage.py convert_docx_to_pdf --path your_folder_name
# python manage.py convert_docx_to_pdf --path your_folder_name --keep-docx
