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


def generate_transfer_letter_generic(instance, request, instance_type='allotment'):
    """
    Generate transfer letter for either Allotment or BOE.

    Args:
        instance: AllotmentModel or BillOfEntryModel instance
        request: DRF request object containing form data
        instance_type: 'allotment' or 'boe'

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
                instance, company_name, address_line1, address_line2, cif_edits
            )
            prefix = f'TL_ALLOT_{instance.id}'
        elif instance_type == 'boe':
            data = _prepare_boe_data(
                instance, company_name, address_line1, address_line2, cif_edits
            )
            prefix = f'TL_BOE_{instance.bill_of_entry_number}'
        else:
            return Response({
                'error': f'Invalid instance type: {instance_type}'
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
        generate_tl_software(
            data=data,
            tl_path=tl_path,
            path=file_path,
            transfer_letter_name=transfer_letter.name.replace(' ', '_')
        )

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

        # Create separate merged PDF for each license
        if unique_licenses:
            for license_obj in unique_licenses:
                # Create filename: "LICENSE_NUMBER - Copy.pdf"
                license_number = license_obj.license_number.replace('/', '_')
                merged_filename = f'{license_number} - Copy.pdf'
                merged_pdf_path = os.path.join(file_path, merged_filename)

                # Merge documents for this specific license only
                merge_license_documents([license_obj], merged_pdf_path)

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


def _prepare_allotment_data(allotment, company_name, address_line1, address_line2, cif_edits):
    """
    Prepare data for allotment transfer letter generation.
    """
    data = []

    for allotment_item in allotment.allotment_details.all():
        license_item = allotment_item.item
        if not license_item:
            continue

        license = license_item.license

        # Get edited CIF value or use original
        cif_fc = Decimal(cif_edits.get(str(allotment_item.id), allotment_item.cif_fc))
        cif_inr = cif_fc * Decimal(allotment.exchange_rate or 1)

        # Use POST data if provided, otherwise fallback to allotment company
        final_company = company_name if company_name else (allotment.company.name if allotment.company else '')
        final_address1 = address_line1 if address_line1 else ''
        final_address2 = address_line2 if address_line2 else ''

        data.append({
            'status': license.purchase_status,
            'company': final_company,
            'company_address_1': final_address1,
            'company_address_2': final_address2,
            'today': datetime.now().date().strftime("%d/%m/%Y"),
            'license': license.license_number,
            'serial_number': license_item.serial_number,
            'license_date': license.license_date.strftime("%d/%m/%Y") if license.license_date else '',
            'file_number': license.file_number or '',
            'quantity': allotment_item.qty,
            'v_allotment_inr': round(float(cif_inr), 2),
            'exporter_name': license.exporter.name if license.exporter else '',
            'v_allotment_usd': float(cif_fc),
            'boe': f"ALLOTMENT ID: {allotment.id}"
        })

    return data


def _prepare_boe_data(boe, company_name, address_line1, address_line2, cif_edits):
    """
    Prepare data for BOE transfer letter generation.
    """
    data = []

    # Use POST data if provided, otherwise fallback to BOE company
    final_company = company_name if company_name else (boe.company.name if boe.company else '')
    final_address1 = address_line1 if address_line1 else ''
    final_address2 = address_line2 if address_line2 else ''

    for item in boe.item_details.all():
        license_item = item.sr_number
        license_obj = license_item.license if license_item else None
        if not license_obj:
            continue

        # Get edited CIF value or use original
        cif_fc = Decimal(cif_edits.get(str(item.id), item.cif_fc))
        cif_inr = Decimal(cif_edits.get(str(item.id) + '_inr', item.cif_inr))

        data.append({
            'status': license_obj.purchase_status,
            'company': final_company,
            'company_address_1': final_address1,
            'company_address_2': final_address2,
            'today': datetime.now().date().strftime("%d/%m/%Y"),
            'license': license_obj.license_number,
            'serial_number': license_item.serial_number if license_item else '',
            'license_date': license_obj.license_date.strftime("%d/%m/%Y") if license_obj.license_date else '',
            'file_number': license_obj.file_number or '',
            'quantity': item.qty,
            'v_allotment_inr': round(float(cif_inr), 2),
            'exporter_name': license_obj.exporter.name if license_obj.exporter else '',
            'v_allotment_usd': float(cif_fc),
            'boe': f"BE NUMBER: {boe.bill_of_entry_number}"
        })

    return data
