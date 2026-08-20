# allotment/views_actions.py
from datetime import datetime
from decimal import Decimal, InvalidOperation
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
from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ViewSet

from apps.accounts.permissions import AllotmentPermission
from apps.allotment.models import AllotmentModel, AllotmentItems
from apps.core.utils.exceptions import api_error, _safe_int
from apps.allotment.serializers import AllotmentSerializer
from apps.license.models import LicenseImportItemsModel
from apps.license.serializers import LicenseImportItemSerializer


class DebitBasis:
    PLAN = "PLAN"
    ACTUAL = "ACTUAL"


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
        - debit_based_on: 'actual' (default) or 'plan' — 'plan' switches the
          entire grid to one row per LicenseItemPlan line instead of per
          import item, so a single import item split across multiple
          planned items (e.g. E132's Vegetable Oil -> PKO + Cheese) shows as
          separate rows, each with only its own planned quantity/value.
        - planned_item_names: (plan mode only) filter by ItemNameModel IDs
          on the plan line itself (comma-separated)
        """
        allotment = get_object_or_404(
            AllotmentModel.objects.prefetch_related('allotment_details__item__license__exporter'), pk=pk)

        # 'plan' mode is a self-contained branch (see _available_licenses_plan_mode)
        # deliberately NOT sharing filter-application code with the Actual-mode
        # path below: duplicating the (small, stable) filter set there keeps
        # this well-tested Actual-mode path completely untouched, which is the
        # strongest guarantee that "Debit Based On = Actual" behaves exactly as
        # it always has.
        debit_based_on = (request.query_params.get('debit_based_on') or DebitBasis.PLAN).strip().upper()
        if debit_based_on == DebitBasis.PLAN:
            requested_target = (
                request.query_params.get('planning_target_item_id')
                or request.query_params.get('item_id')
                or request.query_params.get('item_names')
            )
            if allotment.planning_target_item_id and (
                not requested_target
                or str(requested_target).split(',')[0] != str(allotment.planning_target_item_id)
            ):
                raise ValidationError({
                    'code': 'PLANNING_TARGET_MISMATCH',
                    'message': 'The selected item does not match the allotment Planning Target Item.',
                })
            return self._available_licenses_plan_mode(request, allotment)
        if debit_based_on != DebitBasis.ACTUAL:
            raise ValidationError({'code': 'INVALID_DEBIT_BASIS', 'message': 'Invalid debit basis.'})

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
        item_names = request.query_params.get('item_id', '') or request.query_params.get('item_names', '')
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
            'license__notification_number',
            'license__notes',
            'hs_code'
        ).prefetch_related(
            'items',
            'items__sion_norm_class',
            'license__export_license',
            'utilization_plans',
            'utilization_plans__item_name'
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
            except (ValueError, TypeError, InvalidOperation):
                pass

        if available_quantity_lte:
            try:
                queryset = queryset.filter(available_quantity__lte=Decimal(available_quantity_lte))
            except (ValueError, TypeError, InvalidOperation):
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

        # Actual mode's value range filters use the established live
        # condition-pool value. Plan balances are deliberately absent from
        # this branch; base eligibility remains the established positive raw
        # quantity query above.
        # (available_value_calculated, via the batched available_value_
        # bulk_map — same source LicenseImportItemSerializer.get_available_
        # value uses for display), never the stored `available_value`
        # column. That column is only refreshed on certain saves and can go
        # stale (e.g. after a licence's Balance CIF formula itself changes),
        # which silently excluded licenses whose displayed value clearly
        # satisfied the filter. Not annotatable in SQL (available_value_
        # calculated is a Python property), so this filters in Python — but
        # only AFTER every other (cheap, SQL) filter above has narrowed the
        # candidate set first. This must stay the LAST filter applied: it's
        # the only one that forces full materialization + a live Balance CIF
        # computation for every remaining candidate, so running it before a
        # selective filter (e.g. license_status=active) needlessly recomputes
        # balances for licences that were always going to be excluded anyway.
        if available_value_gte or available_value_lte:
            min_value = None
            max_value = None
            if available_value_gte:
                try:
                    min_value = Decimal(available_value_gte)
                except (ValueError, TypeError, InvalidOperation):
                    min_value = None

            if available_value_lte:
                try:
                    max_value = Decimal(available_value_lte)
                except (ValueError, TypeError, InvalidOperation):
                    max_value = None

            from apps.license.services.condition_pool import available_value_bulk_map
            candidates = list(queryset)
            value_map = available_value_bulk_map(candidates)
            matching_ids = [
                item.id for item in candidates
                if (min_value is None or value_map.get(item.id, Decimal('0')) >= min_value)
                and (max_value is None or value_map.get(item.id, Decimal('0')) <= max_value)
            ]
            queryset = queryset.filter(id__in=matching_ids)

        # Pagination
        page = _safe_int(request.query_params.get('page'), default=1, minimum=1)
        page_size = min(_safe_int(request.query_params.get('page_size'), default=20, minimum=1), 100)

        # Apply pagination first, then count (more efficient for large datasets)
        start = (page - 1) * page_size
        end = start + page_size
        # Materialize once — it's reused below (serializer + optional plan lookup);
        # re-slicing the queryset twice would re-run the query and risks the two
        # reads landing in a different order.
        paginated_items = list(queryset[start:end])

        # Get total count - use a faster approximate count for large result sets
        total_count = queryset.count()

        # Batch this page's live available_value/balance_cif_fc ONCE across
        # every licence represented on the page (not once per item) — same
        # technique as `live_balance_map` for Balance CIF list views. Without
        # this, `LicenseImportItemSerializer.get_available_value` would fall
        # back to the per-item live property, re-running a licence's full
        # Balance CIF aggregate once per import item on that licence (a page
        # of 100 items across 100 different licences would multiply badly).
        from apps.license.services.condition_pool import available_value_bulk_map
        available_value_map = available_value_bulk_map(paginated_items)

        # Same batching for the two other per-item SerializerMethodFields
        # that would otherwise run one query each per row on the page:
        # `planned_quantity` (LicenseItemPlan) and `billed_no_boe`
        # (LicenseTradeLine) — mirrors `available_value_map` above.
        page_item_ids = [item.id for item in paginated_items]
        from apps.license.services.plan_reporting import plan_map_for_import_items
        plan_map = plan_map_for_import_items(page_item_ids)
        from apps.license.services.item_usage import billed_no_boe_bulk_map
        billed_no_boe_map = billed_no_boe_bulk_map(page_item_ids)

        # Serialize the data
        license_serializer = LicenseImportItemSerializer(
            paginated_items, many=True,
            context={
                'request': request,
                'available_value_map': available_value_map,
                'plan_map': plan_map,
                'billed_no_boe_map': billed_no_boe_map,
            }
        )
        allotment_serializer = AllotmentSerializer(allotment, context={'request': request})

        # Add $20 buffer to required value to handle rounding issues
        # Note: Buffer is ONLY for value, NOT for quantity
        allotment_data = allotment_serializer.data
        allotment_data['required_value_with_buffer'] = str(float(allotment_data.get('required_value', 0)) + 20)

        available_items_data = license_serializer.data

        # Attach each item's utilization-plan status — the SAME
        # Original/Used/Remaining `plan_status_for` computes for the
        # `plan_exceeded` check in `allocate_items`. Always computed (not an
        # opt-in toggle): the frontend's Max-allotment cap depends on
        # `remaining_planned_*`, so it can't be a display-only extra.
        # Batched once for the whole page via `plan_status_for_items` (fixed
        # number of queries regardless of page size) rather than calling
        # `plan_status_for` per item — that used to cost one extra group-
        # lookup + four aggregates PER item (~315 queries / ~290ms measured
        # for a 100-item page against a small dev DB).
        from apps.license.services.plan_enforcement import plan_status_for_items
        plan_status_map = plan_status_for_items(paginated_items)
        for row, item in zip(available_items_data, paginated_items):
            status = plan_status_map.get(item.id)
            row['has_plan'] = status is not None
            row['raw_available_qty'] = str(item.available_quantity or Decimal('0.000'))
            row['raw_available_cif'] = str(available_value_map.get(item.id) or Decimal('0.00'))
            if status is not None:
                row['original_planned_quantity'] = str(status['original_quantity'])
                row['used_planned_quantity'] = str(status['used_quantity'])
                row['remaining_planned_quantity'] = str(status['remaining_quantity'])
                row['original_planned_cif_fc'] = str(status['original_cif_fc'])
                row['used_planned_cif_fc'] = str(status['used_cif_fc'])
                row['remaining_planned_cif_fc'] = str(status['remaining_cif_fc'])
                row['original_planned_qty'] = row['original_planned_quantity']
                row['original_planned_cif'] = row['original_planned_cif_fc']
                row['remaining_planned_qty'] = row['remaining_planned_quantity']
                row['remaining_planned_cif'] = row['remaining_planned_cif_fc']
                row['display_plan_qty'] = row['remaining_planned_quantity']
                row['display_plan_cif'] = row['remaining_planned_cif_fc']
                row['max_allotment_qty'] = row['remaining_planned_quantity']
                row['max_allotment_cif'] = row['remaining_planned_cif_fc']
                row['row_max_allotment_qty'] = str(min(Decimal(row['raw_available_qty']), status['remaining_quantity']))
                row['row_max_allotment_cif'] = str(min(Decimal(row['raw_available_cif']), status['remaining_cif_fc']))
                row['can_create_allotment'] = status['remaining_quantity'] > 0 and status['remaining_cif_fc'] > 0
                row['reason_code'] = None if row['can_create_allotment'] else 'NO_PLANNED_BALANCE'
                row['message'] = None if row['can_create_allotment'] else 'No planned quantity or value is available for the selected item.'
            else:
                row.update({
                    'remaining_planned_qty': '0.000', 'remaining_planned_cif': '0.00',
                    'display_plan_qty': '0.000', 'display_plan_cif': '0.00',
                    'max_allotment_qty': '0.000', 'max_allotment_cif': '0.00',
                    'row_max_allotment_qty': '0.000', 'row_max_allotment_cif': '0.00',
                    'can_create_allotment': False, 'reason_code': 'NO_PLANNED_BALANCE',
                    'message': 'No active plan is available for the selected item.',
                })

        return Response({
            'allotment': allotment_data,
            'available_items': available_items_data,
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        })

    def _available_licenses_plan_mode(self, request, allotment):
        """
        Plan-mode variant of `available_licenses`: one row per
        `LicenseItemPlan` line instead of per `LicenseImportItemsModel` row.

        Mirrors the same filter set as the Actual-mode branch above, just
        reached through `import_item__` (one extra join hop, since most of
        these fields live on the underlying import item / its licence, not
        on `LicenseItemPlan` itself). Quantity/value range filters target
        `remaining_quantity`/`remaining_cif_fc` directly — plain stored
        columns on `LicenseItemPlan`, so (unlike Actual mode) no live-
        computed-value Python post-filter step is needed here.

        `remaining_quantity`/`remaining_cif_fc` are the live, independently-
        draining balance for THIS plan line (see `allocate_items`'s
        `plan_line_id` handling) — the authoritative "how much of this
        planning item is left" once Auto-Plan has generated it, never
        recalculated from the shared import item's `available_quantity`.
        `planned_quantity`/`planned_cif_fc` stay the FIXED original target.
        """
        from apps.license.models import LicenseItemPlan

        search = request.query_params.get('search', '')
        license_number = request.query_params.get('license_number', '')
        exporter = request.query_params.get('exporter', '')
        exclude_exporter = request.query_params.get('exclude_exporter', '')
        description = request.query_params.get('description', '')
        planned_quantity_gte = request.query_params.get('available_quantity_gte', '')
        planned_quantity_lte = request.query_params.get('available_quantity_lte', '')
        planned_cif_gte = request.query_params.get('available_value_gte', '')
        planned_cif_lte = request.query_params.get('available_value_lte', '')
        notification_number = request.query_params.get('notification_number', '')
        norm_class = request.query_params.get('norm_class', '')
        hs_code = request.query_params.get('hs_code', '')
        is_restricted = request.query_params.get('is_restricted', '')
        purchase_status = request.query_params.get('purchase_status', '')
        license_status = request.query_params.get('license_status', '')
        item_names = request.query_params.get('planning_target_item_id', '') or request.query_params.get('item_id', '') or request.query_params.get('item_names', '')
        # Deprecated alias: normalize external callers into the sole item filter.
        planned_item_names = request.query_params.get('planned_item_names', '')
        if not item_names and planned_item_names:
            item_names = planned_item_names
        requested_sion = request.query_params.get('sion', '')
        expiry_date_from = request.query_params.get('expiry_date_from', '')
        expiry_date_to = request.query_params.get('expiry_date_to', '')

        queryset = LicenseItemPlan.objects.filter(
            remaining_quantity__gt=0, remaining_cif_fc__gt=0,
        ).select_related(
            'import_item',
            'import_item__license',
            'import_item__license__exporter',
            'import_item__license__port',
            'import_item__license__notification_number',
            'import_item__license__notes',
            'import_item__hs_code',
            'item_name',
        ).prefetch_related(
            'import_item__items',
            'import_item__items__sion_norm_class',
            'import_item__license__export_license',
        ).order_by('import_item__license__license_expiry_date', 'import_item__serial_number')

        if search:
            queryset = queryset.filter(
                Q(import_item__license__license_number__icontains=search) |
                Q(import_item__description__icontains=search) |
                Q(import_item__license__exporter__name__icontains=search)
            )

        if license_number:
            queryset = queryset.filter(import_item__license__license_number__icontains=license_number)

        if description:
            exact_queryset = queryset.filter(
                Q(import_item__items__name__iexact=description) |
                Q(import_item__description__iexact=description) |
                Q(import_item__hs_code__product_description__iexact=description)
            ).distinct()
            if exact_queryset.exists():
                queryset = exact_queryset
            else:
                queryset = queryset.filter(
                    Q(import_item__items__name__icontains=description) |
                    Q(import_item__description__icontains=description) |
                    Q(import_item__hs_code__hs_code__icontains=description) |
                    Q(import_item__hs_code__product_description__icontains=description)
                ).distinct()

        if exporter:
            queryset = queryset.filter(import_item__license__exporter_id=exporter)

        if planned_quantity_gte:
            try:
                queryset = queryset.filter(remaining_quantity__gte=Decimal(planned_quantity_gte))
            except (ValueError, TypeError, InvalidOperation):
                pass

        if planned_quantity_lte:
            try:
                queryset = queryset.filter(remaining_quantity__lte=Decimal(planned_quantity_lte))
            except (ValueError, TypeError, InvalidOperation):
                pass

        if notification_number:
            queryset = queryset.filter(import_item__license__notification_number__code=notification_number)

        if norm_class:
            queryset = queryset.filter(import_item__license__export_license__norm_class_id=norm_class)

        if hs_code:
            queryset = queryset.filter(import_item__hs_code__hs_code__startswith=hs_code)

        if exclude_exporter:
            queryset = queryset.exclude(import_item__license__exporter_id=exclude_exporter)

        if is_restricted and is_restricted.lower() != 'all':
            if is_restricted.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(import_item__is_restricted=True)
            elif is_restricted.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(import_item__is_restricted=False)

        if purchase_status:
            status_list = [s.strip() for s in purchase_status.split(',') if s.strip()]
            if status_list:
                queryset = queryset.filter(import_item__license__purchase_status__code__in=status_list)

        if license_status and license_status.lower() != 'all':
            from django.utils import timezone
            from datetime import timedelta
            today = timezone.now().date()
            if license_status.lower() == 'active':
                queryset = queryset.filter(import_item__license__license_expiry_date__gte=today)
            elif license_status.lower() == 'expired':
                queryset = queryset.filter(import_item__license__license_expiry_date__lt=today)
            elif license_status.lower() == 'expiring_soon':
                expiring_date = today + timedelta(days=30)
                queryset = queryset.filter(
                    import_item__license__license_expiry_date__gte=today,
                    import_item__license__license_expiry_date__lte=expiring_date,
                )

        if expiry_date_from:
            try:
                from datetime import datetime as _dt
                queryset = queryset.filter(
                    import_item__license__license_expiry_date__gte=_dt.strptime(expiry_date_from, '%Y-%m-%d').date())
            except (ValueError, TypeError):
                pass

        if expiry_date_to:
            try:
                from datetime import datetime as _dt
                queryset = queryset.filter(
                    import_item__license__license_expiry_date__lte=_dt.strptime(expiry_date_to, '%Y-%m-%d').date())
            except (ValueError, TypeError):
                pass

        if item_names:
            item_name_list = [int(i.strip()) for i in item_names.split(',') if i.strip().isdigit()]
            if item_name_list:
                queryset = queryset.filter(item_name_id__in=item_name_list)

        if requested_sion:
            queryset = queryset.filter(
                import_item__license__export_license__norm_class__norm_class=requested_sion
            )

        # Planned Item Name filter — the new filter this Plan-mode branch
        # exists for: narrows to plan lines tagged with one of the selected
        # planning items (e.g. only the Palm Kernel Oil split rows).

        if planned_cif_gte:
            try:
                queryset = queryset.filter(remaining_cif_fc__gte=Decimal(planned_cif_gte))
            except (ValueError, TypeError, InvalidOperation):
                pass
        if planned_cif_lte:
            try:
                queryset = queryset.filter(remaining_cif_fc__lte=Decimal(planned_cif_lte))
            except (ValueError, TypeError, InvalidOperation):
                pass

        # Pagination — same slice-then-count pattern as Actual mode.
        page = _safe_int(request.query_params.get('page'), default=1, minimum=1)
        page_size = min(_safe_int(request.query_params.get('page_size'), default=20, minimum=1), 100)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_plans = list(queryset[start:end])
        total_count = queryset.count()

        # Serialize each row's underlying import item through the EXISTING
        # serializer — license/HS/description/exporter/condition/items_detail
        # all come for free, zero duplicated serialization logic — then
        # overlay the plan-specific fields. `available_quantity`/
        # `balance_cif_fc` are ALIASED to the plan line's own quantity/value
        # so the existing stat-bar / Max-allocation frontend code keeps
        # working unchanged in Plan mode too; the new, honest
        # `planned_quantity`/`planned_cif_fc`/`planned_item_name` fields are
        # ALSO included for the new column and mode-aware labels.
        import_items = [plan.import_item for plan in paginated_plans]
        from apps.license.services.condition_pool import available_value_bulk_map
        available_value_map = available_value_bulk_map(import_items)
        from apps.license.services.item_usage import billed_no_boe_bulk_map
        billed_no_boe_map = billed_no_boe_bulk_map([ii.id for ii in import_items])

        license_serializer = LicenseImportItemSerializer(
            import_items, many=True,
            context={
                'request': request,
                'available_value_map': available_value_map,
                'plan_map': {},  # Row 2.5's aggregate plan-status banner doesn't
                                 # apply to an already-per-plan-line row — see
                                 # the frontend, which only renders it in Actual mode.
                'billed_no_boe_map': billed_no_boe_map,
            }
        )
        allotment_serializer = AllotmentSerializer(allotment, context={'request': request})
        allotment_data = allotment_serializer.data
        allotment_data['required_value_with_buffer'] = str(float(allotment_data.get('required_value', 0)) + 20)

        available_items_data = license_serializer.data
        for row, plan in zip(available_items_data, paginated_plans):
            # `id` must be unique PER ROW (two split rows share the same
            # underlying import item) — the frontend keys React lists and its
            # allocation-draft state off `id`, so this has to be the plan
            # line's own id, not the import item's. `import_item_id` carries
            # the real underlying item for the Confirm-allot submission,
            # which must always target the actual import item regardless of
            # which split row triggered it (allocation logic itself is
            # unchanged — see AllotmentAction.tsx's allocateMutation).
            # A missing live remaining balance is not permission to fall back
            # to an historical plan target or raw source availability.
            remaining_qty = plan.remaining_quantity if plan.remaining_quantity is not None else Decimal('0.000')
            remaining_cif = plan.remaining_cif_fc if plan.remaining_cif_fc is not None else Decimal('0.00')
            row['id'] = plan.id
            row['import_item_id'] = plan.import_item_id
            row['planned_item_name'] = plan.item_name.name if plan.item_name_id else None
            row['planned_quantity'] = str(plan.planned_quantity)     # fixed original target
            row['planned_cif_fc'] = str(plan.planned_cif_fc)
            row['remaining_quantity'] = str(remaining_qty)           # live, independently-draining balance
            row['remaining_cif_fc'] = str(remaining_cif)
            row['available_quantity'] = str(remaining_qty)           # aliased for the existing stat-bar/Max-allocation UI
            row['balance_cif_fc'] = str(remaining_cif)
            row['has_active_plan'] = True
            row['remaining_planned_qty'] = str(remaining_qty)
            row['remaining_planned_cif'] = str(remaining_cif)
            row['original_planned_qty'] = str(plan.planned_quantity)
            row['original_planned_cif'] = str(plan.planned_cif_fc)
            row['display_plan_qty'] = str(remaining_qty)
            row['display_plan_cif'] = str(remaining_cif)
            row['max_allotment_qty'] = str(max(remaining_qty, Decimal('0.000')))
            row['max_allotment_cif'] = str(max(remaining_cif, Decimal('0.00')))
            row['row_max_allotment_qty'] = str(min(max(remaining_qty, Decimal('0.000')), Decimal(str(plan.import_item.available_quantity or 0))))
            row['row_max_allotment_cif'] = str(min(max(remaining_cif, Decimal('0.00')), Decimal(str(available_value_map.get(plan.import_item_id) or 0))))
            row['can_create_allotment'] = remaining_qty > 0 and remaining_cif > 0
            row['reason_code'] = None if row['can_create_allotment'] else 'NO_PLANNED_BALANCE'
            row['message'] = None if row['can_create_allotment'] else f'No planned quantity or value is available for {row["planned_item_name"] or row["description"]}.'

        return Response({
            'allotment': allotment_data,
            'available_items': available_items_data,
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
                    "cif_inr": 83000.00,
                    "plan_line_id": 456   # optional — LicenseItemPlan row id
                                          # this allocation was made against
                                          # (sent by the Plan-mode grid);
                                          # decrements that line's own
                                          # remaining_quantity/remaining_cif_fc
                                          # independently of its siblings.
                },
                ...
            ]
        }
        """
        allotment = get_object_or_404(AllotmentModel, pk=pk)
        allocations = request.data.get('allocations', [])
        # Accept the legacy per-line debit field emitted by the mounted UI as
        # well as the explicit top-level dual-mode contract.  Normalize once
        # before validation; never infer a basis from item IDs or balances.
        first_allocation = allocations[0] if allocations else {}
        explicit_search_mode = (
            request.data.get('search_mode')
            or request.data.get('debit_based_on')
            or first_allocation.get('search_mode')
            or first_allocation.get('debit_based_on')
        )
        # Preserve the pre-dual-mode endpoint contract for integrations that
        # have not yet sent identity/mode fields: a legacy plan_line_id is a
        # Plan debit; every other legacy allocation is an Actual debit.  New
        # clients must send explicit SearchMode and AllocationBasis.
        legacy_basis = DebitBasis.PLAN if first_allocation.get('plan_line_id') else DebitBasis.ACTUAL
        search_mode = str(explicit_search_mode or legacy_basis).strip().upper()
        allocation_basis = str(
            request.data.get('allocation_basis')
            or first_allocation.get('allocation_basis')
            or (search_mode if explicit_search_mode else legacy_basis)
        ).strip().upper()
        if search_mode not in (DebitBasis.PLAN, DebitBasis.ACTUAL):
            return Response({'code': 'INVALID_DEBIT_BASIS', 'error': 'Invalid debit basis.'}, status=status.HTTP_400_BAD_REQUEST)
        if allocation_basis not in (DebitBasis.PLAN, DebitBasis.ACTUAL):
            return Response({'code': 'INVALID_ALLOCATION_BASIS', 'error': 'Invalid allocation basis.'}, status=status.HTTP_400_BAD_REQUEST)
        if search_mode == DebitBasis.PLAN and allocation_basis != DebitBasis.PLAN:
            return Response({'code': 'PLAN_MODE_REQUIRES_PLAN_BASIS', 'error': 'Plan mode requires the Plan allocation basis.'}, status=status.HTTP_400_BAD_REQUEST)
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

                if search_mode == DebitBasis.ACTUAL and explicit_search_mode:
                    actual_item_id = allocation.get('actual_item_id') or request.data.get('actual_item_id')
                    if not actual_item_id or not license_item.items.filter(id=actual_item_id).exists():
                        errors.append({
                            'item_id': item_id,
                            'code': 'ACTUAL_ITEM_MISMATCH',
                            'error': 'The selected item does not match this actual licence item.',
                        })
                        continue

                # Plan-mode allocations name an exact canonical plan child.
                # Lock and validate it before consulting raw licence capacity:
                # raw availability is informational and can never revive a
                # fully consumed (or absent) planned balance.
                plan_line_id = allocation.get('plan_line_id')
                locked_plan_line = None
                if allocation_basis == DebitBasis.ACTUAL and plan_line_id:
                    errors.append({
                        'item_id': item_id,
                        'code': 'ACTUAL_ITEM_MISMATCH',
                        'error': 'Actual allocations must not include a Planning Target Item plan line.',
                    })
                    continue
                if allocation_basis == DebitBasis.PLAN and allotment.planning_target_item_id and not plan_line_id:
                    errors.append({
                        'item_id': item_id,
                        'code': 'PLANNING_TARGET_MISMATCH',
                        'error': 'A Planning Target Item plan line is required for this allotment.',
                    })
                    continue
                if allocation_basis == DebitBasis.PLAN and plan_line_id:
                    from apps.license.models import LicenseItemPlan
                    try:
                        locked_plan_line = LicenseItemPlan.objects.select_for_update().get(
                            id=plan_line_id, import_item_id=item_id,
                        )
                    except LicenseItemPlan.DoesNotExist:
                        errors.append({'item_id': item_id, 'code': 'NO_PLANNED_BALANCE',
                                       'error': 'No active plan is available for the selected item.',
                                       'max_qty': '0.000', 'max_cif': '0.00'})
                        continue
                    if (
                        allotment.planning_target_item_id
                        and locked_plan_line.item_name_id != allotment.planning_target_item_id
                    ):
                        errors.append({
                            'item_id': item_id,
                            'code': 'PLANNING_TARGET_MISMATCH',
                            'error': 'The selected item does not match the allotment Planning Target Item.',
                        })
                        continue
                    remaining_plan_qty = locked_plan_line.remaining_quantity if locked_plan_line.remaining_quantity is not None else Decimal('0.000')
                    remaining_plan_cif = locked_plan_line.remaining_cif_fc if locked_plan_line.remaining_cif_fc is not None else Decimal('0.00')
                    if remaining_plan_qty <= 0 or remaining_plan_cif <= 0:
                        item_name = locked_plan_line.item_name.name if locked_plan_line.item_name_id else 'The selected item'
                        if remaining_plan_qty <= 0 and remaining_plan_cif <= 0:
                            code = 'NO_PLANNED_BALANCE'
                            message = f'{item_name} has no remaining planned quantity or value.'
                        elif remaining_plan_qty <= 0:
                            code = 'NO_PLANNED_QTY_BALANCE'
                            message = f'{item_name} has no remaining planned quantity.'
                        else:
                            code = 'NO_PLANNED_CIF_BALANCE'
                            message = f'{item_name} has no remaining planned value.'
                        errors.append({'item_id': item_id, 'code': code,
                                       'message': message, 'error': message,
                                       'item_name': item_name, 'allocation_basis': 'PLAN',
                                       'max_qty': str(max(remaining_plan_qty, Decimal('0.000'))),
                                       'max_cif': str(max(remaining_plan_cif, Decimal('0.00')))})
                        continue
                    if qty <= 0 or cif_fc <= 0:
                        errors.append({'item_id': item_id, 'code': 'INVALID_ALLOTMENT_AMOUNT',
                                       'error': 'Quantity and value must be greater than zero.'})
                        continue
                    if qty > remaining_plan_qty or cif_fc > remaining_plan_cif:
                        errors.append({'item_id': item_id,
                                       'code': 'ALLOTMENT_QTY_EXCEEDS_PLAN' if qty > remaining_plan_qty else 'ALLOTMENT_CIF_EXCEEDS_PLAN',
                                       'error': 'Requested allotment exceeds the remaining planned balance.',
                                       'max_qty': str(remaining_plan_qty), 'max_cif': str(remaining_plan_cif)})
                        continue

                # Reject allocations against an already-expired license. Computed
                # directly off license_expiry_date (the same comparison the
                # license_status=active/expired filters above use) rather than
                # the cached LicenseFlags.is_expired column, so this can't be
                # fooled by a stale flag between nightly recalculation runs.
                from django.utils import timezone
                license_expiry_date = license_item.license.license_expiry_date
                if license_expiry_date and license_expiry_date < timezone.now().date():
                    errors.append({
                        'item_id': item_id,
                        'error': f'License has expired on {license_expiry_date}. Cannot allocate against an expired license.'
                    })
                    continue

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
                        'code': 'ALLOTMENT_QTY_EXCEEDS_ACTUAL' if allocation_basis == DebitBasis.ACTUAL else 'INSUFFICIENT_AVAILABLE_QTY',
                        'error': f'Insufficient available quantity. Available: {actual_available_qty}, Requested: {qty}'
                    })
                    continue

                # Check if available CIF FC is sufficient — always against the
                # LIVE, centralized value (`available_value_calculated`, aka
                # `balance_cif_fc`), the same one the Available Value column
                # and the Allotment "available-licenses" filter use. That
                # property already branches on `condition_type` (%/AU/open)
                # via `condition_pool` to apply restriction pooling — it does
                # NOT need a separate is_restricted / ItemNameModel.
                # restriction_percentage / "exception license" check here.
                # That older signal set predates the condition_type model and
                # is stale by design elsewhere (see the "is_restricted is no
                # longer set from ItemNameModel.restriction_percentage"
                # comments in license/signals.py, license/tasks.py, and
                # license/utils/item_matcher.py) — it was simply never
                # migrated in this one call site. Worse, it trusted the
                # stored `available_value` column outright whenever it was
                # merely non-zero (treating "non-zero" as "freshly
                # processed"), which let genuinely stale values through
                # un-checked and wrongly rejected valid allocations.
                available_cif = Decimal(str(license_item.available_value_calculated or 0))

                if available_cif < cif_fc:
                    errors.append({
                        'item_id': item_id,
                        'code': 'ALLOTMENT_CIF_EXCEEDS_ACTUAL' if allocation_basis == DebitBasis.ACTUAL else 'INSUFFICIENT_AVAILABLE_CIF',
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
                #
                # `plan_status_for` is the single source of truth for
                # Original/Used/Remaining — the same function backs the
                # Allocate screen's Planned Qty/$ display, so what's shown
                # there can never drift from what's enforced here. Remaining
                # is NOT a stored/decremented field: it's Original (from
                # LicenseItemPlan, untouched by allotment code) minus Used
                # (live-summed from AllotmentItems), so create/delete/edit of
                # an allotment automatically changes it on the next read.
                from apps.license.services.plan_enforcement import plan_status_for
                plan_status = plan_status_for(license_item) if allocation_basis == DebitBasis.PLAN else None
                if allocation_basis == DebitBasis.PLAN and plan_status is not None:
                    if plan_status["remaining_quantity"] <= 0 or plan_status["remaining_cif_fc"] <= 0:
                        errors.append({
                            'item_id': item_id, 'code': 'NO_PLANNED_BALANCE',
                            'error': 'No planned quantity or value is available for the selected item.',
                            'max_qty': str(max(plan_status["remaining_quantity"], Decimal('0.000'))),
                            'max_cif': str(max(plan_status["remaining_cif_fc"], Decimal('0.00'))),
                        })
                        continue
                    exceeds_qty = (plan_status["used_quantity"] + qty) > plan_status["original_quantity"]
                    exceeds_val = (plan_status["used_cif_fc"] + cif_fc) > plan_status["original_cif_fc"]
                    if exceeds_qty or exceeds_val:
                        msg = (
                            "Cannot allot quantity greater than remaining planned quantity."
                            if exceeds_qty else
                            "Cannot allot CIF value greater than remaining planned value."
                        )
                        errors.append({
                            'item_id': item_id,
                            'plan_exceeded': True,
                            'error': msg,
                            'original_planned_quantity': str(plan_status["original_quantity"]),
                            'used_planned_quantity': str(plan_status["used_quantity"]),
                            'remaining_planned_quantity': str(plan_status["remaining_quantity"]),
                            'original_planned_cif_fc': str(plan_status["original_cif_fc"]),
                            'used_planned_cif_fc': str(plan_status["used_cif_fc"]),
                            'remaining_planned_cif_fc': str(plan_status["remaining_cif_fc"]),
                            'requested_quantity': str(qty),
                            'requested_cif_fc': str(cif_fc),
                        })
                        continue
                elif allocation_basis == DebitBasis.PLAN:
                    errors.append({
                        'item_id': item_id, 'code': 'NO_ACTIVE_PLAN',
                        'error': 'No active plan is available for the selected item.',
                        'max_qty': '0.000', 'max_cif': '0.00',
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
                    existing.allocation_basis = allocation_basis
                    existing.planning_target_item_id = allotment.planning_target_item_id if allocation_basis == DebitBasis.PLAN else None
                    existing.plan_line = locked_plan_line if allocation_basis == DebitBasis.PLAN else None
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
                        is_boe=False,
                        allocation_basis=allocation_basis,
                        planning_target_item_id=allotment.planning_target_item_id if allocation_basis == DebitBasis.PLAN else None,
                        plan_line=locked_plan_line if allocation_basis == DebitBasis.PLAN else None,
                    )

                created_items.append({
                    'id': allotment_item.id,
                    'item_id': item_id,
                    'license_number': license_item.license.license_number,
                    'qty': str(qty),
                    'cif_fc': str(cif_fc),
                    'cif_inr': str(cif_inr)
                })

                # --- Plan-line balance tracking (Plan View allocations) -----
                # A real debit has no item_name of its own — when one import
                # item carries several plan lines (e.g. E132's Vegetable Oil
                # split into PKO + Cheese), `available_quantity` alone can't
                # say which line this allotment was meant to draw down. The
                # Plan-mode grid (views_actions.py::_available_licenses_plan_mode)
                # already knows exactly which LicenseItemPlan row the request
                # originated from and sends it as `plan_line_id` — use THAT as
                # the source of truth and decrement its own remaining balance
                # directly, independent of any sibling plan line on the same
                # import item. Absent for Actual-mode allocations (unchanged
                # behavior — no plan line to decrement).
                if locked_plan_line:
                    try:
                        plan_line = locked_plan_line
                        current_remaining = (
                            plan_line.remaining_quantity
                            if plan_line.remaining_quantity is not None
                            else plan_line.planned_quantity
                        )
                        new_remaining_qty = max(Decimal('0'), current_remaining - qty)
                        plan_line.remaining_quantity = new_remaining_qty
                        plan_line.remaining_cif_fc = new_remaining_qty * plan_line.unit_price
                        plan_line.save(update_fields=['remaining_quantity', 'remaining_cif_fc'])
                    except LicenseItemPlan.DoesNotExist:
                        # Could be stale reference (e.g. Auto-Plan regenerated this
                        # line between page load and Confirm), or plan_line_id doesn't
                        # belong to this item (security issue caught, silently ignored).
                        pass
                # ------------------------------------------------------------

            except LicenseImportItemsModel.DoesNotExist:
                errors.append({
                    'item_id': item_id,
                    'error': 'License import item not found'
                })
            except Exception:
                import logging as _log
                _log.getLogger(__name__).exception("allocate_items: failed for item_id %s", item_id)
                errors.append({'item_id': item_id, 'error': 'Allocation failed; check server logs'})

        # Refresh allotment to get updated balanced_quantity
        allotment.refresh_from_db()

        # Serialize allotment data to return updated balance
        from apps.allotment.serializers import AllotmentSerializer
        allotment_data = AllotmentSerializer(allotment).data

        # A request is an allocation transaction, not a best-effort batch.
        # Returning a 400 after an earlier row was written would otherwise
        # leave a partial allocation behind.  Mark the enclosing atomic block
        # for rollback before serialising the useful structured row errors.
        if errors:
            transaction.set_rollback(True)
            created_items = []

        return Response({
            'success': len(created_items),
            'created_items': created_items,
            'errors': errors,
            'allotment': allotment_data  # Include updated allotment with new balanced_quantity
        }, status=status.HTTP_201_CREATED if created_items else status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete-item/(?P<item_id>[^/.]+)')
    @transaction.atomic
    def delete_allotment_item(self, request, pk=None, item_id=None):
        """
        Delete an allotment item (deallocate a license from this allotment).
        This will restore the available quantity to the license.

        This is the "credit" side of the utilization-plan cap: since
        `Remaining Planned Qty/$` is computed live as Original minus a live
        SUM of `AllotmentItems` (see `plan_status_for` /
        `live_allotted_qty_for`), deleting this row automatically restores
        the remaining plan on the very next read — no explicit credit step
        needed. `@transaction.atomic` + `select_for_update()` here (matching
        `allocate_items`) close the same race window: without it, a
        concurrent `allocate-items` call on the same import item could read
        stale "already allotted" totals mid-delete.
        """
        try:
            allotment_item = get_object_or_404(
                AllotmentItems,
                id=item_id,
                allotment_id=pk
            )

            license_number = allotment_item.item.license.license_number if allotment_item.item else "Unknown"
            qty = allotment_item.qty

            # Lock the parent import item for the duration of the delete so
            # this can't interleave with a concurrent allocate-items call
            # that's mid-way through its own plan-cap check on the same item.
            if allotment_item.item_id:
                LicenseImportItemsModel.objects.select_for_update().get(id=allotment_item.item_id)

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
