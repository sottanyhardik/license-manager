# allotment/views_actions.py
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.db import transaction
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

from apps.accounts.permissions import AllotmentPermission
from apps.allotment.models import AllotmentModel, AllotmentItems
from apps.core.utils.exceptions import api_error, _safe_int
from apps.allotment.serializers import AllotmentSerializer
from apps.license.models import LicenseImportItemsModel
from apps.license.serializers import LicenseImportItemSerializer


class AllotmentActionViewSet(ViewSet):
    """
    ViewSet for allotment actions like viewing available licenses and allocating them
    """
    permission_classes = [AllotmentPermission]

    def get_permissions(self):
        if self.action == 'generate_transfer_letter':
            from apps.accounts.permissions import TransferLetterPermission
            return [TransferLetterPermission()]
        return super().get_permissions()

    @action(detail=True, methods=['get'], url_path='available-licenses')
    def available_licenses(self, request, pk=None):
        """
        Get available license import items that can be allocated to this allotment.
        Filters by available_quantity > 0 and sorts by expiry date.

        Query Parameters:
        - search: Search in license number, description, exporter name
        - license_number: Filter by license number (icontains)
        - exporter: Filter by exporter ID
        - exclude_exporter: Exclude exporter ID
        - description: Filter by description (icontains)
        - available_quantity_gte: Minimum available quantity
        - available_quantity_lte: Maximum available quantity
        - available_value_gte: Minimum available value
        - available_value_lte: Maximum available value
        - notification_number: Filter by license notification number
        - norm_class: Filter by license norm class (export license)
        - hs_code: Filter by HS code
        - is_restricted: Filter by is_restricted flag (true/false/all)
        - purchase_status: Filter by purchase status (comma-separated)
        - license_status: Filter by license status (active/expired/expiring_soon/all)
        - item_names: Filter by item name IDs (comma-separated)
        """
        allotment = get_object_or_404(
            AllotmentModel.objects.prefetch_related('allotment_details__item__license__exporter'), pk=pk)

        # Get query parameters for filtering
        search = request.query_params.get('search', '')
        license_number = request.query_params.get('license_number', '')
        exporter = request.query_params.get('exporter', '')
        exclude_exporter = request.query_params.get('exclude_exporter', '')
        description = request.query_params.get('description', '')
        available_quantity_gte = request.query_params.get('available_quantity_gte', '')
        available_quantity_lte = request.query_params.get('available_quantity_lte', '')
        available_value_gte = request.query_params.get('available_value_gte', '')
        available_value_lte = request.query_params.get('available_value_lte', '')
        notification_number = request.query_params.get('notification_number', '')
        norm_class = request.query_params.get('norm_class', '')
        hs_code = request.query_params.get('hs_code', '')
        is_restricted = request.query_params.get('is_restricted', '')
        purchase_status = request.query_params.get('purchase_status', '')
        license_status = request.query_params.get('license_status', '')
        item_names = request.query_params.get('item_names', '')
        expiry_date_from = request.query_params.get('expiry_date_from', '')
        expiry_date_to = request.query_params.get('expiry_date_to', '')

        # Get available license import items with available quantity
        # Show all items with available quantity > 0 (including partially allocated ones)
        # Note: We explicitly use .all() to avoid any default manager filters
        queryset = LicenseImportItemsModel.objects.all().filter(
            available_quantity__gt=0
        ).select_related(
            'license',
            'license__exporter',
            'license__port',
            'hs_code'
        ).prefetch_related(
            'items',
            'items__sion_norm_class',
            'license__export_license'
        ).order_by('license__license_expiry_date', 'serial_number')

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

        # Apply description filter - prefer exact match on item name, but also include partial matches
        if description:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Filtering by description: '{description}'")

            # Strategy: Try exact match first, if none found, try partial matches
            # This prevents "Other" from matching "Mother board", "Leather", etc.

            # Try exact matches first
            # Note: For ManyToMany (items__name), we need to be careful with empty relations
            exact_queryset = queryset.filter(
                Q(items__name__iexact=description) |  # Exact match on item name
                Q(description__iexact=description) |   # Exact match on description
                Q(hs_code__product_description__iexact=description)  # Exact match on HS product description
            ).distinct()

            if exact_queryset.exists():
                queryset = exact_queryset
            else:
                # No exact matches, try partial matches
                queryset = queryset.filter(
                    Q(items__name__icontains=description) |
                    Q(description__icontains=description) |
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
            queryset = queryset.filter(license__notification_number__code=notification_number)

        # Apply norm class filter (through export license)
        if norm_class:
            queryset = queryset.filter(license__export_license__norm_class_id=norm_class)

        # Apply HS code filter (starts with)
        if hs_code:
            queryset = queryset.filter(hs_code__hs_code__startswith=hs_code)

        # Apply exclude exporter filter
        if exclude_exporter:
            queryset = queryset.exclude(license__exporter_id=exclude_exporter)

        # Apply is_restricted filter
        if is_restricted and is_restricted.lower() != 'all':
            if is_restricted.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(is_restricted=True)
            elif is_restricted.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(is_restricted=False)

        # Apply purchase_status filter
        if purchase_status:
            status_list = [s.strip() for s in purchase_status.split(',') if s.strip()]
            if status_list:
                queryset = queryset.filter(license__purchase_status__code__in=status_list)

        # Apply license_status filter
        if license_status and license_status.lower() != 'all':
            from django.utils import timezone
            from datetime import timedelta
            today = timezone.now().date()
            if license_status.lower() == 'active':
                queryset = queryset.filter(license__license_expiry_date__gte=today)
            elif license_status.lower() == 'expired':
                queryset = queryset.filter(license__license_expiry_date__lt=today)
            elif license_status.lower() == 'expiring_soon':
                # Expiring within next 30 days
                expiring_date = today + timedelta(days=30)
                queryset = queryset.filter(
                    license__license_expiry_date__gte=today,
                    license__license_expiry_date__lte=expiring_date
                )

        # Apply expiry date range filter
        if expiry_date_from:
            try:
                from datetime import datetime as _dt
                queryset = queryset.filter(license__license_expiry_date__gte=_dt.strptime(expiry_date_from, '%Y-%m-%d').date())
            except (ValueError, TypeError):
                pass

        if expiry_date_to:
            try:
                from datetime import datetime as _dt
                queryset = queryset.filter(license__license_expiry_date__lte=_dt.strptime(expiry_date_to, '%Y-%m-%d').date())
            except (ValueError, TypeError):
                pass

        # Apply item_names filter
        if item_names:
            item_name_list = [int(i.strip()) for i in item_names.split(',') if i.strip().isdigit()]
            if item_name_list:
                queryset = queryset.filter(items__id__in=item_name_list).distinct()

        # Pagination
        page = _safe_int(request.query_params.get('page'), default=1, minimum=1)
        page_size = min(_safe_int(request.query_params.get('page_size'), default=20, minimum=1), 100)

        # Apply pagination first, then count (more efficient for large datasets)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_queryset = queryset[start:end]

        # Get total count - use a faster approximate count for large result sets
        total_count = queryset.count()

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
    @transaction.atomic
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
                # Get the license import item. select_for_update locks the row for
                # the read-check-create sequence (the whole action runs in one
                # transaction via @transaction.atomic), so two concurrent
                # allocations cannot both pass the plan/availability cap.
                license_item = LicenseImportItemsModel.objects.select_for_update().get(id=item_id)

                # Use the stored available_quantity field — this is the value the
                # user sees in the Available License Items list (AVAIL QTY column)
                # and is kept in sync by update_balance_values() via post_save
                # signals. Recomputing dynamically via calculate_available_quantity
                # diverges from the UI for restricted items: it sets credit =
                # old_quantity (the already-debited amount) and returns 0 even
                # when the stored field correctly shows balance remaining.
                actual_available_qty = Decimal(str(license_item.available_quantity or 0))

                # Check if available quantity is sufficient
                if actual_available_qty < qty:
                    errors.append({
                        'item_id': item_id,
                        'error': f'Insufficient available quantity. Available: {actual_available_qty}, Requested: {qty}'
                    })
                    continue

                # Check if available CIF FC is sufficient
                # PRIORITY 1: Check is_restricted flag
                # If is_restricted=False (not restricted), always use license-level balance (balance_cif_fc)
                # If is_restricted=True AND has restriction percentage, use restricted balance logic

                # Get calculated balance
                balance_cif_fc = Decimal(str(license_item.balance_cif_fc or 0))

                # PRIORITY 1: Check is_restricted flag
                if not license_item.is_restricted:
                    # Non-restricted item: always use balance_cif_fc from property
                    available_cif = balance_cif_fc
                else:
                    # is_restricted=True: check if item has restriction percentage
                    # Check if license is exception (098/2009 or Conversion)
                    notif_code = (
                        license_item.license.notification_number.code
                        if license_item.license and license_item.license.notification_number_id
                        else None
                    )
                    is_exception = (
                        license_item.license and (
                            notif_code == "098/2009" or
                            (license_item.license.purchase_status and license_item.license.purchase_status.code == "CO")
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
                        # Exception license or no restriction percentage: use calculated balance_cif_fc
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

                # --- Utilization-plan cap (per description-group) -----------
                # A product is planned by its description group (summed across
                # serial numbers). The cumulative allotment across the WHOLE
                # group (already allotted + this request) may not exceed the
                # group's total planned qty / CIF-FC. Exceeding it returns a
                # `plan_exceeded` error so the frontend can open the planner.
                # Groups WITHOUT any plan line fall through to existing behavior.
                from django.db.models import Sum as _Sum, DecimalField as _DecimalField, Value as _Value
                from django.db.models.functions import Coalesce as _Coalesce
                from apps.license.models import LicenseItemPlan as _LIP
                from apps.license.services.plan_grouping import group_ids_of as _group_ids_of
                _gids = _group_ids_of(license_item)
                _group_plans = _LIP.objects.filter(import_item_id__in=_gids)
                plan_agg = _group_plans.aggregate(
                    pq=_Coalesce(_Sum('planned_quantity'), _Value(Decimal('0')), output_field=_DecimalField()),
                    pv=_Coalesce(_Sum('planned_cif_fc'), _Value(Decimal('0')), output_field=_DecimalField()),
                )
                if _group_plans.exists():
                    from apps.license.services.plan_enforcement import (
                        live_allotted_qty_for, live_allotted_value_for,
                    )
                    already_qty = live_allotted_qty_for(_gids)
                    already_val = live_allotted_value_for(_gids)
                    planned_qty = Decimal(str(plan_agg['pq'] or 0))
                    planned_val = Decimal(str(plan_agg['pv'] or 0))
                    if (already_qty + qty) > planned_qty or (already_val + cif_fc) > planned_val:
                        errors.append({
                            'item_id': item_id,
                            'plan_exceeded': True,
                            'error': 'Allocation exceeds the utilization plan for this item.',
                            'planned_quantity': str(planned_qty),
                            'planned_cif_fc': str(planned_val),
                            'already_allotted_quantity': str(already_qty),
                            'already_allotted_cif_fc': str(already_val),
                            'requested_quantity': str(qty),
                            'requested_cif_fc': str(cif_fc),
                            'remaining_planned_quantity': str(planned_qty - already_qty),
                            'remaining_planned_cif_fc': str(planned_val - already_val),
                        })
                        continue
                # ------------------------------------------------------------

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
                import logging as _log
                _log.getLogger(__name__).exception("allocate_items: failed for item_id %s", item_id)
                errors.append({'item_id': item_id, 'error': 'Allocation failed; check server logs'})

        # Refresh allotment to get updated balanced_quantity
        allotment.refresh_from_db()

        # Serialize allotment data to return updated balance
        from apps.allotment.serializers import AllotmentSerializer
        allotment_data = AllotmentSerializer(allotment).data

        return Response({
            'success': len(created_items),
            'created_items': created_items,
            'errors': errors,
            'allotment': allotment_data  # Include updated allotment with new balanced_quantity
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
            return Response(
                api_error('Failed to delete allotment item', e, __name__),
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['get'], url_path='generate-pdf')
    def generate_pdf(self, request, pk=None):
        """
        Generate allotment letter PDF with allotment details and license information.
        """
        from apps.allotment.scripts.allotment_pdf import generate_allotment_pdf_bytes, allotment_pdf_filename
        try:
            allotment = get_object_or_404(
                AllotmentModel.objects.select_related('company', 'port').prefetch_related(
                    'allotment_details__item__license__exporter',
                    'allotment_details__item__hs_code'
                ),
                pk=pk
            )
            pdf_bytes = generate_allotment_pdf_bytes(allotment)
            filename = allotment_pdf_filename(allotment)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response

        except Exception as e:
            return Response(
                api_error('Failed to generate PDF', e, __name__),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
        from apps.core.utils.transfer_letter import generate_transfer_letter_generic

        allotment = get_object_or_404(AllotmentModel.objects.select_related('company'), id=pk)
        return generate_transfer_letter_generic(allotment, request, instance_type='allotment')
