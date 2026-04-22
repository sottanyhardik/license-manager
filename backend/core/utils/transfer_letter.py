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

        for license_obj in licenses:
            documents = license_obj.license_documents.all()
            sorted_docs = sorted(documents, key=lambda doc: type_order.get(doc.type, 3))

            for doc in sorted_docs:
                if not doc.file:
                    continue

                file_path = doc.file.path
                if not os.path.exists(file_path):
                    continue

                file_ext = os.path.splitext(file_path)[1].lower()

                if file_ext == '.pdf':
                    # Add PDF directly
                    merger.append(file_path)
                    added_count += 1
                elif file_ext in ['.doc', '.docx']:
                    # Convert DOCX/DOC to PDF using proper conversion
                    try:
                        import tempfile

                        # Create temporary PDF file
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
                            tmp_pdf_path = tmp_pdf.name

                        # Use the reliable convert_docx_to_pdf function from aro.py
                        if convert_docx_to_pdf(file_path, tmp_pdf_path):
                            # Add converted PDF to merger
                            merger.append(tmp_pdf_path)
                            added_count += 1
                            logger.debug("Converted DOCX to PDF: %s", os.path.basename(file_path))

                            # Clean up temp file after adding to merger
                            try:
                                os.remove(tmp_pdf_path)
                            except OSError:
                                pass
                        else:
                            logger.warning("Failed to convert DOCX file: %s", os.path.basename(file_path))
                            continue

                    except Exception as e:
                        logger.error("Error converting DOCX file %s: %s", os.path.basename(file_path), str(e))
                        continue
                elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    # Convert image to PDF
                    img = Image.open(file_path)

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


def _build_license_copy_map(unique_licenses, output_dir):
    """Generate merged license copy PDFs and return a map of license_number -> pdf_path."""
    import shutil
    license_copy_map = {}
    temp_dir = os.path.join(output_dir, '__license_copies__')
    os.makedirs(temp_dir, exist_ok=True)
    for license_obj in unique_licenses:
        license_number = license_obj.license_number.replace('/', '_')
        pdf_path = os.path.join(temp_dir, f'{license_number} - Copy.pdf')
        merge_license_documents([license_obj], pdf_path)
        if os.path.exists(pdf_path):
            license_copy_map[license_number] = pdf_path
    return license_copy_map, temp_dir


def _apply_license_copies_to_dir(output_dir, license_copy_map):
    """Single-party: TL + license copy → FS PDF per license number. Removes originals."""
    import shutil
    successfully_merged = []
    for filename in os.listdir(output_dir):
        if not filename.endswith('.pdf'):
            continue
        if filename.endswith(' - Copy.pdf') or filename.endswith(' - FS.pdf'):
            continue
        license_number = filename.split('_')[0]
        if license_number not in license_copy_map:
            continue
        tl_pdf = os.path.join(output_dir, filename)
        copy_dest = os.path.join(output_dir, f'{license_number} - Copy.pdf')
        shutil.copy2(license_copy_map[license_number], copy_dest)
        fs_pdf = os.path.join(output_dir, f'{license_number} - FS.pdf')
        if merge_tl_with_license_copy(tl_pdf, copy_dest, fs_pdf):
            successfully_merged.append((tl_pdf, copy_dest))
            logger.info("Created FS PDF: %s", os.path.basename(fs_pdf))
    for tl_p, copy_p in successfully_merged:
        for f in (tl_p, copy_p):
            try:
                os.remove(f)
            except OSError as e:
                logger.warning("Could not delete %s: %s", os.path.basename(f), str(e))


def _apply_license_copies_multi_party(output_root, license_copy_map):
    """
    Multi-party: for each license number, merge ALL party TLs + one license copy
    into a single FS PDF. Removes the individual TL files afterward.
    """
    from collections import defaultdict
    from pypdf import PdfWriter

    license_tl_files = defaultdict(list)
    for fname in sorted(os.listdir(output_root)):
        if not fname.endswith('.pdf'):
            continue
        if fname.endswith(' - Copy.pdf') or fname.endswith(' - FS.pdf'):
            continue
        license_number = fname.split('_')[0]
        license_tl_files[license_number].append(os.path.join(output_root, fname))

    for license_number, tl_files in license_tl_files.items():
        if license_number not in license_copy_map:
            continue
        fs_pdf = os.path.join(output_root, f'{license_number} - FS.pdf')
        try:
            writer = PdfWriter()
            for tl_file in tl_files:
                writer.append(tl_file)
            writer.append(license_copy_map[license_number])
            with open(fs_pdf, 'wb') as f:
                writer.write(f)
            logger.info("Created merged FS PDF: %s", os.path.basename(fs_pdf))
            for tl_file in tl_files:
                try:
                    os.remove(tl_file)
                except OSError as e:
                    logger.warning("Could not delete %s: %s", os.path.basename(tl_file), str(e))
        except Exception as e:
            logger.error("Error creating FS PDF for %s: %s", license_number, str(e))


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

        # Pre-build license copy map once (shared across all parties)
        license_copy_map = {}
        temp_copy_dir = None
        if include_license_copy:
            unique_licenses = _collect_unique_licenses(instance, instance_type)
            if unique_licenses:
                license_copy_map, temp_copy_dir = _build_license_copy_map(unique_licenses, output_root)

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

            template_path = transfer_letter.tl.path
            if not os.path.exists(template_path) or not template_path.lower().endswith('.docx'):
                logger.warning("Template file invalid for party %d, skipping", idx + 1)
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

            if multi_party:
                # Generate to temp dir, then move files to root with party name as suffix
                temp_party_dir = os.path.join(output_root, f'__party_{idx}__')
                os.makedirs(temp_party_dir, exist_ok=True)

                generate_tl_software(
                    data=data,
                    tl_path=template_path,
                    path=temp_party_dir,
                    transfer_letter_name=transfer_letter.name.replace(' ', '_'),
                    additional_context=additional_context
                )

                # Rename: suffix party name onto each file (keeps license number at start)
                safe_name = re.sub(r'[^\w\s-]', '', company_name)[:20].strip().replace(' ', '_')
                party_suffix = f'_{safe_name}' if safe_name else f'_Party{idx + 1}'
                for fname in os.listdir(temp_party_dir):
                    if fname.endswith('.pdf'):
                        base, ext = os.path.splitext(fname)
                        os.rename(
                            os.path.join(temp_party_dir, fname),
                            os.path.join(temp_party_dir, f'{base}{party_suffix}{ext}')
                        )

                # Move all renamed files flat into output root
                for fname in os.listdir(temp_party_dir):
                    shutil.move(os.path.join(temp_party_dir, fname), os.path.join(output_root, fname))
                shutil.rmtree(temp_party_dir)
            else:
                generate_tl_software(
                    data=data,
                    tl_path=template_path,
                    path=output_root,
                    transfer_letter_name=transfer_letter.name.replace(' ', '_'),
                    additional_context=additional_context
                )

        # Apply license copies after all parties are done
        if include_license_copy and license_copy_map:
            if multi_party:
                # One FS per license number = all party TLs + one license copy merged
                _apply_license_copies_multi_party(output_root, license_copy_map)
            else:
                _apply_license_copies_to_dir(output_root, license_copy_map)

        # Clean up shared license copies temp directory
        if temp_copy_dir and os.path.exists(temp_copy_dir):
            shutil.rmtree(temp_copy_dir)

        if not any_data_generated:
            return Response({
                'error': 'No valid items found with license information. Please ensure the selected items have license numbers linked.'
            }, status=status.HTTP_400_BAD_REQUEST)

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
