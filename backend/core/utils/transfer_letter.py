"""
Generic Transfer Letter Generation Utility
Works for both Allotment and BOE
"""
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)
from decimal import Decimal
from shutil import make_archive

from django.conf import settings
from django.db.models import prefetch_related_objects
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from core.models import TransferLetterModel
from allotment.scripts.aro import convert_docx_to_pdf


def merge_license_documents(licenses, output_path):
    """
    Merge all license documents into a single PDF.

    Args:
        licenses: List of unique license objects
        output_path: Path where merged PDF should be saved

    Returns:
        True if successful, False otherwise
    """
    try:
        from pypdf import PdfWriter, PdfReader
        from PIL import Image
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        import io

        merger = PdfWriter()
        added_count = 0

        # Sort documents: TRANSFER LETTER first, then LICENSE COPY, then OTHER
        type_order = {'TRANSFER LETTER': 0, 'LICENSE COPY': 1, 'OTHER': 2}

        license_list = list(licenses)
        prefetch_related_objects(license_list, 'license_documents')
        for license_obj in license_list:
            documents = license_obj.license_documents.all()
            sorted_docs = sorted(documents, key=lambda doc: type_order.get(doc.type, 3))

            for doc in sorted_docs:
                if not doc.file:
                    continue

                # Use Django storage API so this works for local, S3, or any backend
                storage = doc.file.storage
                file_name = doc.file.name

                if not storage.exists(file_name):
                    logger.warning("File not found in storage, skipping: %s", file_name)
                    continue

                file_ext = os.path.splitext(file_name)[1].lower()

                if file_ext == '.pdf':
                    with storage.open(file_name, 'rb') as f:
                        merger.append(io.BytesIO(f.read()))
                    added_count += 1
                elif file_ext in ['.doc', '.docx']:
                    try:
                        import tempfile

                        # Download to a local temp file (convert_docx_to_pdf needs a local path)
                        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp_docx:
                            tmp_docx_path = tmp_docx.name
                            with storage.open(file_name, 'rb') as f:
                                tmp_docx.write(f.read())

                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
                            tmp_pdf_path = tmp_pdf.name

                        if convert_docx_to_pdf(tmp_docx_path, tmp_pdf_path):
                            merger.append(tmp_pdf_path)
                            added_count += 1
                            logger.debug("Converted DOCX to PDF: %s", os.path.basename(file_name))
                        else:
                            logger.warning("Failed to convert DOCX file: %s", os.path.basename(file_name))

                        for p in (tmp_docx_path, tmp_pdf_path):
                            try:
                                os.remove(p)
                            except OSError:
                                pass

                    except Exception as e:
                        logger.error("Error converting DOCX file %s: %s", os.path.basename(file_name), str(e))
                        continue
                elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    with storage.open(file_name, 'rb') as img_f:
                        img = Image.open(io.BytesIO(img_f.read()))

                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    # Create PDF from image using ReportLab
                    img_buffer = io.BytesIO()
                    img_width, img_height = img.size

                    # Use A4 size for PDF
                    canvas = pdf_canvas.Canvas(img_buffer, pagesize=A4)
                    a4_width, a4_height = A4

                    # Calculate scaling to fit image on A4 page
                    scale = min(a4_width / img_width, a4_height / img_height)
                    new_width = img_width * scale
                    new_height = img_height * scale

                    # Center image on page
                    x = (a4_width - new_width) / 2
                    y = (a4_height - new_height) / 2

                    # Use ImageReader for PIL Image object
                    img_reader = ImageReader(img)
                    canvas.drawImage(img_reader, x, y, width=new_width, height=new_height)
                    canvas.save()

                    # Rewind buffer and add to merger
                    img_buffer.seek(0)
                    pdf_reader = PdfReader(img_buffer)
                    merger.append(pdf_reader)
                    added_count += 1

        if added_count > 0:
            # Write merged PDF
            with open(output_path, 'wb') as f:
                merger.write(f)
            logger.info("Merged %d license documents into %s", added_count, os.path.basename(output_path))
            return True
        else:
            logger.warning("No license documents found to merge")
            return False

    except Exception as e:
        logger.exception("Error merging license documents")
        return False


