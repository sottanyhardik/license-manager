"""
Item-wise Pivot Report

Shows licenses with items as column headers, displaying quantities and values per item.
Similar to the GE DFIA report format.
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Any

from django.db.models import Sum, Prefetch
from django.http import JsonResponse, HttpResponse
from django.views import View
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.accounts.permissions import ReportPermission
from rest_framework.response import Response

from apps.core.constants import DEC_0, DEC_000, GE, MI, CO
from apps.core.models import ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel

def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default



logger = logging.getLogger(__name__)


class ItemPivotReportView(View):
    """
    Report showing licenses with items as columns (pivot format).

    GET parameters:
        - format: 'json' or 'excel' (default: json)
        - days: Number of days to look back (default: 30)
    """

    def get(self, request, *args, **kwargs):
        output_format = request.GET.get('format', 'json').lower()
        days = _safe_int(request.GET.get('days'), 30)
        sion_norm = request.GET.get('sion_norm')
        company_ids = request.GET.get('company_ids')  # Comma-separated company IDs
        exclude_company_ids = request.GET.get('exclude_company_ids')  # Comma-separated company IDs to exclude
        min_balance = _safe_int(request.GET.get('min_balance'), 200)
        license_status = request.GET.get('license_status', 'active')
        expiry_date_from = request.GET.get('expiry_date_from')  # YYYY-MM-DD
        expiry_date_to = request.GET.get('expiry_date_to')      # YYYY-MM-DD
        purchase_status = request.GET.get('purchase_status')    # Comma-separated codes

        # For Excel export, use streaming approach to avoid timeout
        if output_format == 'excel':
            try:
                return self.export_to_excel_streaming(days, sion_norm, company_ids, exclude_company_ids, min_balance, license_status, expiry_date_from, expiry_date_to, purchase_status)
            except Exception as e:
                logger.exception("Error exporting item pivot report to Excel")
                return JsonResponse({
                    'error': str(e)
                }, status=500)

        # For JSON, generate full report
        try:
            report_data = self.generate_report(days, sion_norm, company_ids, exclude_company_ids, min_balance,
                                               license_status, expiry_date_from, expiry_date_to, purchase_status)
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)

        return JsonResponse(report_data, safe=False)

    def generate_report(self, days: int = 30, sion_norm: str = None,
                        company_ids: str = None, exclude_company_ids: str = None,
                        min_balance: int = 200, license_status: str = 'active',
                        expiry_date_from: str = None, expiry_date_to: str = None,
                        purchase_status: str = None) -> Dict[str, Any]:
        """
        Generate item-wise pivot report.

        Args:
            days: Number of days to look back for active licenses
            sion_norm: Filter by specific SION norm class (optional)
            company_ids: Comma-separated company IDs to include (optional)
            exclude_company_ids: Comma-separated company IDs to exclude (optional)
            min_balance: Minimum balance CIF to include (default 200)
            license_status: Filter by status - 'active', 'expired', 'expiring_soon', 'all' (default 'active')

        Returns:
            Dictionary with report data
        """
        from datetime import date, timedelta
        today = date.today()
        start_date = today - timedelta(days=days)

        # Base query - licenses with required purchase status.
        # The frontend sends the chosen codes as a comma-separated string;
        # when omitted, fall back to GE / MI / CO (Global Exim, MITC,
        # Conversion) which is the historical default for this report.
        if purchase_status:
            ps_codes = [c.strip() for c in purchase_status.split(',') if c.strip()]
        else:
            ps_codes = [GE, MI, CO]
        licenses = LicenseDetailsModel.objects.filter(
            purchase_status__code__in=ps_codes
        )

        # Apply license status filter
        if license_status == 'active':
            # Active: expiry date > today - 30 days (not expired more than 30 days ago)
            licenses = licenses.filter(
                flags__is_active=True,
                license_expiry_date__gt=today - timedelta(days=30)
            )
        elif license_status == 'expired':
            # Expired: expiry date < today (don't filter by is_active to include all expired licenses)
            licenses = licenses.filter(license_expiry_date__lt=today)
        elif license_status == 'expiring_soon':
            # Expiring soon: expiry within next 30 days
            licenses = licenses.filter(
                flags__is_active=True,
                license_expiry_date__gte=today,
                license_expiry_date__lte=today + timedelta(days=30)
            )
        # If 'all', no date or is_active filter applied - shows everything

        # Apply explicit expiry date range filter (overrides license_status date logic if provided)
        if expiry_date_from:
            from datetime import datetime as _dt
            licenses = licenses.filter(license_expiry_date__gte=_dt.strptime(expiry_date_from, '%Y-%m-%d').date())
        if expiry_date_to:
            from datetime import datetime as _dt
            licenses = licenses.filter(license_expiry_date__lte=_dt.strptime(expiry_date_to, '%Y-%m-%d').date())

        # Filter by SION norm if specified (optional)
        if sion_norm:
            licenses = licenses.filter(export_license__norm_class__norm_class=sion_norm).distinct()

        # Filter by company IDs if specified
        if company_ids:
            company_id_list = [int(cid.strip()) for cid in company_ids.split(',') if cid.strip()]
            licenses = licenses.filter(exporter_id__in=company_id_list)

        # Exclude company IDs if specified
        if exclude_company_ids:
            exclude_id_list = [int(cid.strip()) for cid in exclude_company_ids.split(',') if cid.strip()]
            licenses = licenses.exclude(exporter_id__in=exclude_id_list)

        # Filter by min_balance at database level using stored balance_cif field
        # This dramatically reduces the number of licenses we need to process
        licenses = licenses.filter(balance__balance_cif__gte=min_balance)

        # Build filtered prefetch querysets based on sion_norm
        import_items_qs = LicenseImportItemsModel.objects.select_related('hs_code')
        export_items_qs = LicenseExportItemModel.objects.select_related('norm_class')
        item_names_qs = ItemNameModel.objects.filter(is_active=True).select_related('sion_norm_class')

        # If sion_norm specified, filter prefetch queries to only that norm.
        if sion_norm:
            item_names_qs = item_names_qs.filter(sion_norm_class__norm_class=sion_norm)
            export_items_qs = export_items_qs.filter(norm_class__norm_class=sion_norm)

        # Optimize with select_related and prefetch_related to reduce queries.
        # balance_cif / balance_report_notes / condition_sheet / current_owner now
        # live on OneToOne sub-tables (LicenseBalance / LicenseNotes / LicenseOwnership);
        # they're accessed via @property shims, so pull the sub-rows in one shot.
        licenses = licenses.select_related(
            'exporter',
            'port',
            'balance',
            'notes',
            'ownership__current_owner',
            'purchase_status',
        ).prefetch_related(
            Prefetch('import_license',
                     queryset=import_items_qs.prefetch_related(
                         Prefetch('items', queryset=item_names_qs)
                     ).only('id', 'license_id', 'hs_code_id', 'quantity', 'allotted_quantity',
                            'debited_quantity', 'available_quantity', 'debited_value', 'cif_fc', 'description',
                            'condition_type', 'serial_number')),
            Prefetch('export_license',
                     queryset=export_items_qs.only('id', 'license_id', 'norm_class_id', 'cif_fc')),
            'license_documents',
            'transfers'
        ).order_by('license_expiry_date', 'license_date')

        # Collect all unique items across all licenses
        # Use list() with prefetch_related for optimal performance (iterator breaks prefetch)
        all_items = {}  # Changed to dict to store item object for sorting
        valid_licenses = list(licenses)  # Licenses already filtered by balance_cif at DB level

        for license_obj in valid_licenses:
            for import_item in license_obj.import_license.all():
                for item in import_item.items.all():
                    # Only add items with valid names and that are active (is_active=False hides from pivot)
                    if item and item.name and item.is_active:
                        # If filtering by norm, only include items matching that norm
                        if sion_norm:
                            if item.sion_norm_class and item.sion_norm_class.norm_class == sion_norm:
                                all_items[item.id] = item
                        else:
                            all_items[item.id] = item

        # ── "As per planning" per-DFIA item map ────────────────────────────
        # When a DFIA carries a manual utilization plan (LicenseItemPlan), the
        # pivot must show that licence's items *as planned* rather than every
        # import item present on the licence: each row shows only the items that
        # DFIA actually planned, blanking the rest (e.g. BORAX is hidden on the
        # A3627 DFIAs that did not plan it, but still shown on those that did).
        #
        # Licences with NO manual plan are left untouched — they show all their
        # import items as before — so norm-driven norms (E1 / E5 / E132) are
        # unaffected. Column headers remain the union across the report; the
        # filtering is per row/cell in _build_license_row().
        from apps.license.models import LicenseItemPlan

        # import_item_id -> first attached item id, mirroring how a plan's
        # totals are attributed to a single item name in _build_license_row().
        first_item_of_import = {}
        for _lo in valid_licenses:
            for _ii in _lo.import_license.all():
                for _it in _ii.items.all():
                    first_item_of_import[_ii.id] = _it.id
                    break

        # license_id -> {item_id: {'q': planned qty, 'cif': planned CIF-FC}}.
        # Attributed to the plan LINE's own item_name (not the import item's
        # first attached name) so e.g. a RUTILE plan line on a BORAX+RUTILE
        # import item lands on RUTILE. Untagged split lines fall back to the
        # import item's first attached name. The key set doubles as "which
        # items this DFIA planned" for the per-row filter below.
        plan_totals_by_license = defaultdict(
            lambda: defaultdict(lambda: {'q': Decimal('0.000'), 'cif': Decimal('0.00')})
        )
        for _pl in (LicenseItemPlan.objects
                    .filter(license_id__in=[_lo.id for _lo in valid_licenses])
                    .values('license_id', 'import_item_id', 'item_name_id',
                            'planned_quantity', 'planned_cif_fc')):
            _iname = _pl['item_name_id'] or first_item_of_import.get(_pl['import_item_id'])
            if _iname is None:
                continue
            _cell = plan_totals_by_license[_pl['license_id']][_iname]
            _cell['q'] += _pl['planned_quantity'] or Decimal('0')
            _cell['cif'] += _pl['planned_cif_fc'] or Decimal('0')

        # Sort items by display_order first, then by name for consistent column order
        sorted_items = sorted(
            [(item.id, item.name) for item in all_items.values()],
            key=lambda x: (all_items[x[0]].display_order, x[1] or '')
        )

        # Build license data with item columns, grouped by norm first, then notification
        # (defaultdict is imported at module level).
        licenses_by_norm_notification = defaultdict(lambda: defaultdict(list))

        for license_obj in valid_licenses:
            license_row = self._build_license_row(
                license_obj, sorted_items,
                item_plan_totals=plan_totals_by_license.get(license_obj.id),
            )

            if license_row:
                # Handle blank/empty notification numbers
                notification = (license_obj.notification_number.code if license_obj.notification_number_id else '').strip()
                if not notification:
                    notification = 'Unknown'

                # Get norm class from license
                norm_class = 'Unknown'
                if license_obj.export_license.exists():
                    first_export = license_obj.export_license.first()
                    if first_export and first_export.norm_class:
                        norm_class = first_export.norm_class.norm_class

                # Define conversion norms
                conversion_norms = ['E1', 'E5', 'E126', 'E132']
                is_conversion = license_obj.purchase_status and license_obj.purchase_status.code == CO

                # Get exporter name for split sheet logic
                exporter_name = (license_obj.exporter.name or '') if license_obj.exporter else ''
                exporter_name_upper = exporter_name.upper()

                # Determine exporter category for split sheets
                exporter_category = None
                if 'PARLE' in exporter_name_upper:
                    exporter_category = 'Parle'
                elif 'HALDIRAM SNACKS' in exporter_name_upper:
                    exporter_category = 'Haldiram Snacks'
                elif 'HALDIRAM FOODS' in exporter_name_upper:
                    exporter_category = 'Haldiram Foods'
                elif 'HARIOMKAR FOOD' in exporter_name_upper:
                    exporter_category = 'Hariomkar Food'

                # Build notification key based on norm class and purchase status
                if norm_class in conversion_norms and is_conversion:
                    # For conversion licenses in E1, E5, E126, E132
                    if norm_class in ['E5', 'E132']:
                        # E5 and E132 Conversion: split by exporter category
                        if exporter_category:
                            notification_key = f"{notification} - Conversion - {exporter_category}"
                        else:
                            notification_key = f"{notification} - Conversion"
                    else:
                        # E1, E126 Conversion
                        notification_key = f"{notification} - Conversion"

                elif norm_class in ['E5', 'E132']:
                    # E5 and E132 non-conversion: split by exporter category
                    if exporter_category:
                        notification_key = f"{notification} - {exporter_category}"
                    else:
                        notification_key = f"{notification} - Others"

                else:
                    # Regular grouping by notification for other norms
                    notification_key = notification

                # Split every pivot table by PURCHASE STATUS: prefix the group
                # key with the licence's purchase-status label so each rendered
                # table (and its summary / totals / Excel sheet, which all key off
                # this group) contains a single purchase status. The " — " (em
                # dash) delimiter is distinct from the " - " used inside
                # notification_key, so the frontend can split it back apart.
                ps_label = (license_row.get('purchase_status_label')
                            or license_row.get('purchase_status_code') or 'Unknown')
                notification_key = f"{ps_label} — {notification_key}"

                licenses_by_norm_notification[norm_class][notification_key].append(license_row)

        # Determine which items have restrictions
        items_with_restrictions = set()
        for norm_dict in licenses_by_norm_notification.values():
            for licenses_list in norm_dict.values():
                for license_row in licenses_list:
                    for item_id, item_name in sorted_items:
                        item_data = license_row.get('items', {}).get(item_name, {})
                        if item_data.get('restriction') is not None:
                            items_with_restrictions.add(item_id)

        # Convert nested defaultdict to regular dict
        result_dict = {}
        for norm, notification_dict in licenses_by_norm_notification.items():
            result_dict[norm] = dict(notification_dict)

        # Fetch notes and conditions for all norms in a single query
        from apps.core.models import SionNormClassModel
        norm_classes_list = list(result_dict.keys())
        sion_norms = SionNormClassModel.objects.filter(
            norm_class__in=norm_classes_list
        ).prefetch_related('notes', 'conditions')

        # Build dict from fetched norms
        norm_notes_conditions = {}
        sion_norms_dict = {sn.norm_class: sn for sn in sion_norms}

        for norm_class in norm_classes_list:
            if norm_class in sion_norms_dict:
                sion_norm = sion_norms_dict[norm_class]
                norm_notes_conditions[norm_class] = {
                    'notes': [
                        {'note_text': note.note_text, 'display_order': note.display_order}
                        for note in sion_norm.notes.all()
                    ],
                    'conditions': [
                        {'condition_text': cond.condition_text, 'display_order': cond.display_order}
                        for cond in sion_norm.conditions.all()
                    ]
                }
            else:
                norm_notes_conditions[norm_class] = {'notes': [], 'conditions': []}

        return {
            'items': [
                {
                    'id': item_id,
                    'name': item_name,
                    'has_restriction': item_id in items_with_restrictions
                }
                for item_id, item_name in sorted_items
            ],
            'licenses_by_norm_notification': result_dict,
            'norm_notes_conditions': norm_notes_conditions,
            'report_date': today.isoformat(),
        }

    def _build_license_row(self, license_obj: LicenseDetailsModel, all_items: List[tuple],
                           item_plan_totals=None) -> Dict[str, Any]:
        """
        Build a single license row with item columns.

        Args:
            license_obj: LicenseDetailsModel instance
            all_items: List of (item_id, item_name) tuples
            item_plan_totals: When the DFIA is manually planned, a map
                {item_id: {'q': planned qty, 'cif': planned CIF-FC}} of the items
                it actually planned. Drives the per-cell Planned QTY / Planned
                CIF and the "as per planning" filter: items outside this map are
                emitted as empty cells. None => not manually planned, so every
                import item is shown as before.

        Returns:
            Dictionary with license data and item quantities
        """
        # Calculate total CIF from export license items (already prefetched)
        # Start with Decimal('0') to ensure result is always Decimal type
        total_cif = Decimal('0')
        for item in license_obj.export_license.all():
            # Convert to Decimal to handle cases where database returns float
            cif_value = Decimal(str(item.cif_fc)) if item.cif_fc is not None else Decimal('0')
            total_cif += cif_value

        # Calculate Alloted CIF from DFIA allotments that don't have BOE
        from apps.allotment.models import AllotmentItems
        alloted_cif = Decimal('0')
        # Get allotment items for this license where allotment is marked as allotted
        # and is NOT linked to any bill_of_entry (meaning no BOE exists for this allotment)
        allotment_items = AllotmentItems.objects.filter(
            item__license=license_obj,
            allotment__is_allotted=True,
            allotment__bill_of_entry__isnull=True  # No BOE linked to this allotment
        ).select_related('allotment')

        for allot_item in allotment_items:
            alloted_cif += Decimal(str(allot_item.cif_fc)) if allot_item.cif_fc is not None else Decimal('0')

        # Debited CIF = CIF already debited (via BOE) across this licence's import
        # items — the same `debited_value` field the restriction pools treat as
        # debited_cif below. import_license is prefetched, so no extra query.
        debited_cif = Decimal('0')
        for import_item in license_obj.import_license.all():
            debited_cif += Decimal(str(import_item.debited_value)) if import_item.debited_value is not None else DEC_0

        # Aggregate quantities by item (sum across all serial numbers)
        item_quantities = defaultdict(lambda: {
            'quantity': Decimal('0.000'),
            'allotted_quantity': Decimal('0.000'),
            'debited_quantity': Decimal('0.000'),
            'available_quantity': Decimal('0.000'),
            'debited_value': Decimal('0.00'),
            'cif_value': Decimal('0.00'),
            'hs_code': '',
            'description': '',
            'sion_norm_class': None,
            'restriction_percentage': None,
            'condition_type': '',
            # User-authored utilization plan (summed across an item's splits).
            'plan_quantity': Decimal('0.000'),
            'plan_cif': Decimal('0.00'),
        })

        # Per-import-item utilization plan totals for this license (one query).
        from apps.license.services.plan_reporting import plan_map_for_license
        _plan_map = plan_map_for_license(license_obj.id)

        # Per condition_type pool — new restriction model. Each "N%" pool is
        # shared by every import item on this licence with that condition_type,
        # and provides the per-cell `restriction_value` shown in the pivot.
        from apps.license.services.condition_pool import compute_condition_pools
        condition_pools = compute_condition_pools(license_obj)
        # condition_pools = {"2%": Decimal(...), "3%": Decimal(...), ...}

        # (Legacy restriction_groups kept ONLY for backward compatibility with
        # callers that still read it; unused for the cell-level value now.)
        restriction_groups = defaultdict(lambda: {
            'total_cif': Decimal('0.00'),
            'debited_cif': Decimal('0.00'),
            'available_cif': Decimal('0.00'),
            'restriction_percentage': None,
            'sion_norm_class': None,
            'item_ids': []
        })

        for import_item in license_obj.import_license.all():
            # Plan totals are now sourced per plan-line item_name via
            # `item_plan_totals` (see the item-columns loop below); the old
            # first-attached-name attribution is gone as it mis-assigned plans
            # on multi-name import items (e.g. RUTILE on a BORAX+RUTILE item).
            for item in import_item.items.all():
                # Convert all numeric fields to Decimal to handle potential float values from database
                item_quantities[item.id]['quantity'] += Decimal(str(import_item.quantity)) if import_item.quantity is not None else DEC_000
                item_quantities[item.id]['allotted_quantity'] += Decimal(str(import_item.allotted_quantity)) if import_item.allotted_quantity is not None else DEC_000
                item_quantities[item.id]['debited_quantity'] += Decimal(str(import_item.debited_quantity)) if import_item.debited_quantity is not None else DEC_000
                item_quantities[item.id]['available_quantity'] += Decimal(str(import_item.available_quantity)) if import_item.available_quantity is not None else DEC_000
                item_quantities[item.id]['debited_value'] += Decimal(str(import_item.debited_value)) if import_item.debited_value is not None else DEC_0
                item_quantities[item.id]['cif_value'] += Decimal(str(import_item.cif_fc)) if import_item.cif_fc is not None else DEC_0

                if import_item.hs_code and not item_quantities[item.id]['hs_code']:
                    item_quantities[item.id]['hs_code'] = import_item.hs_code.hs_code

                if import_item.description and not item_quantities[item.id]['description']:
                    item_quantities[item.id]['description'] = import_item.description

                # Carry the licence-condition badge through to the pivot cell.
                # If multiple import-item rows map to the same item-name, the
                # first non-empty condition wins (typical case: each item-name
                # appears on one serial number per licence).
                if import_item.condition_type and not item_quantities[item.id]['condition_type']:
                    item_quantities[item.id]['condition_type'] = import_item.condition_type

                # Get restriction from item's sion_norm_class and restriction_percentage
                if item and hasattr(item, 'sion_norm_class') and item.sion_norm_class:
                    sion_norm = item.sion_norm_class.norm_class
                    restriction_pct = item.restriction_percentage

                    item_quantities[item.id]['sion_norm_class'] = sion_norm
                    item_quantities[item.id]['restriction_percentage'] = restriction_pct

                    # Group by (sion_norm_class, restriction_percentage) for shared restriction calculation
                    # Items in same SION norm with same restriction % share the restriction limit
                    restriction_key = f"{sion_norm}_{restriction_pct}"
                    restriction_groups[restriction_key]['sion_norm_class'] = sion_norm
                    restriction_groups[restriction_key]['restriction_percentage'] = restriction_pct
                    # Convert to Decimal to handle potential float values from database
                    restriction_groups[restriction_key]['total_cif'] += Decimal(str(import_item.cif_fc)) if import_item.cif_fc is not None else DEC_0
                    restriction_groups[restriction_key]['debited_cif'] += Decimal(str(import_item.debited_value)) if import_item.debited_value is not None else DEC_0
                    if item.id not in restriction_groups[restriction_key]['item_ids']:
                        restriction_groups[restriction_key]['item_ids'].append(item.id)

        # Calculate available CIF within restriction for each group
        # Use stored balance_cif field instead of property to avoid extra queries
        # Convert to Decimal to handle potential float value from database
        balance_cif = Decimal(str(license_obj.balance_cif)) if license_obj.balance_cif is not None else Decimal('0')
        for group_name, group_data in restriction_groups.items():
            if group_data['restriction_percentage'] and total_cif > 0:
                # Convert restriction_percentage to Decimal to avoid float * Decimal error
                restriction_pct_decimal = Decimal(str(group_data['restriction_percentage']))
                # Maximum allowed CIF for this restriction group
                max_allowed_cif = (total_cif * restriction_pct_decimal) / Decimal('100')
                # Available CIF = max_allowed - debited
                available_cif = max_allowed_cif - group_data['debited_cif']
                # Cap at balance_cif - restriction cannot exceed available balance
                available_cif = min(available_cif, balance_cif)
                group_data['available_cif'] = max(available_cif, Decimal('0'))

        # Build row data
        # Handle blank/empty notification numbers
        notification_display = (license_obj.notification_number.code if license_obj.notification_number_id else '').strip()
        if not notification_display:
            notification_display = 'Unknown'

        # Check for document types
        has_tl = license_obj.license_documents.filter(type='TRANSFER LETTER').exists()
        has_copy = license_obj.license_documents.filter(type='LICENSE COPY').exists()

        # Get latest transfer
        latest_transfer_text = ''
        transfer_qs = license_obj.transfers.order_by("-transfer_date", "-id")
        if transfer_qs.exists():
            transfer = transfer_qs.first()
            latest_transfer_text = str(transfer)
        elif license_obj.current_owner:
            latest_transfer_text = f"Current Owner is {license_obj.current_owner.name}"
        else:
            latest_transfer_text = "Data Not Found"

        # Purchase Status — emitted so the frontend can colour-code each row.
        ps_code  = ''
        ps_label = ''
        if license_obj.purchase_status_id:
            ps = license_obj.purchase_status
            ps_code  = ps.code or ''
            ps_label = ps.label or ''

        row_data = {
            'id': license_obj.id,
            'license_number': license_obj.license_number,
            'license_date': license_obj.license_date.isoformat() if license_obj.license_date else None,
            'license_expiry_date': license_obj.license_expiry_date.isoformat(),
            'ledger_date': license_obj.ledger_date.isoformat() if license_obj.ledger_date else None,
            'exporter': str(license_obj.exporter) if license_obj.exporter else '',
            'port': str(license_obj.port) if license_obj.port else '',
            'notification_number': notification_display,
            'purchase_status_code': ps_code,
            'purchase_status_label': ps_label,
            'total_cif': float(total_cif),
            'debited_cif': float(debited_cif),
            'alloted_cif': float(alloted_cif),
            'balance_cif': float(balance_cif),  # Reuse already calculated balance
            'balance_report_notes': license_obj.balance_report_notes or '',
            'condition_sheet': license_obj.condition_sheet or '',
            'latest_transfer': latest_transfer_text,
            'has_tl': has_tl,
            'has_copy': has_copy,
            # Per-license plan source: 'manual' if the license has any manual
            # plan line, else 'norm'. The frontend uses this to show EITHER the
            # manual plan OR the norm plan for the whole license — never both.
            'plan_source': 'manual' if _plan_map else 'norm',
            'items': {}
        }

        # Calculate unit price for RUTILE - A3627 (Balance CIF / Total Balance QTY of RUTILE)
        rutile_unit_price = None
        rutile_total_balance_qty = Decimal('0')

        # Sum up all RUTILE available quantities
        for item_id, item_name in all_items:
            if item_name == 'RUTILE - A3627' and item_id in item_quantities:
                rutile_total_balance_qty += item_quantities[item_id]['available_quantity']

        # Calculate unit price if we have RUTILE balance qty >= 10, otherwise set to 0
        if rutile_total_balance_qty >= 10:
            rutile_unit_price = float(balance_cif / rutile_total_balance_qty)
        elif rutile_total_balance_qty > 0:
            rutile_unit_price = 0.0

        # ── Per-item Unit Price + Planned CIF (E1 / E5 only) ───────────────
        # Run the same waterfall the bulk Balance Excel runs so the per-item
        # rows in the pivot match the per-category planner exactly. For each
        # item we classify it into a category, compute the category's
        # effective rate (planned_cif / util_qty), then allocate this item's
        # share of the category's planned CIF proportionally to its util qty.
        primary_norm = ''
        if license_obj.export_license.exists():
            first_export = license_obj.export_license.first()
            if first_export and first_export.norm_class:
                primary_norm = first_export.norm_class.norm_class or ''

        # `item_plan_data[item_name]` → {'planned_cif': float, 'unit_price': float}
        item_plan_data: Dict[str, Dict[str, float]] = {}
        if primary_norm in ('E1', 'E5'):
            if primary_norm == 'E1':
                from apps.license.services.e1_plan import (
                    E1_CATS as _CATS, E1_EXCLUDED_CONDITIONS as _EXCL,
                    classify_e1_item as _classify, compute_e1_plan as _compute,
                )
            else:
                from apps.license.services.e5_plan import (
                    E5_CATS as _CATS, classify_e5_item as _classify,
                    compute_e5_plan as _compute,
                )
                _EXCL = None

            # Build a bal_agg-equivalent over each import_item (need per-item
            # condition_type to honour the Display/Util qty split for E1).
            # Items inactive in the master are still included so qty isn't lost.
            from collections import defaultdict as _dd
            import_items = (
                LicenseImportItemsModel.objects
                .filter(license=license_obj)
                .select_related('hs_code')
                .prefetch_related('items')
            )
            display_qty = {c: 0.0 for c in _CATS}
            util_qty    = {c: 0.0 for c in _CATS}
            # Track per ITEM-NAME so we can attribute the right share back.
            per_item_util: Dict[str, float] = {}
            per_item_category: Dict[str, str] = {}
            for ii in import_items:
                names = list(ii.items.values_list('name', flat=True))
                key = ', '.join(sorted(names)) if names else (ii.description or '-')
                hs = ii.hs_code.hs_code if ii.hs_code else ''
                cat = _classify(key, hs, ii.description)
                if not cat or cat not in display_qty:
                    continue
                avail = float(ii.available_quantity or 0)
                display_qty[cat] += avail
                cond = (ii.condition_type or '').strip()
                if _EXCL is not None:
                    excluded = _EXCL.get(cat, frozenset())
                    util_inc = 0.0 if cond in excluded else avail
                else:
                    util_inc = avail
                util_qty[cat] += util_inc
                # Attribute this row's util qty to every linked item-name so
                # the pivot's per-item planner share lines up with the table.
                if names:
                    for nm in names:
                        per_item_util[nm] = per_item_util.get(nm, 0.0) + util_inc
                        per_item_category[nm] = cat
                else:
                    # No master items linked — attribute to description.
                    nm = ii.description or '-'
                    per_item_util[nm] = per_item_util.get(nm, 0.0) + util_inc
                    per_item_category[nm] = cat

            if primary_norm == 'E1':
                planned, rates = _compute(display_qty, util_qty, float(balance_cif))
            else:
                planned, rates = _compute(display_qty, None, float(balance_cif), None)

            # Allocate per-item planned CIF as the item's PROPORTIONAL share
            # of its category's planned CIF — keeps the math equal to the
            # bulk Balance Excel (no rounding drift). Unit price is then
            # planned/qty rounded for display.
            for nm, uq in per_item_util.items():
                cat = per_item_category[nm]
                cat_uq = util_qty.get(cat, 0.0)
                cat_plan = planned.get(cat, 0.0)
                item_plan = (uq / cat_uq) * cat_plan if cat_uq else 0.0
                item_plan_data[nm] = {
                    'unit_price': round(item_plan / uq, 2) if uq else 0.0,
                    'planned_cif': round(item_plan, 2),
                }

        # ── Per-item sequential debit (E132) ──────────────────────────────
        # E132 uses a hard-stop debit sequence (services/e132_debit.py), not the
        # E1/E5 waterfall: each matched item debits qty×rate from a running
        # Balance CIF; on overflow it is flagged "Insufficient Balance" and the
        # run stops. Map the per-item result back by item-name.
        item_e132_data: Dict[str, Dict[str, Any]] = {}
        if primary_norm == 'E132':
            from apps.license.services.e132_debit import compute_e132_debit as _compute_e132_debit
            _e132_input = []
            for _iid, _inm in all_items:
                if _iid in item_quantities:
                    _d132 = item_quantities[_iid]
                    _e132_input.append({
                        'item_name': _inm,
                        'quantity': float(_d132['available_quantity'] or 0),
                        'hs_code': _d132['hs_code'] or '',
                        'description': _d132['description'] or '',
                    })
            _e132_res = _compute_e132_debit(_e132_input, float(balance_cif))
            for _r132 in _e132_res['rows']:
                item_e132_data[_r132['item_name']] = _r132

        # Add item columns
        # A manually-planned DFIA only shows the items it planned; the plan
        # map's keys are that set.
        planned_item_ids = set(item_plan_totals) if item_plan_totals is not None else None
        for item_id, item_name in all_items:
            # "As per planning": a manually-planned DFIA only shows the items it
            # planned; every other item is emitted as an empty cell for this row.
            if planned_item_ids is not None and item_id not in planned_item_ids:
                show_item = False
            else:
                show_item = item_id in item_quantities

            if show_item:
                item_data = item_quantities[item_id]
                # Per-item manual plan totals (empty for norm-driven licences).
                _item_plan = (item_plan_totals or {}).get(item_id) or {}

                # NEW model: restriction is determined by condition_type set
                # on the licence's import item (from the parsed condition
                # sheet), not by ItemNameModel.restriction_percentage.
                cond_type = item_data.get('condition_type') or ''
                restriction_value = None
                available_cif = Decimal('0')
                if cond_type.endswith('%'):
                    try:
                        restriction_value = float(cond_type.rstrip('%'))
                    except ValueError:
                        restriction_value = None
                    if cond_type in condition_pools:
                        available_cif = condition_pools[cond_type]

                # Use pre-calculated unit price for RUTILE; otherwise fall
                # back to the E1/E5 category rate computed above.
                planner = item_plan_data.get(item_name) or {}
                _e132 = item_e132_data.get(item_name) or {}
                if item_name == 'RUTILE - A3627':
                    unit_price = rutile_unit_price
                    planned_cif = planner.get('planned_cif', 0.0)
                elif _e132:
                    # E132 reuses the Unit Price / Planned CIF columns to show
                    # the sequential debit's Unit Rate / Debit Amount. Only a
                    # *Success* row is actually applied to the balance — an
                    # "Insufficient Balance" item is NOT debited, so it must
                    # contribute 0 to the summed Planned CIF (otherwise the
                    # report total can exceed the opening Balance CIF).
                    _applied = _e132.get('status') == 'Success'
                    unit_price = _e132.get('unit_rate') if _applied else None
                    planned_cif = _e132.get('debit_amount') if _applied else 0.0
                else:
                    unit_price = planner.get('unit_price')
                    planned_cif = planner.get('planned_cif', 0.0)

                row_data['items'][item_name] = {
                    'hs_code': item_data['hs_code'],
                    'description': item_data['description'],
                    'quantity': float(item_data['quantity']),
                    'allotted_quantity': float(item_data['allotted_quantity']),
                    'debited_quantity': float(item_data['debited_quantity']),
                    'available_quantity': float(item_data['available_quantity']),
                    'restriction': restriction_value,
                    'restriction_value': float(available_cif),
                    'unit_price': unit_price,
                    'planned_cif': planned_cif,
                    # User-authored plan (distinct from the norm-derived
                    # planned_cif), sourced per plan-line item_name.
                    'plan_quantity': float(_item_plan.get('q') or 0),
                    'plan_cif': float(_item_plan.get('cif') or 0),
                    'condition_type': cond_type,
                    # E132 sequential-debit fields (None for non-E132 norms).
                    'product_code': _e132.get('product_code'),
                    'unit_rate': _e132.get('unit_rate'),
                    'debit_amount': _e132.get('debit_amount'),
                    'previous_balance': _e132.get('previous_balance'),
                    'new_balance': _e132.get('new_balance'),
                    'debit_status': _e132.get('status'),
                }
            else:
                row_data['items'][item_name] = {
                    'hs_code': '',
                    'description': '',
                    'quantity': 0,
                    'allotted_quantity': 0,
                    'debited_quantity': 0,
                    'available_quantity': 0,
                    'restriction': None,
                    'restriction_value': 0,
                    'unit_price': None,
                    'planned_cif': 0,
                    'plan_quantity': 0,
                    'plan_cif': 0,
                    'condition_type': '',
                    'product_code': None,
                    'unit_rate': None,
                    'debit_amount': None,
                    'previous_balance': None,
                    'new_balance': None,
                    'debit_status': None,
                }

        return row_data

    def export_to_excel(self, report_data: Dict[str, Any]) -> HttpResponse:
        """
        Export report to Excel format with items as columns, split by norm then notification.
        Uses streaming to handle large datasets efficiently.

        Args:
            report_data: Report data dictionary

        Returns:
            StreamingHttpResponse with Excel file
        """
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.cell import WriteOnlyCell
        from django.http import StreamingHttpResponse
        import tempfile
        import os
        from apps.license.utils.condition_excel import annotate_cell as _annotate_condition_cell

        # Create a temporary file for the workbook
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_file.close()

        try:
            # Use write_only mode for streaming
            workbook = openpyxl.Workbook(write_only=True)

            licenses_by_norm_notification = report_data.get('licenses_by_norm_notification', {})

            # Create a sheet for each norm-notification combination
            for norm_class in sorted(licenses_by_norm_notification.keys()):
                notifications_dict = licenses_by_norm_notification[norm_class]
                for notification, licenses_list in sorted(notifications_dict.items()):
                    # Sanitize sheet name (Excel has 31 char limit and doesn't allow certain chars)
                    sheet_name = f"{norm_class}_{notification}"[:31].replace('/', '-').replace('\\', '-').replace('*',
                                                                                                                  '-').replace(
                        '[', '(').replace(']', ')')
                    worksheet = workbook.create_sheet(title=sheet_name)

                    # Title row
                    title = f"Item Pivot Report - {norm_class} - {notification}"
                    title_cell = WriteOnlyCell(worksheet, value=title)
                    title_cell.font = Font(bold=True, size=14)
                    title_cell.alignment = Alignment(horizontal='center')
                    worksheet.append([title_cell] + [None] * 25)  # Span across columns
                    worksheet.append([])  # Empty row

                    # Build headers
                    base_headers = [
                        'Sr no', 'DFIA No', 'DFIA Dt', 'Expiry Dt', 'Exporter',
                        'Total CIF', 'Debited CIF', 'Alloted CIF', 'Balance CIF', 'Notes', 'Condition Sheet',
                        'Ledger Date'
                    ]

                    # Add item columns (HSN Code, Product Description, Total QTY, Debited QTY, Available QTY, Restriction %, Restriction Value, Unit Price for RUTILE)
                    item_headers = []
                    for item in report_data['items']:
                        item_name = item['name']
                        has_restriction = item.get('has_restriction', False)
                        is_rutile = item_name == 'RUTILE - A3627'

                        headers = [
                            f"{item_name} HSN Code",
                            f"{item_name} Product Description",
                            f"{item_name} Total QTY",
                            f"{item_name} Allotted QTY",
                            f"{item_name} Debited QTY",
                            f"{item_name} Balance QTY",
                        ]

                        if has_restriction:
                            headers.extend([
                                f"{item_name} Restriction %",
                                f"{item_name} Restriction Value"
                            ])

                        if is_rutile:
                            headers.append(f"{item_name} Unit Price")

                        # Manual plan when present, else norm unit price / planned CIF.
                        headers.append(f"{item_name} Plan Qty / Unit Price")
                        headers.append(f"{item_name} Planned CIF")

                        item_headers.extend(headers)

                    all_headers = base_headers + item_headers

                    # Write headers with styling
                    header_row = []
                    for header in all_headers:
                        cell = WriteOnlyCell(worksheet, value=header)
                        cell.font = Font(bold=True, color='FFFFFF')
                        cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
                        cell.alignment = Alignment(horizontal='center', wrap_text=True)
                        header_row.append(cell)
                    worksheet.append(header_row)

                    # Write data rows for this norm-notification combination
                    for idx, license_data in enumerate(licenses_list, 1):
                        row_data = []

                        # Base columns
                        row_data.append(idx)
                        row_data.append(license_data['license_number'])
                        row_data.append(license_data['license_date'])
                        row_data.append(license_data['license_expiry_date'])
                        row_data.append(license_data['exporter'])
                        row_data.append(license_data['total_cif'])
                        row_data.append(license_data.get('debited_cif', 0))
                        row_data.append(license_data['alloted_cif'])
                        row_data.append(license_data['balance_cif'])
                        row_data.append(license_data.get('balance_report_notes', ''))
                        row_data.append(license_data.get('condition_sheet', ''))
                        row_data.append(license_data.get('ledger_date') or '')

                        # Item columns
                        for item in report_data['items']:
                            item_name = item['name']
                            has_restriction = item.get('has_restriction', False)
                            is_rutile = item_name == 'RUTILE - A3627'
                            item_data = license_data['items'].get(item_name, {
                                'hs_code': '',
                                'description': '',
                                'quantity': 0,
                                'allotted_quantity': 0,
                                'debited_quantity': 0,
                                'available_quantity': 0,
                                'restriction': None,
                                'restriction_value': 0,
                                'unit_price': None,
                                'condition_type': '',
                            })

                            # Tint HSN cell when a licence-condition is set
                            cond = item_data.get('condition_type') or ''
                            hsn_cell = WriteOnlyCell(worksheet, value=item_data.get('hs_code', ''))
                            _annotate_condition_cell(hsn_cell, cond)
                            row_data.append(hsn_cell)
                            row_data.append(item_data.get('description', ''))
                            row_data.append(item_data.get('quantity', 0))
                            row_data.append(item_data.get('allotted_quantity', 0))
                            row_data.append(item_data.get('debited_quantity', 0))
                            row_data.append(item_data.get('available_quantity', 0))

                            # Only write restriction columns if item has restrictions
                            if has_restriction:
                                restriction_val = item_data.get('restriction')
                                row_data.append(restriction_val if restriction_val else '')
                                restriction_value = item_data.get('restriction_value', 0)
                                row_data.append(restriction_value if restriction_value else '')

                            # Add unit price column for RUTILE
                            if is_rutile:
                                unit_price = item_data.get('unit_price')
                                row_data.append(unit_price if unit_price else '')

                            # Per license: manual plan if manually planned, else
                            # norm unit price / planned CIF.
                            if license_data.get('plan_source') == 'manual':
                                plan_q = item_data.get('plan_quantity') or 0
                                plan_c = item_data.get('plan_cif') or 0
                                row_data.append(plan_q if plan_q else '')
                                row_data.append(plan_c if plan_c else '')
                            else:
                                _up = item_data.get('unit_price')
                                _pc = item_data.get('planned_cif')
                                row_data.append(_up if _up else '')
                                row_data.append(_pc if _pc else '')

                        # Append row to worksheet
                        worksheet.append(row_data)

                    # Add totals row for this norm-notification
                    totals_row = []

                    # Total label
                    total_cell = WriteOnlyCell(worksheet, value='TOTAL')
                    total_cell.font = Font(bold=True)
                    totals_row.append(total_cell)

                    # Skip columns 2-5 (DFIA No, DFIA Dt, Expiry Dt, Exporter) + Notes + Condition Sheet
                    totals_row.extend([None, None, None, None, None, None])

                    # Calculate totals for CIF columns
                    total_cif = sum(lic['total_cif'] for lic in licenses_list)
                    balance_cif = sum(lic['balance_cif'] for lic in licenses_list)

                    total_cif_cell = WriteOnlyCell(worksheet, value=total_cif)
                    total_cif_cell.font = Font(bold=True)
                    totals_row.append(total_cif_cell)

                    balance_cif_cell = WriteOnlyCell(worksheet, value=balance_cif)
                    balance_cif_cell.font = Font(bold=True)
                    totals_row.append(balance_cif_cell)

                    # Calculate totals for each item
                    for item in report_data['items']:
                        item_name = item['name']
                        has_restriction = item.get('has_restriction', False)
                        is_rutile = item_name == 'RUTILE - A3627'

                        total_qty = sum(
                            lic['items'].get(item_name, {}).get('quantity', 0)
                            for lic in licenses_list
                        )
                        total_allotted = sum(
                            lic['items'].get(item_name, {}).get('allotted_quantity', 0)
                            for lic in licenses_list
                        )
                        total_debited = sum(
                            lic['items'].get(item_name, {}).get('debited_quantity', 0)
                            for lic in licenses_list
                        )
                        total_avail = sum(
                            lic['items'].get(item_name, {}).get('available_quantity', 0)
                            for lic in licenses_list
                        )
                        total_restriction_val = sum(
                            lic['items'].get(item_name, {}).get('restriction_value', 0)
                            for lic in licenses_list
                        )

                        # Skip HSN and Description columns in totals
                        totals_row.extend([None, None])

                        # Add quantity totals with bold font
                        qty_cell = WriteOnlyCell(worksheet, value=total_qty)
                        qty_cell.font = Font(bold=True)
                        totals_row.append(qty_cell)

                        allotted_cell = WriteOnlyCell(worksheet, value=total_allotted)
                        allotted_cell.font = Font(bold=True)
                        totals_row.append(allotted_cell)

                        debited_cell = WriteOnlyCell(worksheet, value=total_debited)
                        debited_cell.font = Font(bold=True)
                        totals_row.append(debited_cell)

                        avail_cell = WriteOnlyCell(worksheet, value=total_avail)
                        avail_cell.font = Font(bold=True)
                        totals_row.append(avail_cell)

                        # Only add restriction columns if item has restrictions
                        if has_restriction:
                            totals_row.append(None)  # Skip Restriction % column

                            restriction_cell = WriteOnlyCell(worksheet, value=total_restriction_val)
                            restriction_cell.font = Font(bold=True)
                            totals_row.append(restriction_cell)

                        # Add unit price column for RUTILE (leave empty in totals)
                        if is_rutile:
                            totals_row.append(None)

                    worksheet.append(totals_row)

            # Save workbook to temp file
            workbook.save(temp_file.name)
            workbook.close()

            # Create streaming response
            def file_iterator(file_path, chunk_size=8192):
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                # Clean up temp file after streaming
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

            response = StreamingHttpResponse(
                file_iterator(temp_file.name),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="item_pivot_report.xlsx"'
            return response

        except Exception as e:
            # Clean up temp file in case of error
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass
            raise e

    def export_to_excel_streaming(self, days=30, sion_norm=None, company_ids=None,
                                  exclude_company_ids=None, min_balance=200, license_status='active',
                                  expiry_date_from=None, expiry_date_to=None, purchase_status=None):
        """
        Export report to Excel - uses existing generate_report for data, then formats as Excel.
        This ensures consistency with JSON output.

        Returns:
            StreamingHttpResponse with Excel file
        """
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.cell import WriteOnlyCell
        from django.http import StreamingHttpResponse
        import tempfile
        import os
        from apps.license.utils.condition_excel import annotate_cell as _annotate_condition_cell

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_file.close()

        try:
            # Use the working generate_report method
            report_data = self.generate_report(days, sion_norm, company_ids, exclude_company_ids, min_balance, license_status, expiry_date_from, expiry_date_to, purchase_status)

            workbook = openpyxl.Workbook(write_only=True)
            licenses_by_norm_notif = report_data.get('licenses_by_norm_notification', {})

            for norm_class in sorted(licenses_by_norm_notif.keys()):
                notifications_dict = licenses_by_norm_notif[norm_class]
                for notification, licenses_list in sorted(notifications_dict.items()):
                    # Filter items to only those with data in THIS norm-notification
                    items_with_data = []
                    for item in report_data['items']:
                        item_name = item['name']
                        has_data = any(
                            lic['items'].get(item_name, {}).get('quantity', 0) > 0
                            for lic in licenses_list
                        )
                        if has_data:
                            items_with_data.append(item)

                    # Create sheet
                    sheet_name = f"{norm_class}_{notification}"[:31].replace('/', '-').replace('\\', '-').replace('*', '-')
                    worksheet = workbook.create_sheet(title=sheet_name)

                    # Title row
                    title_cell = WriteOnlyCell(worksheet, value=f"Item Pivot Report - {norm_class} - {notification}")
                    title_cell.font = Font(bold=True, size=14)
                    title_cell.alignment = Alignment(horizontal='center')
                    worksheet.append([title_cell] + [None] * 25)
                    worksheet.append([])

                    # Headers
                    base_headers = ['Sr no', 'DFIA No', 'DFIA Dt', 'Expiry Dt', 'Exporter', 'Total CIF', 'Debited CIF', 'Alloted CIF', 'Balance CIF', 'Notes', 'Condition Sheet']
                    item_headers = []
                    for item in items_with_data:
                        item_name = item['name']
                        has_restriction = item.get('has_restriction', False)
                        is_rutile = item_name == 'RUTILE - A3627'
                        headers = [
                            f"{item_name} HSN Code",
                            f"{item_name} Product Description",
                            f"{item_name} Total QTY",
                            f"{item_name} Allotted QTY",
                            f"{item_name} Debited QTY",
                            f"{item_name} Balance QTY"
                        ]
                        if has_restriction:
                            headers.extend([
                                f"{item_name} Restriction %",
                                f"{item_name} Restriction Value"
                            ])
                        # Two new per-item columns sourced from the
                        # e1_plan / e5_plan waterfall so the Excel matches
                        # the bulk Balance report cell-for-cell.
                        headers.extend([
                            f"{item_name} Unit Price",
                            f"{item_name} Planned CIF",
                        ])
                        item_headers.extend(headers)

                    all_headers = base_headers + item_headers
                    header_row = []
                    for header in all_headers:
                        cell = WriteOnlyCell(worksheet, value=header)
                        cell.font = Font(bold=True, color='FFFFFF')
                        cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
                        cell.alignment = Alignment(horizontal='center', wrap_text=True)
                        header_row.append(cell)
                    worksheet.append(header_row)

                    # Data rows
                    for idx, lic in enumerate(licenses_list, 1):
                        row_data = [
                            idx,
                            lic['license_number'],
                            lic['license_date'],
                            lic['license_expiry_date'],
                            lic['exporter'],
                            lic['total_cif'],
                            lic.get('debited_cif', 0),
                            lic['alloted_cif'],
                            lic['balance_cif'],
                            lic.get('balance_report_notes', ''),
                            lic.get('condition_sheet', '')
                        ]

                        for item in items_with_data:
                            item_name = item['name']
                            has_restriction = item.get('has_restriction', False)
                            is_rutile = item_name == 'RUTILE - A3627'
                            item_data = lic['items'].get(item_name, {})
                            cond = item_data.get('condition_type') or ''
                            # Tint the HSN-code cell for this (licence, item)
                            # pair when a condition is set.
                            hsn_cell = WriteOnlyCell(worksheet, value=item_data.get('hs_code', ''))
                            _annotate_condition_cell(hsn_cell, cond)
                            row_data.append(hsn_cell)
                            row_data.extend([
                                item_data.get('description', ''),
                                item_data.get('quantity', 0),
                                item_data.get('allotted_quantity', 0),
                                item_data.get('debited_quantity', 0),
                                item_data.get('available_quantity', 0)
                            ])
                            if has_restriction:
                                row_data.extend([
                                    item_data.get('restriction'),
                                    item_data.get('restriction_value', 0)
                                ])
                            # Unit Price + Planned CIF — from the per-item
                            # planner attached to each row's item dict.
                            row_data.append(item_data.get('unit_price') or 0)
                            row_data.append(item_data.get('planned_cif') or 0)

                        worksheet.append(row_data)

                    # Totals row
                    totals_row = [WriteOnlyCell(worksheet, value='TOTAL')]
                    totals_row[0].font = Font(bold=True)
                    totals_row.extend([None, None, None, None, None, None])

                    total_cif_cell = WriteOnlyCell(worksheet, value=sum(l['total_cif'] for l in licenses_list))
                    total_cif_cell.font = Font(bold=True)
                    totals_row.append(total_cif_cell)

                    debited_cif_cell = WriteOnlyCell(worksheet, value=sum(l.get('debited_cif', 0) for l in licenses_list))
                    debited_cif_cell.font = Font(bold=True)
                    totals_row.append(debited_cif_cell)

                    alloted_cif_cell = WriteOnlyCell(worksheet, value=sum(l['alloted_cif'] for l in licenses_list))
                    alloted_cif_cell.font = Font(bold=True)
                    totals_row.append(alloted_cif_cell)

                    balance_cif_cell = WriteOnlyCell(worksheet, value=sum(l['balance_cif'] for l in licenses_list))
                    balance_cif_cell.font = Font(bold=True)
                    totals_row.append(balance_cif_cell)

                    for item in items_with_data:
                        item_name = item['name']
                        has_restriction = item.get('has_restriction', False)
                        is_rutile = item_name == 'RUTILE - A3627'
                        totals_row.extend([None, None])  # HSN, Description
                        for qty_type in ['quantity', 'allotted_quantity', 'debited_quantity', 'available_quantity']:
                            total = sum(l['items'].get(item_name, {}).get(qty_type, 0) for l in licenses_list)
                            cell = WriteOnlyCell(worksheet, value=total)
                            cell.font = Font(bold=True)
                            totals_row.append(cell)
                        if has_restriction:
                            totals_row.append(None)  # Restriction %
                            total_restriction = sum(l['items'].get(item_name, {}).get('restriction_value', 0) for l in licenses_list)
                            cell = WriteOnlyCell(worksheet, value=total_restriction)
                            cell.font = Font(bold=True)
                            totals_row.append(cell)
                        # Unit Price column total stays blank (it's a rate);
                        # Planned CIF totals across the column.
                        totals_row.append(None)
                        total_planned = sum((l['items'].get(item_name, {}).get('planned_cif') or 0) for l in licenses_list)
                        cell = WriteOnlyCell(worksheet, value=total_planned)
                        cell.font = Font(bold=True)
                        totals_row.append(cell)

                    worksheet.append(totals_row)

            # Save workbook
            workbook.save(temp_file.name)
            workbook.close()

            # Stream file
            def file_iterator(file_path, chunk_size=8192):
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

            response = StreamingHttpResponse(
                file_iterator(temp_file.name),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="item_pivot_report.xlsx"'
            return response

        except Exception as e:
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass
            raise e

class ItemPivotViewSet(viewsets.ViewSet):
    """
    ViewSet for Item Pivot Report.

    Permissions: AllowAny - accessible to all users
    """
    permission_classes = [ReportPermission]

    def list(self, request):
        """
        Get item pivot report.

        Query Parameters:
            days: Number of days to look back (default: 30)
        """
        view = ItemPivotReportView()
        return view.get(request)

    @action(detail=False, methods=['get'], url_path='available-norms')
    def available_norms(self, request):
        """
        Get list of all active norm classes with their descriptions.
        Returns only norms that are marked as active (is_active=True) in SionNormClassModel.
        """
        try:
            # Get only active SION norm classes from the database
            from apps.core.models import SionNormClassModel
            active_norms_data = SionNormClassModel.objects.filter(
                is_active=True
            ).values('norm_class', 'description').order_by('norm_class')

            # Build result with norm_class and description
            result = [
                {
                    'norm_class': norm['norm_class'],
                    'description': norm['description'] or ''
                }
                for norm in active_norms_data
            ]

            return Response(result)
        except Exception as e:
            logger.exception("Error generating item pivot report")
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['post', 'get'], url_path='generate-async')
    def generate_async(self, request):
        """
        Generate Excel report asynchronously using Celery.

        Query Parameters / POST Body:
            days: Number of days to look back (default: 30)
            sion_norm: Filter by SION norm (REQUIRED)
            company_ids: Comma-separated company IDs (optional)
            exclude_company_ids: Comma-separated company IDs to exclude (optional)
            min_balance: Minimum balance CIF (default: 200)
            license_status: Filter by status (default: 'active')

        Returns:
            task_id: ID to check status and download file
        """
        from apps.license.tasks import generate_item_pivot_excel

        # Get parameters from request (support both GET and POST)
        params = request.data if request.method == 'POST' else request.GET
        days = int(params.get('days', 30))
        sion_norm = params.get('sion_norm')  # Optional - if not provided, exports ALL norms
        company_ids = params.get('company_ids')
        exclude_company_ids = params.get('exclude_company_ids')
        min_balance = int(params.get('min_balance', 200))
        license_status = params.get('license_status', 'active')

        # Start the Celery task
        task = generate_item_pivot_excel.delay(
            days=days,
            sion_norm=sion_norm,
            company_ids=company_ids,
            exclude_company_ids=exclude_company_ids,
            min_balance=min_balance,
            license_status=license_status
        )

        return Response({
            'task_id': task.id,
            'status': 'PENDING',
            'message': 'Report generation started. Use the task_id to check status.'
        }, status=202)

    @action(detail=False, methods=['get'], url_path='task-status/(?P<task_id>[^/.]+)')
    def task_status(self, request, task_id=None):
        """
        Check the status of an async Excel generation task.

        Returns:
            state: Task state (PENDING, PROGRESS, SUCCESS, FAILURE)
            current: Current progress (0-100)
            total: Total progress (100)
            status: Status message
            result: Result data (if completed)
        """
        from celery.result import AsyncResult

        task = AsyncResult(task_id)

        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'current': 0,
                'total': 100,
                'status': 'Pending...'
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 100),
                'status': task.info.get('status', '')
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'current': 100,
                'total': 100,
                'status': 'Completed!',
                'result': task.info
            }
        else:
            # Something went wrong
            response = {
                'state': task.state,
                'current': 100,
                'total': 100,
                'status': str(task.info) if task.info else 'Unknown error'
            }

        return Response(response)

    @action(detail=False, methods=['post'], url_path='update-balance')
    def update_balance(self, request):
        """
        Trigger high-priority task to update balance_cif, is_active, is_expired, and restrictions.

        This task:
        1. Updates balance_cif for all licenses using LicenseBalanceCalculator
        2. Updates is_expired based on license_expiry_date
        3. Updates is_null based on balance < $500
        4. Updates is_active based on expiry (mark inactive if expired)
        5. Checks and updates restriction flags on import items

        Returns:
            task_id: ID to check status using task-status endpoint
        """
        from apps.license.tasks import update_all_license_balances

        # Get license_status parameter from request body
        license_status = request.data.get('license_status', 'all')

        # Start the Celery task with high priority
        task = update_all_license_balances.apply_async(
            args=[license_status],
            priority=9  # High priority (0-9, 9 is highest)
        )

        return Response({
            'task_id': task.id,
            'status': 'PENDING',
            'license_status': license_status,
            'message': f'Balance update started for {license_status} licenses. Use the task_id to check status.'
        }, status=202)
