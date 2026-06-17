"""
Transfer Letter Generation Module
Generates transfer letters from DOCX templates and converts to PDF
"""
import os
import shutil
import subprocess
import tempfile
import time
import uuid
import logging
import concurrent.futures
from docxtpl import DocxTemplate

logger = logging.getLogger(__name__)


def convert_docx_to_pdf(docx_path, pdf_path):
    """
    Convert DOCX to PDF using multiple methods:
    1. Microsoft Office on macOS (preferred if available)
    2. unoconv (Linux/macOS)
    3. LibreOffice (Linux/macOS)

    Returns True if successful, False otherwise.
    """
    # Add file logging for debugging
    debug_log = "/tmp/pdf_conversion_debug.log"
    try:
        with open(debug_log, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting conversion\n")
            f.write(f"DOCX: {docx_path}\n")
            f.write(f"PDF: {pdf_path}\n")
            f.write(f"DOCX exists: {os.path.exists(docx_path)}\n")
            f.flush()
    except Exception as e:
        pass  # Ignore logging errors

    logger.info(f"Starting PDF conversion: {os.path.basename(docx_path)}")
    logger.debug(f"DOCX path: {docx_path}, PDF path: {pdf_path}")
    print(f"[CONVERT] Starting: {os.path.basename(docx_path)}", flush=True)

    # Method 0: Try Microsoft Office on macOS first (using AppleScript)
    try:
        import platform
        if platform.system() == 'Darwin':  # macOS only
            logger.debug("Attempting conversion with Microsoft Word (macOS)...")

            # Convert paths to absolute and use POSIX paths
            abs_docx_path = os.path.abspath(docx_path)
            abs_pdf_path = os.path.abspath(pdf_path)

            # Use AppleScript to automate Microsoft Word
            # Note: Escape single quotes in paths and use proper Word syntax
            # Replace single quotes with escaped versions for AppleScript
            escaped_docx = abs_docx_path.replace("'", "\\'")
            escaped_pdf = abs_pdf_path.replace("'", "\\'").replace("`", "\\`")

            applescript = f'''
            tell application "Microsoft Word"
                set inputFile to POSIX file "{escaped_docx}"
                set outputFile to "{escaped_pdf}"

                set theDoc to open file name inputFile
                save as theDoc file name outputFile file format format PDF
                close theDoc saving no
            end tell
            '''

            result = subprocess.run([
                'osascript',
                '-e', applescript
            ], capture_output=True, timeout=60, text=True)

            if result.returncode == 0 and os.path.exists(pdf_path):
                try:
                    with open(debug_log, "a") as f:
                        f.write(f"SUCCESS: Microsoft Word converted successfully\n")
                        f.flush()
                except OSError:
                    pass
                logger.info(f"✓ Successfully converted with Microsoft Word: {os.path.basename(docx_path)}")
                print(f"✓ Successfully converted {os.path.basename(docx_path)} to PDF (Microsoft Word)")
                return True
            else:
                logger.warning(f"Microsoft Word conversion failed, trying other methods...")
                if result.stderr:
                    logger.debug(f"MS Word stderr: {result.stderr}")
                if result.stdout:
                    logger.debug(f"MS Word stdout: {result.stdout}")
    except FileNotFoundError:
        logger.debug("Microsoft Word not found or osascript not available")
    except Exception as e:
        logger.warning(f"Microsoft Word error: {str(e)}, trying other methods...")

    # Method 1: Try unoconv first (more reliable in server environments)
    try:
        logger.debug("Attempting conversion with unoconv...")
        result = subprocess.run([
            'unoconv',
            '-f', 'pdf',
            '-o', pdf_path,
            docx_path
        ], capture_output=True, timeout=60, text=True)

        if result.returncode == 0 and os.path.exists(pdf_path):
            try:
                with open(debug_log, "a") as f:
                    f.write(f"SUCCESS: unoconv converted successfully\n")
                    f.flush()
            except OSError:
                pass
            logger.info(f"✓ Successfully converted with unoconv: {os.path.basename(docx_path)}")
            print(f"✓ Successfully converted {os.path.basename(docx_path)} to PDF")
            return True
        else:
            logger.warning(f"unoconv failed (exit code: {result.returncode}), trying LibreOffice...")
            if result.stderr:
                logger.debug(f"unoconv stderr: {result.stderr}")
    except FileNotFoundError:
        logger.debug("unoconv not found, falling back to LibreOffice")
    except Exception as e:
        logger.warning(f"unoconv error: {str(e)}, falling back to LibreOffice")

    # Method 2: Fall back to LibreOffice using a unique per-conversion user profile.
    # This allows concurrent conversions without conflicts — no global lock needed.
    output_dir = os.path.dirname(pdf_path)
    profile_dir = f'/tmp/soffice_profile_{os.getpid()}_{uuid.uuid4().hex}'

    try:
        soffice_paths = [
            '/usr/bin/soffice',          # Linux
            '/opt/homebrew/bin/soffice', # macOS (Apple Silicon)
            '/usr/local/bin/soffice',    # macOS (Intel)
            'soffice'                    # Fallback to PATH
        ]

        soffice_path = None
        for path in soffice_paths:
            if path == 'soffice' or os.path.exists(path):
                soffice_path = path
                break

        if not soffice_path:
            msg = f"✗ LibreOffice (soffice) not found in PATH"
            logger.error(msg)
            print(msg)
            return False

        logger.debug(f"Running soffice command from: {soffice_path}")

        env = os.environ.copy()
        lo_home = os.path.expanduser('~')
        if not os.path.exists(lo_home) or not os.access(lo_home, os.W_OK):
            lo_home = '/tmp/django-libreoffice-home'
            os.makedirs(lo_home, exist_ok=True)
        env['HOME'] = lo_home

        current_path = env.get('PATH', '')
        system_paths = '/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin'
        if '/usr/bin' not in current_path:
            env['PATH'] = f'{current_path}:{system_paths}' if current_path else system_paths

        result = subprocess.run([
            soffice_path,
            '--headless',
            '--norestore',
            '--nofirststartwizard',
            '--nologo',
            f'-env:UserInstallation=file://{profile_dir}',
            '--convert-to', 'pdf',
            '--outdir', output_dir,
            docx_path
        ], capture_output=True, timeout=60, text=True, env=env)

        logger.debug(f"soffice exit code: {result.returncode}")
        if result.stdout:
            logger.debug(f"soffice stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"soffice stderr: {result.stderr}")

        expected_pdf = os.path.join(output_dir, os.path.basename(docx_path).replace('.docx', '.pdf'))

        if os.path.exists(expected_pdf):
            if expected_pdf != pdf_path:
                os.rename(expected_pdf, pdf_path)
            try:
                with open(debug_log, "a") as f:
                    f.write(f"SUCCESS: LibreOffice converted successfully\n")
                    f.write(f"PDF size: {os.path.getsize(pdf_path)} bytes\n")
                    f.flush()
            except OSError:
                pass
            msg = f"✓ Successfully converted {os.path.basename(docx_path)} to PDF"
            logger.info(msg)
            print(msg)
            return True
        else:
            try:
                with open(debug_log, "a") as f:
                    f.write(f"FAILED: PDF not created at {expected_pdf}\n")
                    f.write(f"Exit code: {result.returncode}\n")
                    f.write(f"Stdout: {result.stdout}\n")
                    f.write(f"Stderr: {result.stderr}\n")
                    f.flush()
            except OSError:
                pass
            msg = f"✗ PDF not created: {os.path.basename(docx_path)}"
            logger.error(msg)
            print(msg)
            if result.stdout:
                print(f"  stdout: {result.stdout}")
            if result.stderr:
                print(f"  stderr: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        msg = f"✗ Conversion timeout for {os.path.basename(docx_path)}"
        logger.error(msg)
        print(msg)
        return False
    except FileNotFoundError:
        msg = f"✗ LibreOffice (soffice) not found in PATH"
        logger.error(msg)
        print(msg)
        return False
    except Exception as e:
        msg = f"✗ Conversion error for {os.path.basename(docx_path)}: {type(e).__name__}: {str(e)}"
        logger.exception(msg)
        print(msg)
        return False
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

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
    except Exception:
        pass

    return False


def generate_tl_software(data, tl_path, path, transfer_letter_name, be_number=None, additional_context=None):
    """
    Generate transfer letters from DOCX template and convert to PDF.

    Args:
        data: List of dictionaries containing transfer letter data
        tl_path: Path to the transfer letter template (.docx file)
        path: Output directory path
        transfer_letter_name: Name for the transfer letter files
        be_number: Optional BOE number
        additional_context: Optional dict of additional context variables (e.g., {'todays_date': '31/12/2025'})
    """
    os.makedirs(path, exist_ok=True)

    # Step 1: Render all DOCX files (fast — sequential is fine)
    pending_conversions = []  # list of (docx_path, pdf_path)
    for idx, context in enumerate(data, start=1):
        try:
            if additional_context:
                context = {**context, **additional_context}

            doc = DocxTemplate(tl_path)
            doc.render(context)

            license_number = context.get('license', 'LICENSE').replace('/', '_')
            serial_number = context.get('serial_number', idx)
            purchase_status = context.get('status', '')
            boe_info = context.get('boe', '')

            filename_parts = [license_number, str(serial_number)]
            if purchase_status:
                filename_parts.append(purchase_status)
            if boe_info and 'BE NUMBER:' in boe_info:
                be_num = boe_info.replace('BE NUMBER:', '').strip().replace('/', '_')
                filename_parts.append(be_num)
            if transfer_letter_name:
                clean_template_name = transfer_letter_name.replace(' ', '_').replace('/', '_')
                filename_parts.append(clean_template_name)

            base_filename = '_'.join(filename_parts)
            docx_path = os.path.join(path, f"{base_filename}.docx")
            pdf_path = os.path.join(path, f"{base_filename}.pdf")

            doc.save(docx_path)
            pending_conversions.append((docx_path, pdf_path))

        except Exception:
            logger.exception("Error rendering transfer letter %s", idx)

    if not pending_conversions:
        return []

    # Step 2: Convert all DOCX→PDF in parallel (each uses its own LO profile dir)
    conversion_failed_count = 0
    generated_files = []

    def _convert(args):
        docx_p, pdf_p = args
        return docx_p, pdf_p, convert_docx_to_pdf(docx_p, pdf_p)

    max_workers = min(2, len(pending_conversions))  # cap at 2 on low-memory servers
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for docx_p, pdf_p, success in executor.map(_convert, pending_conversions):
            if success:
                try:
                    os.remove(docx_p)
                except OSError:
                    pass
                generated_files.append(pdf_p)
            else:
                conversion_failed_count += 1
                print(f"Warning: Could not convert {os.path.basename(docx_p)} to PDF. Keeping DOCX file.")
                generated_files.append(docx_p)  # keep DOCX in output

    if conversion_failed_count > 0:
        print(f"\nWarning: {conversion_failed_count} file(s) could not be converted to PDF.")
        print("To enable PDF conversion, install one of the following:")
        print("  macOS: Microsoft Office (preferred) or LibreOffice (brew install --cask libreoffice)")
        print("  Ubuntu/Debian: sudo apt-get install libreoffice")
        print("  RHEL/CentOS: sudo yum install libreoffice")

    return generated_files