def merge_tl_with_license_copy(tl_pdf_path, license_copy_path, output_path):
    """
    Merge Transfer Letter PDF with License Copy PDF.

    Args:
        tl_pdf_path: Path to the transfer letter PDF (e.g., "0311044439_1_CO.pdf")
        license_copy_path: Path to the license copy PDF (e.g., "0311044439 - Copy.pdf")
        output_path: Path where merged FS PDF should be saved (e.g., "0311044439 - FS.pdf")

    Returns:
        True if successful, False otherwise
    """
    try:
        from pypdf import PdfWriter

        # Check if both files exist
        if not os.path.exists(tl_pdf_path):
            logger.error("Transfer letter PDF not found: %s", tl_pdf_path)
            return False

        if not os.path.exists(license_copy_path):
            logger.error("License copy PDF not found: %s", license_copy_path)
            return False

        merger = PdfWriter()

        # Add transfer letter first, then license copy
        merger.append(tl_pdf_path)
        merger.append(license_copy_path)

        # Write merged PDF
        with open(output_path, 'wb') as f:
            merger.write(f)

        logger.info("Created FS PDF: %s", os.path.basename(output_path))
        return True

    except Exception as e:
        logger.exception("Error merging TL with License Copy")
        return False


def _cleanup_tl_files(media_root, prefix=None):
    """
    Remove all TL_ALLOT_*, TL_BOE_*, TL_TRADE_* files and folders from media_root.
    If prefix is given, also ensures that specific entry is removed.
    """
    import shutil
    tl_prefixes = ('TL_ALLOT_', 'TL_BOE_', 'TL_TRADE_')
    try:
        for entry in os.listdir(media_root):
            if any(entry.startswith(p) for p in tl_prefixes):
                full_path = os.path.join(media_root, entry)
                try:
                    if os.path.isdir(full_path):
                        shutil.rmtree(full_path)
                    elif os.path.isfile(full_path):
                        os.remove(full_path)
                except OSError as e:
                    logger.warning("Cleanup failed for %s: %s", full_path, str(e))
    except OSError as e:
        logger.warning("Could not list media root for cleanup: %s", str(e))


def _collect_unique_licenses(instance, instance_type):
    """Collect unique license objects from an instance."""
    unique_licenses = set()
    if instance_type == 'allotment':
        for item in instance.allotment_details.all():
            if item.item and item.item.license:
                unique_licenses.add(item.item.license)
    elif instance_type == 'boe':
        for item in instance.item_details.all():
            if item.sr_number and item.sr_number.license:
                unique_licenses.add(item.sr_number.license)
    elif instance_type == 'trade':
        for line in instance.lines.all():
            if line.sr_number and line.sr_number.license:
                unique_licenses.add(line.sr_number.license)
    return unique_licenses


