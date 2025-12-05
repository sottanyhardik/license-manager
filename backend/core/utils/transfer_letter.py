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
