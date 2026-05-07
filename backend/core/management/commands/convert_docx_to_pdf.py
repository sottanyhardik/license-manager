import os
from django.core.management.base import BaseCommand
from allotment.scripts.aro import convert_docx_to_pdf

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
        folder_path = options['path']
        keep_docx = options['keep_docx']

        if not os.path.exists(folder_path):
            self.stdout.write(self.style.ERROR(f"❌ Folder '{folder_path}' does not exist."))
            return

        docx_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.docx')]
        if not docx_files:
            self.stdout.write(self.style.WARNING(f"⚠️ No DOCX files found in '{folder_path}'."))
            return

        self.stdout.write(f"📝 Converting {len(docx_files)} DOCX files to PDF in '{folder_path}'...")

        success_count = 0
        failed_count = 0
        deleted = 0

        for docx_file in docx_files:
            docx_path = os.path.join(folder_path, docx_file)
            pdf_path = os.path.join(folder_path, docx_file.replace('.docx', '.pdf'))

            self.stdout.write(f"  Converting: {docx_file}...")

            try:
                if convert_docx_to_pdf(docx_path, pdf_path):
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f"    ✅ Converted: {docx_file}"))

                    # Delete DOCX file if conversion successful and --keep-docx not specified
                    if not keep_docx:
                        try:
                            os.remove(docx_path)
                            deleted += 1
                            self.stdout.write(f"    🗑️  Deleted: {docx_file}")
                        except Exception as del_err:
                            self.stdout.write(self.style.WARNING(f"    ⚠️  Failed to delete '{docx_file}': {del_err}"))
                else:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f"    ❌ Failed: {docx_file}"))

            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f"    ❌ Error converting '{docx_file}': {e}"))

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