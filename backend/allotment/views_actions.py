# allotment/views_actions.py
from decimal import Decimal
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from django.shortcuts import get_object_or_404
from django.db.models import Q, F

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
        allotment = get_object_or_404(AllotmentModel.objects.prefetch_related('allotment_details__item__license__exporter'), pk=pk)

        # Get query parameters for filtering
        search = request.query_params.get('search', '')
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
        ).select_related('license', 'license__exporter', 'hs_code').order_by('license__license_expiry_date', 'serial_number')

        # Apply search filter if provided
        if search:
            queryset = queryset.filter(
                Q(license__license_number__icontains=search) |
                Q(description__icontains=search) |
                Q(license__exporter__name__icontains=search)
            )

        # Apply description filter
        if description:
            queryset = queryset.filter(description__icontains=description)

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

        # Apply HS code filter
        if hs_code:
            queryset = queryset.filter(hs_code_id=hs_code)

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
                    errors.append({
                        'item_id': item_id,
                        'error': 'This item is already allocated to this allotment'
                    })
                    continue

                # Create the allotment item
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
