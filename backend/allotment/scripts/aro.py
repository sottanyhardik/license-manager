"""
Transfer Letter Generation Module
Generates transfer letters from DOCX templates and converts to PDF
"""
import os
import subprocess
import tempfile
from docxtpl import DocxTemplate


def convert_docx_to_pdf(docx_path, pdf_path):
    """
    Convert DOCX to PDF using available tools.

    Tries in order:
    1. LibreOffice (soffice)
    2. Microsoft Word (if on macOS)

    Returns True if successful, False otherwise.
    """
    output_dir = os.path.dirname(pdf_path)

    # Try LibreOffice first
    try:
        # Use a temporary user profile directory to avoid permission issues
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env['HOME'] = tmpdir

            result = subprocess.run([
                'soffice', '--headless', '--convert-to', 'pdf',
                '--outdir', output_dir, docx_path
            ], check=True, capture_output=True, timeout=30, env=env)

        # LibreOffice creates PDF with same name as DOCX
        expected_pdf = docx_path.replace('.docx', '.pdf')
        if os.path.exists(expected_pdf) and expected_pdf != pdf_path:
            os.rename(expected_pdf, pdf_path)

        return os.path.exists(pdf_path)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"LibreOffice conversion failed: {type(e).__name__}: {str(e)}")
        if hasattr(e, 'stderr'):
            print(f"stderr: {e.stderr.decode()}")
        pass

    # Try using macOS textutil + cupsfilter
    try:
        import platform
        if platform.system() == 'Darwin':  # macOS
            # Convert DOCX to HTML first
            html_path = docx_path.replace('.docx', '.html')
            subprocess.run(['textutil', '-convert', 'html', docx_path, '-output', html_path],
                         check=True, timeout=30)

            # Convert HTML to PDF
            subprocess.run(['cupsfilter', html_path],
                         stdout=open(pdf_path, 'wb'), check=True, timeout=30)

            # Clean up HTML
            if os.path.exists(html_path):
                os.remove(html_path)

            return os.path.exists(pdf_path)
    except:
        pass

    return False


def generate_tl_software(data, tl_path, path, transfer_letter_name, be_number=None):
    """
    Generate transfer letters from DOCX template and convert to PDF.

    Args:
        data: List of dictionaries containing transfer letter data
        tl_path: Path to the transfer letter template (.docx file)
        path: Output directory path
        transfer_letter_name: Name for the transfer letter files
        be_number: Optional BOE number
    """
    # Create output directory if it doesn't exist
    os.makedirs(path, exist_ok=True)

    conversion_failed_count = 0

    # Generate a transfer letter for each data item
    for idx, context in enumerate(data, start=1):
        try:
            # DOCX template processing
            doc = DocxTemplate(tl_path)
            doc.render(context)

            # Save as DOCX first
            docx_filename = f"{transfer_letter_name}_{idx}.docx"
            docx_path = os.path.join(path, docx_filename)
            doc.save(docx_path)

            # Convert DOCX to PDF
            pdf_filename = f"{transfer_letter_name}_{idx}.pdf"
            pdf_path = os.path.join(path, pdf_filename)

            if convert_docx_to_pdf(docx_path, pdf_path):
                # Successful conversion - delete DOCX
                os.remove(docx_path)
            else:
                # Conversion failed - keep DOCX
                conversion_failed_count += 1
                print(f"Warning: Could not convert {docx_filename} to PDF. Keeping DOCX file.")

        except Exception as e:
            print(f"Error generating transfer letter {idx}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    if conversion_failed_count > 0:
        print(f"\nWarning: {conversion_failed_count} file(s) could not be converted to PDF.")
        print("To enable PDF conversion, install LibreOffice:")
        print("  macOS: brew install --cask libreoffice")
        print("  Ubuntu/Debian: sudo apt-get install libreoffice")
        print("  RHEL/CentOS: sudo yum install libreoffice")