def _copy_license_docs_to_output(unique_licenses, output_dir):
    """
    Copy all license documents from storage directly into the output directory
    so they are included as individual files in the zip alongside the TL.
    Files from the same license that share a basename are prefixed with the
    license number to prevent collisions.
    """
    import shutil
    license_list = list(unique_licenses)
    # Batch-fetch all license documents in a single query instead of N queries.
    prefetch_related_objects(license_list, 'license_documents')
    for license_obj in license_list:
        license_number = license_obj.license_number.replace('/', '_')
        for doc in license_obj.license_documents.all():
            if not doc.file:
                continue
            storage = doc.file.storage
            file_name = doc.file.name
            if not storage.exists(file_name):
                logger.warning("License doc not found in storage, skipping: %s", file_name)
                continue
            base_name = os.path.basename(file_name)
            # Always prefix with license number so _create_license_fs_pdfs can
            # reliably match every copied doc regardless of its original filename.
            # Skip the prefix if the filename already starts with the license number.
            if base_name.startswith(license_number):
                dest_name = base_name
            else:
                dest_name = f'{license_number}_{base_name}'
            dest_path = os.path.join(output_dir, dest_name)
            if os.path.exists(dest_path):
                name, ext = os.path.splitext(dest_name)
                dest_path = os.path.join(output_dir, f'{name}_dup{ext}')
            try:
                with storage.open(file_name, 'rb') as src:
                    with open(dest_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                logger.info("Included license doc in zip: %s", os.path.basename(dest_path))
            except Exception as e:
                logger.error("Failed to copy license doc %s: %s", file_name, str(e))


def _create_license_fs_pdfs(unique_licenses, output_dir, tl_files_before):
    """
    For each license, merge its generated TL PDF(s) with its copied license doc PDFs
    into a single {license_number}_FS.pdf, then remove the originals.
    tl_files_before: set of filenames that existed before _copy_license_docs_to_output ran.
    """
    try:
        from pypdf import PdfWriter
    except ImportError:
        logger.error("pypdf not installed — cannot create FS PDFs")
        return

    all_files_now = set(os.listdir(output_dir))
    copy_files = all_files_now - tl_files_before  # files added by _copy_license_docs_to_output

    for license_obj in unique_licenses:
        license_number = license_obj.license_number.replace('/', '_')

        # TL PDFs for this license: were present before copy step, start with license_number + '_'
        tl_pdfs = sorted(
            f for f in tl_files_before
            if f.startswith(license_number + '_') and f.lower().endswith('.pdf')
            and os.path.exists(os.path.join(output_dir, f))
        )

        # Copy PDFs for this license: added during copy step, contain license_number
        copy_pdfs = sorted(
            f for f in copy_files
            if license_number in f and f.lower().endswith('.pdf')
            and os.path.exists(os.path.join(output_dir, f))
        )

        if not tl_pdfs:
            continue

        try:
            merger = PdfWriter()
            for fname in tl_pdfs:
                merger.append(os.path.join(output_dir, fname))
            for fname in copy_pdfs:
                try:
                    merger.append(os.path.join(output_dir, fname))
                except Exception as e:
                    logger.warning("Skipping copy PDF %s in FS merge: %s", fname, e)

            fs_path = os.path.join(output_dir, f'{license_number}_FS.pdf')
            with open(fs_path, 'wb') as f:
                merger.write(f)
            logger.info("Created FS PDF: %s", f'{license_number}_FS.pdf')

            # Remove originals — keep any DOCX files (failed conversions)
            for fname in tl_pdfs + copy_pdfs:
                try:
                    os.remove(os.path.join(output_dir, fname))
                except OSError:
                    pass
        except Exception as e:
            logger.error("Failed to create FS PDF for license %s: %s", license_number, e)


def generate_transfer_letter_generic(instance, request, instance_type='allotment'):
    """
    Generate transfer letter for Allotment, BOE, or Trade.
    Supports multiple parties via the `parties` request field.
    Each party can have its own template.

    Args:
        instance: AllotmentModel, BillOfEntryModel, or LicenseTrade instance
        request: DRF request object containing form data
        instance_type: 'allotment', 'boe', or 'trade'

    Returns:
        Response with zip file or error message
    """
    import shutil, re

    try:
        cif_edits = request.data.get('cif_edits', {})
        include_license_copy = request.data.get('include_license_copy', True)
        selected_items = request.data.get('selected_items', [])
        include_todays_date = request.data.get('include_todays_date', False)
        output_format = request.data.get('format', 'zip')  # 'zip' | 'pdf'

        # --- Party extraction ---
        # Each party carries its own template_id.
        # Fall back to flat fields + global template_id for backward compatibility.
        raw_parties = request.data.get('parties', None)
        global_template_id = request.data.get('template_id')

        if raw_parties and isinstance(raw_parties, list) and len(raw_parties) > 0:
            parties = [
                {
                    'company_name': p.get('company_name', '').strip(),
                    'address_line1': p.get('address_line1', '').strip(),
                    'address_line2': p.get('address_line2', '').strip(),
                    'template_id': p.get('template_id') or global_template_id,
                }
                for p in raw_parties
            ]
        else:
            parties = [{
                'company_name': request.data.get('company_name', '').strip(),
                'address_line1': request.data.get('address_line1', '').strip(),
                'address_line2': request.data.get('address_line2', '').strip(),
                'template_id': global_template_id,
            }]

        # Validate all parties have a template
        for idx, party in enumerate(parties):
            if not party['template_id']:
                label = f"party {idx + 1} ({party['company_name']})" if party['company_name'] else f"party {idx + 1}"
                return Response(
                    {'error': f'Template ID is required for {label}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Build output directory prefix
        if instance_type == 'allotment':
            prefix = f'TL_ALLOT_{instance.id}'
        elif instance_type == 'boe':
            boe_number = instance.bill_of_entry_number or instance.id
            prefix = f'TL_BOE_{boe_number}'
        elif instance_type == 'trade':
            trade_ref = (instance.invoice_number or instance.id)
            prefix = f'TL_TRADE_{trade_ref}'.replace('/', '_')
        else:
            return Response({'error': f'Invalid instance type: {instance_type}'}, status=status.HTTP_400_BAD_REQUEST)

        dir_name = prefix
        output_root = os.path.join(settings.MEDIA_ROOT, dir_name)

        # Clean up any previous generation files for this instance
        _cleanup_tl_files(settings.MEDIA_ROOT, prefix)
        os.makedirs(output_root, exist_ok=True)

        additional_context = {}
        if include_todays_date:
            additional_context['todays_date'] = datetime.now().strftime('%d-%m-%Y')

        from allotment.scripts.aro import generate_tl_software

        # Collect unique licenses once (used after TL generation)
        unique_licenses = set()
        if include_license_copy:
            unique_licenses = _collect_unique_licenses(instance, instance_type)

        multi_party = len(parties) > 1
        any_data_generated = False

        for idx, party in enumerate(parties):
            company_name = party['company_name']
            address_line1 = party['address_line1']
            address_line2 = party['address_line2']
            template_id = party['template_id']

            # Load this party's template
            try:
                transfer_letter = TransferLetterModel.objects.get(pk=template_id)
            except TransferLetterModel.DoesNotExist:
                logger.warning("Template %s not found for party %d, skipping", template_id, idx + 1)
                continue

            if not transfer_letter.tl:
                logger.warning("Template %s has no file for party %d, skipping", template_id, idx + 1)
                continue

            tl_file_name = transfer_letter.tl.name
            if not tl_file_name.lower().endswith('.docx'):
                logger.warning("Template %s is not a .docx file for party %d, skipping", tl_file_name, idx + 1)
                continue

            # Download template to a local temp file — storage-agnostic (works for local, S3, etc.)
            import tempfile
            tl_storage = transfer_letter.tl.storage
            if not tl_storage.exists(tl_file_name):
                logger.warning("Template file not found in storage: %s (party %d)", tl_file_name, idx + 1)
                continue

            tmp_tl = tempfile.NamedTemporaryFile(suffix='.docx', delete=False)
            try:
                with tl_storage.open(tl_file_name, 'rb') as src:
                    tmp_tl.write(src.read())
                tmp_tl.close()
                template_path = tmp_tl.name
            except Exception as e:
                tmp_tl.close()
                try:
                    os.remove(tmp_tl.name)
                except OSError:
                    pass
                logger.error("Failed to download template %s for party %d: %s", tl_file_name, idx + 1, str(e))
                continue

            if instance_type == 'allotment':
                data = _prepare_allotment_data(instance, company_name, address_line1, address_line2, cif_edits, selected_items)
            elif instance_type == 'boe':
                data = _prepare_boe_data(instance, company_name, address_line1, address_line2, cif_edits, selected_items)
            elif instance_type == 'trade':
                data = _prepare_trade_data(instance, company_name, address_line1, address_line2, cif_edits, selected_items)
            else:
                data = []

            if not data:
                logger.warning("No data for party %d (%s), skipping", idx + 1, company_name)
                continue

            any_data_generated = True

            try:
                if multi_party:
                    # Generate to temp dir, then move files to root with party name suffix
                    temp_party_dir = os.path.join(output_root, f'__party_{idx}__')
                    os.makedirs(temp_party_dir, exist_ok=True)

                    generated = generate_tl_software(
                        data=data,
                        tl_path=template_path,
                        path=temp_party_dir,
                        transfer_letter_name=transfer_letter.name.replace(' ', '_'),
                        additional_context=additional_context
                    ) or []

                    # Rename in-place using the returned file list (avoids os.listdir race)
                    safe_name = re.sub(r'[^\w\s-]', '', company_name)[:20].strip().replace(' ', '_')
                    party_suffix = f'_{safe_name}' if safe_name else f'_Party{idx + 1}'
                    renamed = []
                    for fpath in generated:
                        if os.path.exists(fpath):
                            base, ext = os.path.splitext(os.path.basename(fpath))
                            new_name = f'{base}{party_suffix}{ext}'
                            new_path = os.path.join(temp_party_dir, new_name)
                            os.rename(fpath, new_path)
                            renamed.append(new_path)

                    # Move renamed files to output root
                    for fpath in renamed:
                        if os.path.exists(fpath):
                            shutil.move(fpath, os.path.join(output_root, os.path.basename(fpath)))
                    shutil.rmtree(temp_party_dir, ignore_errors=True)
                else:
                    generate_tl_software(
                        data=data,
                        tl_path=template_path,
                        path=output_root,
                        transfer_letter_name=transfer_letter.name.replace(' ', '_'),
                        additional_context=additional_context
                    )
            finally:
                # Always clean up the locally downloaded template temp file
                try:
                    os.remove(template_path)
                except OSError:
                    pass

        # Include the allotment PDF (same as "Download Allotment" action) in the output
        if instance_type == 'allotment':
            try:
                from allotment.scripts.allotment_pdf import generate_allotment_pdf_bytes, allotment_pdf_filename
                allotment_qs = instance.__class__.objects.select_related('company', 'port').prefetch_related(
                    'allotment_details__item__license__exporter',
                    'allotment_details__item__hs_code',
                ).get(pk=instance.pk)
                pdf_bytes = generate_allotment_pdf_bytes(allotment_qs)
                fname = allotment_pdf_filename(allotment_qs)
                with open(os.path.join(output_root, fname), 'wb') as f:
                    f.write(pdf_bytes)
                logger.info("Included allotment PDF in output: %s", fname)
            except Exception as e:
                logger.warning("Could not generate allotment PDF for zip: %s", e)

        # Snapshot TL files before copying license docs so we can distinguish them later
        tl_files_before = set(os.listdir(output_root)) if os.path.exists(output_root) else set()

        # Copy original license documents into the output dir for inclusion in zip
        if include_license_copy and unique_licenses:
            _copy_license_docs_to_output(unique_licenses, output_root)
            # Merge each license's TL PDF + Copy PDFs into a single {license}_FS.pdf
            _create_license_fs_pdfs(unique_licenses, output_root, tl_files_before)

        if not any_data_generated:
            return Response({
                'error': 'No valid items found with license information. Please ensure the selected items have license numbers linked.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if output_format == 'pdf':
            # Merge all TL PDFs in output_root into a single PDF and return directly
            import io
            from pypdf import PdfWriter
            merger = PdfWriter()
            pdf_files = sorted(
                f for f in os.listdir(output_root) if f.lower().endswith('.pdf')
            )
            for pdf_file in pdf_files:
                merger.append(os.path.join(output_root, pdf_file))

            pdf_buffer = io.BytesIO()
            merger.write(pdf_buffer)
            pdf_content = pdf_buffer.getvalue()

            _cleanup_tl_files(settings.MEDIA_ROOT, prefix)

            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{dir_name}.pdf"'
            return response

        # Create zip, read into memory, then clean up server files immediately
        file_name = f'{dir_name}.zip'
        path_to_zip = make_archive(output_root.rstrip('/'), 'zip', output_root.rstrip('/'))

        with open(path_to_zip, 'rb') as zip_file:
            zip_content = zip_file.read()

        _cleanup_tl_files(settings.MEDIA_ROOT, prefix)

        response = HttpResponse(zip_content, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response

    except Exception as e:
        logger.exception("Failed to generate transfer letter")
        return Response(
            {'error': f'Failed to generate transfer letter: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _prepare_allotment_data(allotment, company_name, address_line1, address_line2, cif_edits, selected_items=None):
    """
    Prepare data for allotment transfer letter generation.
    Groups items by license number and sums CIF values for duplicates.

    Args:
        selected_items: List of allotment_detail IDs to include (None = include all)
    """
    # Use POST data if provided, otherwise fallback to allotment company
    final_company = company_name if company_name else (allotment.company.name if allotment.company else '')
    final_address1 = address_line1 if address_line1 else ''
    final_address2 = address_line2 if address_line2 else ''

    # Group by license number to merge duplicates
    license_groups = {}

    for allotment_item in allotment.allotment_details.all():
        # Filter by selected items if provided
        if selected_items and allotment_item.id not in selected_items:
            continue

        license_item = allotment_item.item
        if not license_item:
            continue

        license = license_item.license

        # Get edited CIF value or use original
        cif_fc = Decimal(cif_edits.get(str(allotment_item.id), allotment_item.cif_fc))
        cif_inr = cif_fc * Decimal(allotment.exchange_rate or 1)

        license_number = license.license_number

        # If license already exists, sum the CIF values
        if license_number in license_groups:
            license_groups[license_number]['v_allotment_usd'] += float(cif_fc)
            license_groups[license_number]['v_allotment_inr'] += float(cif_inr)
            license_groups[license_number]['quantity'] += allotment_item.qty
        else:
            # Create new entry
            license_groups[license_number] = {
                'status': license.purchase_status.code if license.purchase_status else '',
                'company': final_company,
                'company_address_1': final_address1,
                'company_address_2': final_address2,
                'today': datetime.now().date().strftime("%d-%m-%Y"),
                'license': license_number,
                'serial_number': license_item.serial_number,
                'license_date': license.license_date.strftime("%d-%m-%Y") if license.license_date else '',
                'file_number': license.file_number or '',
                'quantity': allotment_item.qty,
                'v_allotment_inr': float(cif_inr),
                'exporter_name': license.exporter.name if license.exporter else '',
                'v_allotment_usd': float(cif_fc),
                'boe': f"ALLOTMENT ID: {allotment.id}"
            }

    # Convert to list and round the final CIF values
    data = []
    for entry in license_groups.values():
        entry['v_allotment_inr'] = round(entry['v_allotment_inr'], 2)
        entry['v_allotment_usd'] = round(entry['v_allotment_usd'], 2)
        data.append(entry)

    return data


def _prepare_boe_data(boe, company_name, address_line1, address_line2, cif_edits, selected_items=None):
    """
    Prepare data for BOE transfer letter generation.
    Groups items by license number and sums CIF values for duplicates.

    Args:
        selected_items: List of item_detail IDs to include (None = include all)
    """
    # Convert selected_items to integers if provided as strings
    if selected_items:
        selected_items = [int(item_id) if isinstance(item_id, str) else item_id for item_id in selected_items]

    # Use POST data if provided, otherwise fallback to BOE company
    final_company = company_name if company_name else (boe.company.name if boe.company else '')
    final_address1 = address_line1 if address_line1 else ''
    final_address2 = address_line2 if address_line2 else ''

    # Group by license number to merge duplicates
    license_groups = {}

    for item in boe.item_details.all():
        # Filter by selected items if provided
        if selected_items and item.id not in selected_items:
            continue

        license_item = item.sr_number
        license_obj = license_item.license if license_item else None
        if not license_obj:
            continue

        # Get edited CIF value or use original
        cif_fc = Decimal(cif_edits.get(str(item.id), item.cif_fc))
        cif_inr = Decimal(cif_edits.get(str(item.id) + '_inr', item.cif_inr))

        license_number = license_obj.license_number

        # If license already exists, sum the CIF values
        if license_number in license_groups:
            license_groups[license_number]['v_allotment_usd'] += float(cif_fc)
            license_groups[license_number]['v_allotment_inr'] += float(cif_inr)
            license_groups[license_number]['quantity'] += item.qty
        else:
            # Create new entry
            license_groups[license_number] = {
                'status': license_obj.purchase_status.code if license_obj.purchase_status else '',
                'company': final_company,
                'company_address_1': final_address1,
                'company_address_2': final_address2,
                'today': datetime.now().date().strftime("%d-%m-%Y"),
                'license': license_number,
                'serial_number': license_item.serial_number if license_item else '',
                'license_date': license_obj.license_date.strftime("%d-%m-%Y") if license_obj.license_date else '',
                'file_number': license_obj.file_number or '',
                'quantity': item.qty,
                'v_allotment_inr': float(cif_inr),
                'exporter_name': license_obj.exporter.name if license_obj.exporter else '',
                'v_allotment_usd': float(cif_fc),
                'boe': f"BE NUMBER: {boe.bill_of_entry_number}"
            }

    # Convert to list and round the final CIF values
    data = []
    for entry in license_groups.values():
        entry['v_allotment_inr'] = round(entry['v_allotment_inr'], 2)
        entry['v_allotment_usd'] = round(entry['v_allotment_usd'], 2)
        data.append(entry)

    return data


def _prepare_trade_data(trade, company_name, address_line1, address_line2, cif_edits, selected_items=None):
    """
    Prepare data for Trade transfer letter generation.

    Args:
        trade: LicenseTrade instance
        selected_items: List of trade line IDs to include (None = include all)
    """
    data = []

    # Convert selected_items to integers if provided as strings
    if selected_items:
        selected_items = [int(item_id) if isinstance(item_id, str) else item_id for item_id in selected_items]

    # Determine which company to use based on trade direction
    if trade.direction == 'PURCHASE':
        # For purchase, we're buying FROM another company (they're the exporter/seller)
        default_company = trade.from_company.name if trade.from_company else ''
        default_address1 = trade.from_addr_line_1 or ''
        default_address2 = trade.from_addr_line_2 or ''
    else:  # SALE
        # For sale, we're selling TO another company (they're the buyer)
        default_company = trade.to_company.name if trade.to_company else ''
        default_address1 = trade.to_addr_line_1 or ''
        default_address2 = trade.to_addr_line_2 or ''

    # Use POST data if provided, otherwise fallback to trade company
    final_company = company_name if company_name else default_company
    final_address1 = address_line1 if address_line1 else default_address1
    final_address2 = address_line2 if address_line2 else default_address2

    skipped_lines = []
    for line in trade.lines.all():
        # Filter by selected items if provided
        if selected_items and line.id not in selected_items:
            continue

        license_item = line.sr_number
        if not license_item:
            skipped_lines.append(f"Line {line.id}: No sr_number (license item) linked")
            continue

        license_obj = license_item.license if license_item else None
        if not license_obj:
            skipped_lines.append(f"Line {line.id} (sr_number: {license_item.serial_number}): License item has no parent license")
            continue

        # Get edited CIF value or use original
        # For trade, we use cif_inr from the line
        cif_inr = Decimal(cif_edits.get(str(line.id) + '_inr', line.cif_inr))
        cif_fc = Decimal(cif_edits.get(str(line.id), line.cif_fc))

        data.append({
            'status': license_obj.purchase_status.code if license_obj.purchase_status else '',
            'company': final_company,
            'company_address_1': final_address1,
            'company_address_2': final_address2,
            'today': datetime.now().date().strftime("%d-%m-%Y"),
            'license': license_obj.license_number,
            'serial_number': license_item.serial_number if license_item else '',
            'license_date': license_obj.license_date.strftime("%d-%m-%Y") if license_obj.license_date else '',
            'file_number': license_obj.file_number or '',
            'quantity': line.qty_kg,
            'v_allotment_inr': round(float(cif_inr), 2),
            'exporter_name': license_obj.exporter.name if license_obj.exporter else '',
            'v_allotment_usd': float(cif_fc),
            'boe': f"TRADE {trade.direction}: {trade.invoice_number or trade.id}"
        })

    # Log skipped lines for debugging
    if skipped_lines:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Trade {trade.id} transfer letter - Skipped lines: {'; '.join(skipped_lines)}")

    return data
