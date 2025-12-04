import os
from django.core.management.base import BaseCommand
from docx2pdf import convert

class Command(BaseCommand):
    help = "Convert all DOCX files in the specified folder to PDF and delete the original DOCX files"

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            default='my_docx_folder',
            help='Folder path containing DOCX files to convert'
        )

    def handle(self, *args, **options):
        folder_path = options['path']

        if not os.path.exists(folder_path):
            self.stdout.write(self.style.ERROR(f"❌ Folder '{folder_path}' does not exist."))
            return

        docx_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.docx')]
        if not docx_files:
            self.stdout.write(self.style.WARNING(f"⚠️ No DOCX files found in '{folder_path}'."))
            return

        self.stdout.write(f"📝 Converting {len(docx_files)} DOCX files to PDF in '{folder_path}'...")

        try:
            convert(folder_path)
            self.stdout.write(self.style.SUCCESS("✅ Conversion complete. Now deleting DOCX files..."))

            deleted = 0
            for f in docx_files:
                docx_path = os.path.join(folder_path, f)
                try:
                    os.remove(docx_path)
                    deleted += 1
                except Exception as del_err:
                    self.stdout.write(self.style.ERROR(f"❌ Failed to delete '{f}': {del_err}"))

            self.stdout.write(self.style.SUCCESS(f"🗑️ Deleted {deleted} DOCX files. Done!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Conversion failed: {e}"))


#python manage.py convert_docx_to_pdf --path your_folder_name