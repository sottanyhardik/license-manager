"""
Generic Transfer Letter Generation Utility
Works for both Allotment and BOE
"""
import os
from datetime import datetime
from decimal import Decimal
from shutil import make_archive

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from core.models import TransferLetterModel


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
        from PyPDF2 import PdfMerger, PdfReader
        from PIL import Image
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        import io

        merger = PdfMerger()
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
            merger.write(output_path)
            merger.close()
            print(f"✓ Merged {added_count} license documents into {os.path.basename(output_path)}")
            return True
        else:
            print("✗ No license documents found to merge")
            return False

    except Exception as e:
        print(f"✗ Error merging license documents: {str(e)}")
        import traceback
        traceback.print_exc()
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
        from PyPDF2 import PdfMerger

        # Check if both files exist
        if not os.path.exists(tl_pdf_path):
            print(f"✗ Transfer letter PDF not found: {tl_pdf_path}")
            return False

        if not os.path.exists(license_copy_path):
            print(f"✗ License copy PDF not found: {license_copy_path}")
            return False

        merger = PdfMerger()

        # Add transfer letter first, then license copy
        merger.append(tl_pdf_path)
        merger.append(license_copy_path)

        # Write merged PDF
        merger.write(output_path)
        merger.close()

        print(f"✓ Created FS PDF: {os.path.basename(output_path)}")
        return True

    except Exception as e:
        print(f"✗ Error merging TL with License Copy: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def generate_transfer_letter_generic(instance, request, instance_type='allotment'):
    """
    Generate transfer letter for Allotment, BOE, or Trade.

    Args:
        instance: AllotmentModel, BillOfEntryModel, or LicenseTrade instance
        request: DRF request object containing form data
        instance_type: 'allotment', 'boe', or 'trade'

    Returns:
        Response with zip file or error message
    """
    try:
        # Extract request data
        company_name = request.data.get('company_name', '').strip()
        address_line1 = request.data.get('address_line1', '').strip()
        address_line2 = request.data.get('address_line2', '').strip()
        template_id = request.data.get('template_id')
        cif_edits = request.data.get('cif_edits', {})
        include_license_copy = request.data.get('include_license_copy', True)  # Default: True (with license copy)
        selected_items = request.data.get('selected_items', [])  # List of item IDs to include
        include_todays_date = request.data.get('include_todays_date', False)  # Include today's date in template

        if not template_id:
            return Response({
                'error': 'Template ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get transfer letter template
        transfer_letter = get_object_or_404(TransferLetterModel, pk=template_id)

        # Validate template file
        if not transfer_letter.tl:
            return Response({
                'error': 'Transfer letter template file not found'
            }, status=status.HTTP_400_BAD_REQUEST)

        tl_path = transfer_letter.tl.path

        if not os.path.exists(tl_path):
            return Response({
                'error': f'Transfer letter template file does not exist at: {tl_path}'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not tl_path.lower().endswith('.docx'):
            return Response({
                'error': 'Only DOCX templates are supported. Please upload a .docx file.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Prepare data based on instance type
        data = []

        if instance_type == 'allotment':
            data = _prepare_allotment_data(
                instance, company_name, address_line1, address_line2, cif_edits, selected_items
            )
            prefix = f'TL_ALLOT_{instance.id}'
        elif instance_type == 'boe':
            data = _prepare_boe_data(
                instance, company_name, address_line1, address_line2, cif_edits, selected_items
            )
            # Use BOE number from instance (e.g., "1234567" from bill_of_entry_number)
            boe_number = instance.bill_of_entry_number or instance.id
            prefix = f'TL_BOE_{boe_number}'
        elif instance_type == 'trade':
            data = _prepare_trade_data(
                instance, company_name, address_line1, address_line2, cif_edits, selected_items
            )
            # Use trade invoice number or ID
            trade_ref = instance.invoice_number or instance.id
            prefix = f'TL_TRADE_{trade_ref}'.replace('/', '_')
        else:
            return Response({
                'error': f'Invalid instance type: {instance_type}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate that we have data to process
        if not data:
            return Response({
                'error': 'No valid items found with license information. Please ensure the selected items have license numbers linked.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create output directory
        dir_name = f'{prefix}_{transfer_letter.name.replace(" ", "_")}'
        file_path = os.path.join(settings.MEDIA_ROOT, dir_name)

        # Clean up old directory if it exists (always generate fresh)
        import shutil
        if os.path.exists(file_path):
            shutil.rmtree(file_path)

        os.makedirs(file_path, exist_ok=True)

        # Generate transfer letters
        from allotment.scripts.aro import generate_tl_software

        # Add today's date to context if requested
        additional_context = {}
        if include_todays_date:
            from datetime import datetime
            additional_context['todays_date'] = datetime.now().strftime('%d/%m/%Y')

        generate_tl_software(
            data=data,
            tl_path=tl_path,
            path=file_path,
            transfer_letter_name=transfer_letter.name.replace(' ', '_'),
            additional_context=additional_context
        )

        # Only include license copy if requested
        if include_license_copy:
            # Collect unique licenses from the data
            unique_licenses = set()
            if instance_type == 'allotment':
                for allotment_item in instance.allotment_details.all():
                    if allotment_item.item and allotment_item.item.license:
                        unique_licenses.add(allotment_item.item.license)
            elif instance_type == 'boe':
                for item in instance.item_details.all():
                    if item.sr_number and item.sr_number.license:
                        unique_licenses.add(item.sr_number.license)
            elif instance_type == 'trade':
                for line in instance.lines.all():
                    if line.sr_number and line.sr_number.license:
                        unique_licenses.add(line.sr_number.license)

            # Create separate merged PDF for each license
            license_copy_map = {}  # Map license_number -> license_copy_path
            if unique_licenses:
                for license_obj in unique_licenses:
                    # Create filename: "LICENSE_NUMBER - Copy.pdf"
                    license_number = license_obj.license_number.replace('/', '_')
                    merged_filename = f'{license_number} - Copy.pdf'
                    merged_pdf_path = os.path.join(file_path, merged_filename)

                    # Merge documents for this specific license only
                    merge_license_documents([license_obj], merged_pdf_path)

                    # Store mapping for FS merge
                    if os.path.exists(merged_pdf_path):
                        license_copy_map[license_number] = merged_pdf_path

            # Create FS PDFs: merge each TL PDF with its corresponding License Copy
            # Keep track of which TL and Copy PDFs have FS created successfully
            successfully_merged = []  # List of (tl_path, copy_path) tuples

            # Look for all PDF files in the directory (these are the TL PDFs)
            for filename in os.listdir(file_path):
                if not filename.endswith('.pdf'):
                    continue

                # Skip the "- Copy.pdf" files themselves
                if filename.endswith(' - Copy.pdf'):
                    continue

                # Skip already created "- FS.pdf" files
                if filename.endswith(' - FS.pdf'):
                    continue

                # Extract license number from filename (first part before _)
                # Example: "0311044439_1_CO.pdf" -> "0311044439"
                license_number = filename.split('_')[0]

                # Check if we have a license copy for this license number
                if license_number in license_copy_map:
                    tl_pdf_path = os.path.join(file_path, filename)
                    license_copy_path = license_copy_map[license_number]
                    # Create filename: "LICENSE_NUMBER - FS.pdf"
                    fs_filename = f'{license_number} - FS.pdf'
                    fs_pdf_path = os.path.join(file_path, fs_filename)

                    # Merge TL + License Copy -> FS
                    if merge_tl_with_license_copy(tl_pdf_path, license_copy_path, fs_pdf_path):
                        # FS PDF created successfully - track for deletion
                        successfully_merged.append((tl_pdf_path, license_copy_path))
                        print(f"✓ Created FS PDF: {fs_filename}")

            # Delete only the TL and Copy PDFs that have FS successfully created
            for tl_path, copy_path in successfully_merged:
                try:
                    os.remove(tl_path)
                    print(f"✓ Deleted TL PDF: {os.path.basename(tl_path)}")
                except Exception as e:
                    print(f"✗ Could not delete TL PDF {os.path.basename(tl_path)}: {str(e)}")

                try:
                    os.remove(copy_path)
                    print(f"✓ Deleted Copy PDF: {os.path.basename(copy_path)}")
                except Exception as e:
                    print(f"✗ Could not delete Copy PDF {os.path.basename(copy_path)}: {str(e)}")

        # Create zip file
        file_name = f'{dir_name}.zip'
        path_to_zip = make_archive(file_path.rstrip('/'), 'zip', file_path.rstrip('/'))

        # Return zip file
        with open(path_to_zip, 'rb') as zip_file:
            response = HttpResponse(zip_file.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            return response

    except TransferLetterModel.DoesNotExist:
        return Response({
            'error': 'Transfer letter template not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'error': f'Failed to generate transfer letter: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                'today': datetime.now().date().strftime("%d/%m/%Y"),
                'license': license_number,
                'serial_number': license_item.serial_number,
                'license_date': license.license_date.strftime("%d/%m/%Y") if license.license_date else '',
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
                'today': datetime.now().date().strftime("%d/%m/%Y"),
                'license': license_number,
                'serial_number': license_item.serial_number if license_item else '',
                'license_date': license_obj.license_date.strftime("%d/%m/%Y") if license_obj.license_date else '',
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
            'today': datetime.now().date().strftime("%d/%m/%Y"),
            'license': license_obj.license_number,
            'serial_number': license_item.serial_number if license_item else '',
            'license_date': license_obj.license_date.strftime("%d/%m/%Y") if license_obj.license_date else '',
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
