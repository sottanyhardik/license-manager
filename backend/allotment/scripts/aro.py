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
    Convert DOCX to PDF using LibreOffice.

    Returns True if successful, False otherwise.
    """
    output_dir = os.path.dirname(pdf_path)

    # Try LibreOffice conversion
    try:
        # Run soffice in headless mode with simple environment
        # Don't override HOME as it can cause permission issues
        result = subprocess.run([
            'soffice',
            '--headless',
            '--norestore',
            '--nofirststartwizard',
            '--nologo',
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            docx_path
        ], capture_output=True, timeout=60, text=True)

        # LibreOffice creates PDF with same name as DOCX in the output directory
        expected_pdf = os.path.join(output_dir, os.path.basename(docx_path).replace('.docx', '.pdf'))

        # Check if PDF was created
        if os.path.exists(expected_pdf):
            if expected_pdf != pdf_path:
                os.rename(expected_pdf, pdf_path)
            print(f"✓ Successfully converted {os.path.basename(docx_path)} to PDF")
            return True
        else:
            print(f"✗ PDF not created: {os.path.basename(docx_path)}")
            if result.stdout:
                print(f"  stdout: {result.stdout}")
            if result.stderr:
                print(f"  stderr: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print(f"✗ Conversion timeout for {os.path.basename(docx_path)}")
        return False
    except FileNotFoundError:
        print(f"✗ LibreOffice (soffice) not found in PATH")
        return False
    except Exception as e:
        print(f"✗ Conversion error for {os.path.basename(docx_path)}: {type(e).__name__}: {str(e)}")
        return False

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

            # Build filename: license_number + serial_number + purchase_status + BOE_number (if exists)
            license_number = context.get('license', 'LICENSE').replace('/', '_')
            serial_number = context.get('serial_number', idx)
            purchase_status = context.get('status', '')
            boe_info = context.get('boe', '')

            # Create descriptive filename
            filename_parts = [license_number, str(serial_number)]
            if purchase_status:
                filename_parts.append(purchase_status)
            if boe_info and 'BE NUMBER:' in boe_info:
                # Extract BE number from "BE NUMBER: XXXXX"
                be_num = boe_info.replace('BE NUMBER:', '').strip().replace('/', '_')
                filename_parts.append(be_num)

            base_filename = '_'.join(filename_parts)

            # Save as DOCX first
            docx_filename = f"{base_filename}.docx"
            docx_path = os.path.join(path, docx_filename)
            doc.save(docx_path)

            # Convert DOCX to PDF
            pdf_filename = f"{base_filename}.pdf"
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
