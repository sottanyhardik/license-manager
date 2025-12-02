# allotment/views_actions.py
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from allotment.models import AllotmentModel, AllotmentItems
from allotment.serializers import AllotmentSerializer
from license.models import LicenseImportItemsModel
from license.serializers import LicenseImportItemSerializer


class AllotmentActionViewSet(ViewSet):
    """
    ViewSet for allotment actions like viewing available licenses and allocating them
    """

    @action(detail=True, methods=['get'], url_path='available-licenses')
    def available_licenses(self, request, pk=None):
        """
        Get available license import items that can be allocated to this allotment.
        Filters by available_quantity > 0 and sorts by expiry date.

        Query Parameters:
        - search: Search in license number, description, exporter name
        - license_number: Filter by license number (icontains)
        - exporter: Filter by exporter ID
        - description: Filter by description (icontains)
        - available_quantity_gte: Minimum available quantity
        - available_quantity_lte: Maximum available quantity
        - available_value_gte: Minimum available value
        - available_value_lte: Maximum available value
        - notification_number: Filter by license notification number
        - norm_class: Filter by license norm class (export license)
        - hs_code: Filter by HS code
        - is_expired: Filter expired licenses (true/false)
        """
        allotment = get_object_or_404(
            AllotmentModel.objects.prefetch_related('allotment_details__item__license__exporter'), pk=pk)

        # Get query parameters for filtering
        search = request.query_params.get('search', '')
        license_number = request.query_params.get('license_number', '')
        exporter = request.query_params.get('exporter', '')
        description = request.query_params.get('description', '')
        available_quantity_gte = request.query_params.get('available_quantity_gte', '')
        available_quantity_lte = request.query_params.get('available_quantity_lte', '')
        available_value_gte = request.query_params.get('available_value_gte', '')
        available_value_lte = request.query_params.get('available_value_lte', '')
        notification_number = request.query_params.get('notification_number', '')
        norm_class = request.query_params.get('norm_class', '')
        hs_code = request.query_params.get('hs_code', '')
        is_expired = request.query_params.get('is_expired', '')

        # Get available license import items with available quantity
        # Show all items with available quantity > 0 (including partially allocated ones)
        queryset = LicenseImportItemsModel.objects.filter(
            available_quantity__gt=0
        ).select_related('license', 'license__exporter', 'hs_code').order_by('license__license_expiry_date',
                                                                             'serial_number')

        # Apply search filter if provided
        if search:
            queryset = queryset.filter(
                Q(license__license_number__icontains=search) |
                Q(description__icontains=search) |
                Q(license__exporter__name__icontains=search)
            )

        # Apply license number filter
        if license_number:
            queryset = queryset.filter(license__license_number__icontains=license_number)

        # Apply description filter - search in description, item names, and HS code
        if description:
            queryset = queryset.filter(
                Q(description__icontains=description) |
                Q(items__name__icontains=description) |
                Q(hs_code__hs_code__icontains=description) |
                Q(hs_code__product_description__icontains=description)
            ).distinct()

        # Apply exporter filter (after description to ensure AND logic)
        if exporter:
            queryset = queryset.filter(license__exporter_id=exporter)

        # Apply available quantity filters
        if available_quantity_gte:
            try:
                queryset = queryset.filter(available_quantity__gte=Decimal(available_quantity_gte))
            except (ValueError, TypeError):
                pass

        if available_quantity_lte:
            try:
                queryset = queryset.filter(available_quantity__lte=Decimal(available_quantity_lte))
            except (ValueError, TypeError):
                pass

        # Apply available value filters
        if available_value_gte:
            try:
                queryset = queryset.filter(available_value__gte=Decimal(available_value_gte))
            except (ValueError, TypeError):
                pass

        if available_value_lte:
            try:
                queryset = queryset.filter(available_value__lte=Decimal(available_value_lte))
            except (ValueError, TypeError):
                pass

        # Apply notification number filter
        if notification_number:
            queryset = queryset.filter(license__notification_number=notification_number)

        # Apply norm class filter (through export license)
        if norm_class:
            queryset = queryset.filter(license__export_license__norm_class_id=norm_class)

        # Apply HS code filter (starts with)
        if hs_code:
            queryset = queryset.filter(hs_code__hs_code__startswith=hs_code)

        # Apply is_expired filter
        if is_expired:
            from django.utils import timezone
            today = timezone.now().date()
            if is_expired.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(license__license_expiry_date__lt=today)
            elif is_expired.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(license__license_expiry_date__gte=today)

        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))

        # Get total count
        total_count = queryset.count()

        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_queryset = queryset[start:end]

        # Serialize the data
        license_serializer = LicenseImportItemSerializer(paginated_queryset, many=True, context={'request': request})
        allotment_serializer = AllotmentSerializer(allotment, context={'request': request})

        # Add $20 buffer to required value to handle rounding issues
        # Note: Buffer is ONLY for value, NOT for quantity
        allotment_data = allotment_serializer.data
        allotment_data['required_value_with_buffer'] = str(float(allotment_data.get('required_value', 0)) + 20)

        return Response({
            'allotment': allotment_data,
            'available_items': license_serializer.data,
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        })

    @action(detail=True, methods=['post'], url_path='allocate-items')
    def allocate_items(self, request, pk=None):
        """
        Allocate selected license import items to this allotment.

        Request body:
        {
            "allocations": [
                {
                    "item_id": 123,
                    "qty": 100.00,
                    "cif_fc": 1000.00,
                    "cif_inr": 83000.00
                },
                ...
            ]
        }
        """
        allotment = get_object_or_404(AllotmentModel, pk=pk)
        allocations = request.data.get('allocations', [])

        if not allocations:
            return Response(
                {'error': 'No allocations provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_items = []
        errors = []

        for allocation in allocations:
            item_id = allocation.get('item_id')
            qty = Decimal(str(allocation.get('qty', 0)))
            cif_fc = Decimal(str(allocation.get('cif_fc', 0)))
            cif_inr = Decimal(str(allocation.get('cif_inr', 0)))

            try:
                # Get the license import item
                license_item = LicenseImportItemsModel.objects.get(id=item_id)

                # Check if available quantity is sufficient
                if license_item.available_quantity < qty:
                    errors.append({
                        'item_id': item_id,
                        'error': f'Insufficient available quantity. Available: {license_item.available_quantity}, Requested: {qty}'
                    })
                    continue

                # Check if available CIF FC is sufficient
                # CRITICAL: For restricted items, use available_value (maintained by update_restriction_balances)
                # For non-restricted items OR exception licenses (098/2009, Conversion), use calculated balance_cif_fc

                # Get calculated balance
                balance_cif_fc = Decimal(str(license_item.balance_cif_fc or 0))

                # Check if license is exception (098/2009 or Conversion)
                is_exception = (
                    license_item.license and (
                        license_item.license.notification_number == "098/2009" or
                        license_item.license.purchase_status == "CO"
                    )
                )

                # Check if item has restrictions
                has_restriction = license_item.items.filter(
                    sion_norm_class__isnull=False,
                    restriction_percentage__gt=0
                ).exists()

                # Determine which value to use
                if has_restriction and not is_exception:
                    # Restricted item, non-exception license: use stored available_value
                    stored_available = Decimal(str(license_item.available_value or 0))
                    # If available_value is not set (0 or NULL), fall back to balance_cif_fc
                    if stored_available > 0:
                        available_cif = stored_available
                    else:
                        # Not yet processed by update_restriction_balances, use calculated
                        available_cif = balance_cif_fc
                else:
                    # Non-restricted item OR exception license: use calculated balance_cif_fc
                    available_cif = balance_cif_fc

                # CRITICAL: available_cif can NEVER exceed balance_cif_fc
                if available_cif > balance_cif_fc:
                    available_cif = balance_cif_fc

                if available_cif < cif_fc:
                    errors.append({
                        'item_id': item_id,
                        'error': f'Insufficient available CIF FC. Available: {available_cif:.2f}, Requested: {cif_fc}'
                    })
                    continue

                # Check if allocation would exceed balance quantity
                from decimal import Decimal as D
                current_allotted = allotment.alloted_quantity
                required_qty = D(str(allotment.required_quantity))
                remaining_balance = required_qty - D(str(current_allotted))

                if qty > remaining_balance:
                    errors.append({
                        'item_id': item_id,
                        'error': f'Allocation exceeds balance quantity. Balance: {remaining_balance}, Requested: {qty}'
                    })
                    continue

                # Check if this item is already allocated to this allotment
                existing = AllotmentItems.objects.filter(
                    allotment=allotment,
                    item=license_item
                ).first()

                if existing:
                    # Item already exists - amend by adding to existing quantities
                    existing.qty += qty
                    existing.cif_fc += cif_fc
                    existing.cif_inr += cif_inr
                    existing.save()
                    allotment_item = existing
                else:
                    # Create new allotment item
                    allotment_item = AllotmentItems.objects.create(
                        allotment=allotment,
                        item=license_item,
                        qty=qty,
                        cif_fc=cif_fc,
                        cif_inr=cif_inr,
                        is_boe=False
                    )

                created_items.append({
                    'id': allotment_item.id,
                    'item_id': item_id,
                    'license_number': license_item.license.license_number,
                    'qty': str(qty),
                    'cif_fc': str(cif_fc),
                    'cif_inr': str(cif_inr)
                })

            except LicenseImportItemsModel.DoesNotExist:
                errors.append({
                    'item_id': item_id,
                    'error': 'License import item not found'
                })
            except Exception as e:
                errors.append({
                    'item_id': item_id,
                    'error': str(e)
                })

        return Response({
            'success': len(created_items),
            'created_items': created_items,
            'errors': errors
        }, status=status.HTTP_201_CREATED if created_items else status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete-item/(?P<item_id>[^/.]+)')
    def delete_allotment_item(self, request, pk=None, item_id=None):
        """
        Delete an allotment item (deallocate a license from this allotment).
        This will restore the available quantity to the license.
        """
        try:
            allotment_item = get_object_or_404(
                AllotmentItems,
                id=item_id,
                allotment_id=pk
            )

            license_number = allotment_item.item.license.license_number if allotment_item.item else "Unknown"
            qty = allotment_item.qty

            # Delete the allotment item (signals will handle updating available quantity)
            allotment_item.delete()

            return Response({
                'message': f'Successfully removed allocation of {qty} from {license_number}',
                'deleted_qty': str(qty)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='generate-pdf')
    def generate_pdf(self, request, pk=None):
        """
        Generate allotment letter PDF with allotment details and license information.
        """
        try:
            allotment = get_object_or_404(
                AllotmentModel.objects.select_related('company', 'port').prefetch_related(
                    'allotment_details__item__license__exporter',
                    'allotment_details__item__hs_code'
                ),
                pk=pk
            )

            # Create the HttpResponse object with PDF headers
            response = HttpResponse(content_type='application/pdf')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'Allotment_{allotment.company.name}_{timestamp}.pdf'
            response['Content-Disposition'] = f'inline; filename="{filename}"'

            # Create the PDF object using BytesIO buffer
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)

            # Container for the 'Flowable' objects
            elements = []

            # Define styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=14,
                textColor=colors.black,
                spaceAfter=12,
                alignment=TA_CENTER
            )

            header_style = ParagraphStyle(
                'CustomHeader',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.black,
                spaceAfter=6,
                alignment=TA_LEFT
            )

            # Header with timestamp
            header_text = f"Allotment Time: {datetime.now().strftime('%d %B %Y %H:%M')}"
            elements.append(Paragraph(header_text, header_style))
            elements.append(Spacer(1, 12))

            # Company details
            company_name = allotment.company.name if allotment.company else "N/A"
            company_address = getattr(allotment.company, 'address', '') or ''
            elements.append(Paragraph(f"<b>To,</b>", header_style))
            elements.append(Paragraph(f"<b>{company_name}</b>", header_style))
            if company_address:
                elements.append(Paragraph(company_address, header_style))
            elements.append(Spacer(1, 12))

            # Subject line
            total_qty = int(allotment.required_quantity or 0)
            invoice = allotment.invoice or "N/A"
            item_name = allotment.item_name or "N/A"
            subject = f"<b>Subject:</b> License Allotment for {item_name} Invoice No. {invoice} for {total_qty:,} Kg"
            elements.append(Paragraph(subject, header_style))
            elements.append(Spacer(1, 12))

            # Summary table
            summary_data = [
                ['Date', 'Item', 'Port Of Discharge'],
                [
                    allotment.estimated_arrival_date.strftime(
                        '%d/%m/%Y') if allotment.estimated_arrival_date else 'N/A',
                    item_name,
                    allotment.port.code if allotment.port else 'N/A'
                ]
            ]

            summary_table = Table(summary_data, colWidths=[1.2 * inch, 1.5 * inch, 1.2 * inch, 1.5 * inch, 1.5 * inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(summary_table)
            elements.append(Spacer(1, 18))

            # Detailed DFIA table
            detail_data = [
                ['DFIA No', 'Reg No', 'Port Code', 'Duty Type',
                 'Item Sr.No', 'Qty', 'CIF $', 'NTF No']
            ]

            # Add allotment details
            for detail in allotment.allotment_details.all():
                license_obj = detail.item.license if detail.item else None
                license_num_date = f"{license_obj.license_number}\n{license_obj.license_date.strftime('%d/%m/%Y')}" if license_obj and license_obj.license_date else (
                    license_obj.license_number if license_obj else 'N/A')
                reg_num_date = f"{license_obj.registration_number}\n{license_obj.registration_date.strftime('%d/%m/%Y')}" if license_obj and license_obj.registration_date else (
                    license_obj.registration_number if license_obj else 'N/A')

                row = [
                    license_num_date,
                    reg_num_date,
                    license_obj.port if license_obj else 'N/A',
                    'DFIA',  # Default duty type
                    str(detail.item.serial_number) if detail.item else 'N/A',
                    f"{int(detail.qty):,}",
                    f"{float(detail.cif_fc):,.2f}",
                    license_obj.notification_number if license_obj else 'N/A',
                ]
                detail_data.append(row)

            # Add totals row
            total_qty_allotted = sum(int(d.qty) for d in allotment.allotment_details.all())
            total_cif = sum(float(d.cif_fc) for d in allotment.allotment_details.all())
            detail_data.append([
                'Total', '', '', '', '',
                f"{total_qty_allotted:,}",
                f"{total_cif:,.2f}",
                ''
            ])

            detail_table = Table(detail_data,
                                 colWidths=[1.2 * inch, 1.2 * inch, 0.8 * inch, 0.7 * inch, 0.8 * inch,
                                            0.8 * inch, 0.9 * inch, 1.1 * inch])
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Make totals row bold
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ]))
            elements.append(detail_table)

            # Build PDF
            doc.build(elements)

            # Get the value of the BytesIO buffer and write it to the response
            pdf = buffer.getvalue()
            buffer.close()
            response.write(pdf)

            return response

        except Exception as e:
            return Response({
                'error': f'Failed to generate PDF: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='generate-transfer-letter')
    def generate_transfer_letter(self, request, pk=None):
        """
        Generate transfer letter for allotment using generic utility.

        Request body:
        - company_name: Company name (optional, uses allotment company if not provided)
        - address_line1: Address line 1
        - address_line2: Address line 2
        - template_id: ID of the transfer letter template
        - cif_edits: Dict of allotment_item_id -> edited CIF FC value
        """
        from core.utils.transfer_letter import generate_transfer_letter_generic

        allotment = get_object_or_404(AllotmentModel.objects.select_related('company'), id=pk)
        return generate_transfer_letter_generic(allotment, request, instance_type='allotment')
