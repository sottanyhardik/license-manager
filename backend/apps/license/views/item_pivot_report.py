# license/views/item_pivot_report.py
"""
Item-wise Pivot Report — licenses as rows, items as columns.

Ported from legacy/backend/apps/license/views/item_pivot_report.py (1572 lines).

New backend field mapping vs legacy model methods:
  license_obj.balance_cif          → license_obj.balance.balance_cif
  license_obj.balance_report_notes → license_obj.notes.balance_report_notes
  license_obj.condition_sheet      → license_obj.notes.condition_sheet
  license_obj.current_owner        → license_obj.ownership.current_owner
  license_obj.ledger_date          → license_obj.balance.ledger_date

OQ-6 compliance: async Celery generation is preserved.
Routes registered in urls.py:
  GET  /api/v1/item-pivot/                           → list (JSON sync)
  GET  /api/v1/item-pivot/available-norms/           → available_norms
  POST /api/v1/item-pivot/generate-async/            → generate_async
  GET  /api/v1/item-pivot/task-status/{task_id}/    → task_status
  POST /api/v1/item-pivot/update-balance/            → update_balance
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Any

from django.db.models import Sum, Prefetch
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReportPermission
from apps.core.models import ItemNameModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
    LicenseExportItemModel,
)

logger = logging.getLogger(__name__)

DEC_0 = Decimal("0")
DEC_000 = Decimal("0.000")


# ---------------------------------------------------------------------------
# Internal helpers — replace legacy model-method shortcuts
# ---------------------------------------------------------------------------

def _get_balance_cif(license_obj) -> Decimal:
    """Access balance_cif via OneToOne LicenseBalance sub-table."""
    try:
        return Decimal(str(license_obj.balance.balance_cif or 0))
    except Exception:
        return DEC_0


def _get_ledger_date(license_obj):
    """Access ledger_date via OneToOne LicenseBalance sub-table."""
    try:
        return license_obj.balance.ledger_date
    except Exception:
        return None


def _get_balance_report_notes(license_obj) -> str:
    try:
        return license_obj.notes.balance_report_notes or ""
    except Exception:
        return ""


def _get_condition_sheet(license_obj) -> str:
    try:
        return license_obj.notes.condition_sheet or ""
    except Exception:
        return ""


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _xlsx_safe_row(row):
    """Strip XML-illegal control characters from string cells before writing."""
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    cleaned = []
    for cell in row:
        val = getattr(cell, "value", cell)
        if isinstance(val, str):
            safe = ILLEGAL_CHARACTERS_RE.sub("", val)
            if val is not cell:
                cell.value = safe
                cleaned.append(cell)
            else:
                cleaned.append(safe)
        else:
            cleaned.append(cell)
    return cleaned


# ---------------------------------------------------------------------------
# Core report-generation logic (shared by sync list + async task)
# ---------------------------------------------------------------------------

class _ItemPivotReportEngine:
    """
    Stateless report engine extracted from the legacy ItemPivotReportView.
    Used by both the synchronous list action and the async Celery task.
    """

    def generate_report(
        self,
        days: int = 30,
        sion_norm: str = None,
        company_ids: str = None,
        exclude_company_ids: str = None,
        min_balance: int = 200,
        license_status: str = 'active',
        expiry_date_from: str = None,
        expiry_date_to: str = None,
        purchase_status: str = None,
    ) -> Dict[str, Any]:
        from datetime import date, timedelta
        from apps.core.constants import GE, MI, CO

        today = date.today()

        # Purchase status codes.
        if purchase_status:
            ps_codes = [c.strip() for c in purchase_status.split(',') if c.strip()]
        else:
            ps_codes = [GE, MI, CO]

        licenses = LicenseDetailsModel.objects.filter(
            purchase_status__code__in=ps_codes
        )

        # License status filter.
        if license_status == 'active':
            licenses = licenses.filter(
                flags__is_active=True,
                license_expiry_date__gt=today - timedelta(days=30),
            )
        elif license_status == 'expired':
            licenses = licenses.filter(license_expiry_date__lt=today)
        elif license_status == 'expiring_soon':
            licenses = licenses.filter(
                flags__is_active=True,
                license_expiry_date__gte=today,
                license_expiry_date__lte=today + timedelta(days=30),
            )

        if expiry_date_from:
            from datetime import datetime as _dt
            licenses = licenses.filter(
                license_expiry_date__gte=_dt.strptime(expiry_date_from, '%Y-%m-%d').date()
            )
        if expiry_date_to:
            from datetime import datetime as _dt
            licenses = licenses.filter(
                license_expiry_date__lte=_dt.strptime(expiry_date_to, '%Y-%m-%d').date()
            )

        if sion_norm:
            licenses = licenses.filter(export_license__norm_class__norm_class=sion_norm).distinct()

        if company_ids:
            company_id_list = [int(cid.strip()) for cid in company_ids.split(',') if cid.strip()]
            licenses = licenses.filter(exporter_id__in=company_id_list)

        if exclude_company_ids:
            exclude_id_list = [int(cid.strip()) for cid in exclude_company_ids.split(',') if cid.strip()]
            licenses = licenses.exclude(exporter_id__in=exclude_id_list)

        # Pre-filter by stored balance_cif.
        licenses = licenses.filter(balance__balance_cif__gte=min_balance)

        import_items_qs = LicenseImportItemsModel.objects.select_related('hs_code')
        export_items_qs = LicenseExportItemModel.objects.select_related('norm_class')
        item_names_qs = ItemNameModel.objects.select_related('sion_norm_class')

        if sion_norm:
            item_names_qs = item_names_qs.filter(sion_norm_class__norm_class=sion_norm)
            export_items_qs = export_items_qs.filter(norm_class__norm_class=sion_norm)

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
                            'debited_quantity', 'available_quantity', 'debited_value', 'cif_fc',
                            'description', 'condition_type', 'serial_number')),
            Prefetch('export_license',
                     queryset=export_items_qs.only('id', 'license_id', 'norm_class_id', 'cif_fc')),
            'license_documents',
            'transfers',
        ).order_by('license_expiry_date', 'license_date')

        valid_licenses = list(licenses)

        # Collect all unique item names across all licenses.
        all_items = {}
        for license_obj in valid_licenses:
            for import_item in license_obj.import_license.all():
                for item in import_item.items.all():
                    if item and item.name and item.is_active:
                        if sion_norm:
                            if item.sion_norm_class and item.sion_norm_class.norm_class == sion_norm:
                                all_items[item.id] = item
                        else:
                            all_items[item.id] = item

        # "As per planning" per-DFIA item map.
        from apps.license.models import LicenseItemPlan

        first_item_of_import = {}
        for _lo in valid_licenses:
            for _ii in _lo.import_license.all():
                for _it in _ii.items.all():
                    first_item_of_import[_ii.id] = _it.id
                    break

        plan_totals_by_license = defaultdict(
            lambda: defaultdict(lambda: {'q': Decimal('0.000'), 'cif': Decimal('0.00')})
        )
        planned_item_ids_all = set()
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
            planned_item_ids_all.add(_iname)

        # Add manually-planned but inactive items back into the column set.
        _missing_planned = [iid for iid in planned_item_ids_all if iid not in all_items]
        if _missing_planned:
            for _it in ItemNameModel.objects.filter(id__in=_missing_planned).select_related('sion_norm_class'):
                if not _it.name:
                    continue
                if sion_norm and not (_it.sion_norm_class and _it.sion_norm_class.norm_class == sion_norm):
                    continue
                all_items[_it.id] = _it

        # Sort items by display_order then name.
        sorted_items = sorted(
            [(item.id, item.name) for item in all_items.values()],
            key=lambda x: (all_items[x[0]].display_order, x[1] or ''),
        )

        # Batch document-type lookups.
        from apps.license.models import LicenseDocumentModel
        doc_types_by_license = defaultdict(set)
        for _lid, _dt in (LicenseDocumentModel.objects
                          .filter(license_id__in=[_lo.id for _lo in valid_licenses])
                          .values_list('license_id', 'type')):
            doc_types_by_license[_lid].add(_dt)

        # Batch condition-pool computation.
        from apps.license.services.condition_pool import compute_condition_pools_bulk
        cond_pools_by_license = compute_condition_pools_bulk([_lo.id for _lo in valid_licenses])

        # Build grouped data.
        licenses_by_norm_notification = defaultdict(lambda: defaultdict(list))

        from apps.core.constants import CO
        for license_obj in valid_licenses:
            license_row = self._build_license_row(
                license_obj, sorted_items,
                item_plan_totals=plan_totals_by_license.get(license_obj.id),
                document_types=doc_types_by_license.get(license_obj.id, frozenset()),
                condition_pools=cond_pools_by_license.get(license_obj.id, {}),
            )

            if license_row:
                notification = (
                    license_obj.notification_number.code
                    if license_obj.notification_number_id else ''
                ).strip()
                if not notification:
                    notification = 'Unknown'

                norm_class = 'Unknown'
                if license_obj.export_license.exists():
                    first_export = license_obj.export_license.first()
                    if first_export and first_export.norm_class:
                        norm_class = first_export.norm_class.norm_class

                conversion_norms = ['E1', 'E5', 'E126', 'E132']
                is_conversion = license_obj.purchase_status and license_obj.purchase_status.code == CO

                exporter_name = (license_obj.exporter.name or '') if license_obj.exporter else ''
                exporter_name_upper = exporter_name.upper()

                exporter_category = None
                if 'PARLE' in exporter_name_upper:
                    exporter_category = 'Parle'
                elif 'HALDIRAM SNACKS' in exporter_name_upper:
                    exporter_category = 'Haldiram Snacks'
                elif 'HALDIRAM FOODS' in exporter_name_upper:
                    exporter_category = 'Haldiram Foods'
                elif 'HARIOMKAR FOOD' in exporter_name_upper:
                    exporter_category = 'Hariomkar Food'

                if norm_class in conversion_norms and is_conversion:
                    if norm_class in ['E5', 'E132']:
                        if exporter_category:
                            notification_key = f"{notification} - Conversion - {exporter_category}"
                        else:
                            notification_key = f"{notification} - Conversion"
                    else:
                        notification_key = f"{notification} - Conversion"
                elif norm_class in ['E5', 'E132']:
                    if exporter_category:
                        notification_key = f"{notification} - {exporter_category}"
                    else:
                        notification_key = f"{notification} - Others"
                else:
                    notification_key = notification

                ps_label = (
                    license_row.get('purchase_status_label')
                    or license_row.get('purchase_status_code') or 'Unknown'
                )
                notification_key = f"{ps_label} — {notification_key}"

                licenses_by_norm_notification[norm_class][notification_key].append(license_row)

        # Mark items that have any restriction value.
        items_with_restrictions = set()
        for norm_dict in licenses_by_norm_notification.values():
            for licenses_list in norm_dict.values():
                for license_row in licenses_list:
                    for item_id, item_name in sorted_items:
                        item_data = license_row.get('items', {}).get(item_name, {})
                        if item_data.get('restriction') is not None:
                            items_with_restrictions.add(item_id)

        result_dict = {
            norm: dict(notif_dict)
            for norm, notif_dict in licenses_by_norm_notification.items()
        }

        # Fetch SION norm notes/conditions.
        from apps.core.models import SionNormClassModel
        norm_classes_list = list(result_dict.keys())
        sion_norms = SionNormClassModel.objects.filter(
            norm_class__in=norm_classes_list
        ).prefetch_related('notes', 'conditions')
        sion_norms_dict = {sn.norm_class: sn for sn in sion_norms}

        norm_notes_conditions = {}
        for norm_class_key in norm_classes_list:
            if norm_class_key in sion_norms_dict:
                sn = sion_norms_dict[norm_class_key]
                norm_notes_conditions[norm_class_key] = {
                    'notes': [
                        {'note_text': note.note_text, 'display_order': note.display_order}
                        for note in sn.notes.all()
                    ],
                    'conditions': [
                        {'condition_text': cond.condition_text, 'display_order': cond.display_order}
                        for cond in sn.conditions.all()
                    ],
                }
            else:
                norm_notes_conditions[norm_class_key] = {'notes': [], 'conditions': []}

        return {
            'items': [
                {
                    'id': item_id,
                    'name': item_name,
                    'has_restriction': item_id in items_with_restrictions,
                }
                for item_id, item_name in sorted_items
            ],
            'licenses_by_norm_notification': result_dict,
            'norm_notes_conditions': norm_notes_conditions,
            'report_date': today.isoformat(),
        }

    def _build_license_row(
        self,
        license_obj: LicenseDetailsModel,
        all_items: List[tuple],
        item_plan_totals=None,
        document_types=None,
        condition_pools=None,
    ) -> Dict[str, Any]:
        """Build a single license row with item columns."""
        # Total CIF from export side.
        total_cif = Decimal('0')
        for item in license_obj.export_license.all():
            cif_value = Decimal(str(item.cif_fc)) if item.cif_fc is not None else Decimal('0')
            total_cif += cif_value

        # Allotted CIF (allotted but no BOE yet).
        from apps.allotment.models import AllotmentItems
        alloted_cif = Decimal('0')
        allotment_items = AllotmentItems.objects.filter(
            item__license=license_obj,
            allotment__is_allotted=True,
            allotment__bill_of_entry__isnull=True,
        ).select_related('allotment')
        for allot_item in allotment_items:
            alloted_cif += Decimal(str(allot_item.cif_fc)) if allot_item.cif_fc is not None else DEC_0

        # Debited CIF from import items.
        debited_cif = Decimal('0')
        for import_item in license_obj.import_license.all():
            debited_cif += Decimal(str(import_item.debited_value)) if import_item.debited_value is not None else DEC_0

        # Per-item quantity aggregation.
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
            'plan_quantity': Decimal('0.000'),
            'plan_cif': Decimal('0.00'),
        })

        from apps.license.services.plan_reporting import plan_map_for_license
        _plan_map = plan_map_for_license(license_obj.id)

        if condition_pools is None:
            from apps.license.services.condition_pool import compute_condition_pools
            condition_pools = compute_condition_pools(license_obj)

        restriction_groups = defaultdict(lambda: {
            'total_cif': Decimal('0.00'),
            'debited_cif': Decimal('0.00'),
            'available_cif': Decimal('0.00'),
            'restriction_percentage': None,
            'sion_norm_class': None,
            'item_ids': [],
        })

        for import_item in license_obj.import_license.all():
            for item in import_item.items.all():
                item_quantities[item.id]['quantity'] += (
                    Decimal(str(import_item.quantity)) if import_item.quantity is not None else DEC_000
                )
                item_quantities[item.id]['allotted_quantity'] += (
                    Decimal(str(import_item.allotted_quantity)) if import_item.allotted_quantity is not None else DEC_000
                )
                item_quantities[item.id]['debited_quantity'] += (
                    Decimal(str(import_item.debited_quantity)) if import_item.debited_quantity is not None else DEC_000
                )
                item_quantities[item.id]['available_quantity'] += (
                    Decimal(str(import_item.available_quantity)) if import_item.available_quantity is not None else DEC_000
                )
                item_quantities[item.id]['debited_value'] += (
                    Decimal(str(import_item.debited_value)) if import_item.debited_value is not None else DEC_0
                )
                item_quantities[item.id]['cif_value'] += (
                    Decimal(str(import_item.cif_fc)) if import_item.cif_fc is not None else DEC_0
                )

                if import_item.hs_code and not item_quantities[item.id]['hs_code']:
                    item_quantities[item.id]['hs_code'] = import_item.hs_code.hs_code

                if import_item.description and not item_quantities[item.id]['description']:
                    item_quantities[item.id]['description'] = import_item.description

                if import_item.condition_type and not item_quantities[item.id]['condition_type']:
                    item_quantities[item.id]['condition_type'] = import_item.condition_type

                if item and hasattr(item, 'sion_norm_class') and item.sion_norm_class:
                    sion_norm_val = item.sion_norm_class.norm_class
                    restriction_pct = item.restriction_percentage
                    item_quantities[item.id]['sion_norm_class'] = sion_norm_val
                    item_quantities[item.id]['restriction_percentage'] = restriction_pct
                    restriction_key = f"{sion_norm_val}_{restriction_pct}"
                    restriction_groups[restriction_key]['sion_norm_class'] = sion_norm_val
                    restriction_groups[restriction_key]['restriction_percentage'] = restriction_pct
                    restriction_groups[restriction_key]['total_cif'] += (
                        Decimal(str(import_item.cif_fc)) if import_item.cif_fc is not None else DEC_0
                    )
                    restriction_groups[restriction_key]['debited_cif'] += (
                        Decimal(str(import_item.debited_value)) if import_item.debited_value is not None else DEC_0
                    )
                    if item.id not in restriction_groups[restriction_key]['item_ids']:
                        restriction_groups[restriction_key]['item_ids'].append(item.id)

        balance_cif = _get_balance_cif(license_obj)
        for group_name, group_data in restriction_groups.items():
            if group_data['restriction_percentage'] and total_cif > 0:
                restriction_pct_decimal = Decimal(str(group_data['restriction_percentage']))
                max_allowed_cif = (total_cif * restriction_pct_decimal) / Decimal('100')
                available_cif = max_allowed_cif - group_data['debited_cif']
                available_cif = min(available_cif, balance_cif)
                group_data['available_cif'] = max(available_cif, Decimal('0'))

        # Build the row header data.
        notification_display = (
            license_obj.notification_number.code if license_obj.notification_number_id else ''
        ).strip()
        if not notification_display:
            notification_display = 'Unknown'

        if document_types is None:
            document_types = {d.type for d in license_obj.license_documents.all()}
        has_tl = 'TRANSFER LETTER' in document_types
        has_copy = 'LICENSE COPY' in document_types

        latest_transfer_text = ''
        transfer_qs = license_obj.transfers.order_by('-transfer_date', '-id')
        if transfer_qs.exists():
            transfer = transfer_qs.first()
            latest_transfer_text = str(transfer)
        else:
            try:
                owner = license_obj.ownership.current_owner
                if owner:
                    latest_transfer_text = f"Current Owner is {owner.name}"
                else:
                    latest_transfer_text = "Data Not Found"
            except Exception:
                latest_transfer_text = "Data Not Found"

        ps_code = ''
        ps_label = ''
        if license_obj.purchase_status_id:
            ps = license_obj.purchase_status
            ps_code = ps.code or ''
            ps_label = ps.label or ''

        ledger_date = _get_ledger_date(license_obj)

        row_data = {
            'id': license_obj.id,
            'license_number': license_obj.license_number,
            'license_date': license_obj.license_date.isoformat() if license_obj.license_date else None,
            'license_expiry_date': license_obj.license_expiry_date.isoformat() if license_obj.license_expiry_date else None,
            'ledger_date': ledger_date.isoformat() if ledger_date else None,
            'exporter': str(license_obj.exporter) if license_obj.exporter else '',
            'port': str(license_obj.port) if license_obj.port else '',
            'notification_number': notification_display,
            'purchase_status_code': ps_code,
            'purchase_status_label': ps_label,
            'total_cif': float(total_cif),
            'debited_cif': float(debited_cif),
            'alloted_cif': float(alloted_cif),
            'balance_cif': float(balance_cif),
            'balance_report_notes': _get_balance_report_notes(license_obj),
            'condition_sheet': _get_condition_sheet(license_obj),
            'latest_transfer': latest_transfer_text,
            'has_tl': has_tl,
            'has_copy': has_copy,
            'plan_source': 'manual' if _plan_map else 'norm',
            'items': {},
        }

        # RUTILE unit price.
        rutile_unit_price = None
        rutile_total_balance_qty = Decimal('0')
        for item_id, item_name in all_items:
            if item_name == 'RUTILE - A3627' and item_id in item_quantities:
                rutile_total_balance_qty += item_quantities[item_id]['available_quantity']
        if rutile_total_balance_qty >= 10:
            rutile_unit_price = float(balance_cif / rutile_total_balance_qty)
        elif rutile_total_balance_qty > 0:
            rutile_unit_price = 0.0

        # E1 / E5 per-item plan data.
        primary_norm = ''
        if license_obj.export_license.exists():
            first_export = license_obj.export_license.first()
            if first_export and first_export.norm_class:
                primary_norm = first_export.norm_class.norm_class or ''

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

            import_items_for_plan = (
                LicenseImportItemsModel.objects
                .filter(license=license_obj)
                .select_related('hs_code')
                .prefetch_related('items')
            )
            display_qty = {c: 0.0 for c in _CATS}
            util_qty = {c: 0.0 for c in _CATS}
            per_item_util: Dict[str, float] = {}
            per_item_category: Dict[str, str] = {}
            for ii in import_items_for_plan:
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
                if names:
                    for nm in names:
                        per_item_util[nm] = per_item_util.get(nm, 0.0) + util_inc
                        per_item_category[nm] = cat
                else:
                    nm = ii.description or '-'
                    per_item_util[nm] = per_item_util.get(nm, 0.0) + util_inc
                    per_item_category[nm] = cat

            if primary_norm == 'E1':
                planned, rates = _compute(display_qty, util_qty, float(balance_cif))
            else:
                planned, rates = _compute(display_qty, None, float(balance_cif), None)

            for nm, uq in per_item_util.items():
                cat = per_item_category[nm]
                cat_uq = util_qty.get(cat, 0.0)
                cat_plan = planned.get(cat, 0.0)
                item_plan = (uq / cat_uq) * cat_plan if cat_uq else 0.0
                item_plan_data[nm] = {
                    'unit_price': round(item_plan / uq, 2) if uq else 0.0,
                    'planned_cif': round(item_plan, 2),
                }

        # E132 per-item plan data.
        item_e132_data: Dict[str, Dict[str, Any]] = {}
        if primary_norm == 'E132':
            from apps.license.services.e132_plan import plan_e132_per_item
            _e132_input = []
            for _iid, _inm in all_items:
                if _iid in item_quantities:
                    _d132 = item_quantities[_iid]
                    _e132_input.append({
                        'record_id': _inm,
                        'quantity': float(_d132['available_quantity'] or 0),
                        'hs_code': _d132['hs_code'] or '',
                        'description': _d132['description'] or '',
                    })
            item_e132_data = plan_e132_per_item(_e132_input, float(balance_cif))

        # E132 "as per planning" name filter.
        e132_planned_names = None
        if primary_norm == 'E132' and item_plan_totals is None:
            e132_planned_names = set(item_e132_data.keys())

        planned_item_ids = set(item_plan_totals) if item_plan_totals is not None else None

        for item_id, item_name in all_items:
            if planned_item_ids is not None and item_id not in planned_item_ids:
                show_item = False
            elif e132_planned_names is not None and item_name not in e132_planned_names:
                show_item = False
            else:
                show_item = item_id in item_quantities

            if show_item:
                item_data = item_quantities[item_id]
                _item_plan = (item_plan_totals or {}).get(item_id) or {}

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

                planner = item_plan_data.get(item_name) or {}
                _e132 = item_e132_data.get(item_name) or {}
                if item_name == 'RUTILE - A3627':
                    unit_price = rutile_unit_price
                    planned_cif = planner.get('planned_cif', 0.0)
                elif _e132:
                    _e132_up = _e132.get('unit_price')
                    _e132_cif = _e132.get('planned_cif')
                    unit_price = float(_e132_up) if _e132_up is not None else None
                    planned_cif = float(_e132_cif) if _e132_cif is not None else 0.0
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
                    'plan_quantity': float(_item_plan.get('q') or 0),
                    'plan_cif': float(_item_plan.get('cif') or 0),
                    'condition_type': cond_type,
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

    def export_to_excel_streaming(self, report_data: Dict[str, Any]) -> HttpResponse:
        """
        Export report to Excel — streaming via temp file + WriteOnlyCell.
        """
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.cell import WriteOnlyCell
        from django.http import StreamingHttpResponse
        import tempfile
        import os
        from apps.license.utils.condition_excel import annotate_cell as _annotate_condition_cell

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_file.close()

        try:
            workbook = openpyxl.Workbook(write_only=True)
            licenses_by_norm_notif = report_data.get('licenses_by_norm_notification', {})

            for norm_class in sorted(licenses_by_norm_notif.keys()):
                notifications_dict = licenses_by_norm_notif[norm_class]
                for notification, licenses_list in sorted(notifications_dict.items()):
                    # Filter items to only those with data in THIS norm-notification.
                    items_with_data = []
                    for item in report_data['items']:
                        item_name = item['name']
                        has_data = any(
                            lic['items'].get(item_name, {}).get('quantity', 0) > 0
                            for lic in licenses_list
                        )
                        if has_data:
                            items_with_data.append(item)

                    sheet_name = (
                        f"{norm_class}_{notification}"[:31]
                        .replace('/', '-').replace('\\', '-').replace('*', '-')
                    )
                    worksheet = workbook.create_sheet(title=sheet_name)

                    title_cell = WriteOnlyCell(
                        worksheet,
                        value=f"Item Pivot Report - {norm_class} - {notification}",
                    )
                    title_cell.font = Font(bold=True, size=14)
                    title_cell.alignment = Alignment(horizontal='center')
                    worksheet.append(_xlsx_safe_row([title_cell] + [None] * 25))
                    worksheet.append([])

                    base_headers = [
                        'Sr no', 'DFIA No', 'DFIA Dt', 'Expiry Dt', 'Exporter',
                        'Total CIF', 'Debited CIF', 'Alloted CIF', 'Balance CIF',
                        'Notes', 'Condition Sheet',
                    ]
                    item_headers = []
                    for item in items_with_data:
                        item_name = item['name']
                        has_restriction = item.get('has_restriction', False)
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
                                f"{item_name} Restriction Value",
                            ])
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
                    worksheet.append(_xlsx_safe_row(header_row))

                    for idx, lic in enumerate(licenses_list, 1):
                        row = [
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
                            lic.get('condition_sheet', ''),
                        ]

                        for item in items_with_data:
                            item_name = item['name']
                            has_restriction = item.get('has_restriction', False)
                            item_data = lic['items'].get(item_name, {})
                            cond = item_data.get('condition_type') or ''
                            hsn_cell = WriteOnlyCell(worksheet, value=item_data.get('hs_code', ''))
                            _annotate_condition_cell(hsn_cell, cond)
                            row.append(hsn_cell)
                            row.extend([
                                item_data.get('description', ''),
                                item_data.get('quantity', 0),
                                item_data.get('allotted_quantity', 0),
                                item_data.get('debited_quantity', 0),
                                item_data.get('available_quantity', 0),
                            ])
                            if has_restriction:
                                row.extend([
                                    item_data.get('restriction'),
                                    item_data.get('restriction_value', 0),
                                ])
                            row.append(item_data.get('unit_price') or 0)
                            row.append(item_data.get('planned_cif') or 0)

                        worksheet.append(_xlsx_safe_row(row))

                    # Totals row.
                    totals_row = [WriteOnlyCell(worksheet, value='TOTAL')]
                    totals_row[0].font = Font(bold=True)
                    totals_row.extend([None, None, None, None, None, None])

                    total_cif_cell = WriteOnlyCell(
                        worksheet, value=sum(l['total_cif'] for l in licenses_list)
                    )
                    total_cif_cell.font = Font(bold=True)
                    totals_row.append(total_cif_cell)

                    debited_cif_cell = WriteOnlyCell(
                        worksheet, value=sum(l.get('debited_cif', 0) for l in licenses_list)
                    )
                    debited_cif_cell.font = Font(bold=True)
                    totals_row.append(debited_cif_cell)

                    alloted_cif_cell = WriteOnlyCell(
                        worksheet, value=sum(l['alloted_cif'] for l in licenses_list)
                    )
                    alloted_cif_cell.font = Font(bold=True)
                    totals_row.append(alloted_cif_cell)

                    balance_cif_cell = WriteOnlyCell(
                        worksheet, value=sum(l['balance_cif'] for l in licenses_list)
                    )
                    balance_cif_cell.font = Font(bold=True)
                    totals_row.append(balance_cif_cell)

                    # Notes + Condition Sheet totals skipped (text columns).
                    totals_row.extend([None, None])

                    for item in items_with_data:
                        item_name = item['name']
                        has_restriction = item.get('has_restriction', False)
                        totals_row.extend([None, None])  # HSN, Description
                        for qty_type in ['quantity', 'allotted_quantity', 'debited_quantity', 'available_quantity']:
                            total = sum(l['items'].get(item_name, {}).get(qty_type, 0) for l in licenses_list)
                            cell = WriteOnlyCell(worksheet, value=total)
                            cell.font = Font(bold=True)
                            totals_row.append(cell)
                        if has_restriction:
                            totals_row.append(None)  # Restriction %
                            total_restriction = sum(
                                l['items'].get(item_name, {}).get('restriction_value', 0)
                                for l in licenses_list
                            )
                            cell = WriteOnlyCell(worksheet, value=total_restriction)
                            cell.font = Font(bold=True)
                            totals_row.append(cell)
                        totals_row.append(None)  # Unit Price — blank in totals
                        total_planned = sum(
                            (l['items'].get(item_name, {}).get('planned_cif') or 0)
                            for l in licenses_list
                        )
                        cell = WriteOnlyCell(worksheet, value=total_planned)
                        cell.font = Font(bold=True)
                        totals_row.append(cell)

                    worksheet.append(_xlsx_safe_row(totals_row))

            workbook.save(temp_file.name)
            workbook.close()

            def file_iterator(file_path, chunk_size=8192):
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                try:
                    import os as _os
                    _os.unlink(file_path)
                except OSError:
                    pass

            from django.http import StreamingHttpResponse
            response = StreamingHttpResponse(
                file_iterator(temp_file.name),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            response['Content-Disposition'] = 'attachment; filename="item_pivot_report.xlsx"'
            return response

        except Exception as exc:
            try:
                import os as _os
                _os.unlink(temp_file.name)
            except OSError:
                pass
            raise exc


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------

class ItemPivotViewSet(viewsets.ViewSet):
    """
    ViewSet for Item Pivot Report (licenses × items pivot table).

    OQ-6: async Celery generation is preserved.
    """
    permission_classes = [ReportPermission]

    def list(self, request):
        """Synchronous JSON pivot report (suitable for small datasets)."""
        params = request.GET
        engine = _ItemPivotReportEngine()
        try:
            report_data = engine.generate_report(
                days=_safe_int(params.get('days'), 30),
                sion_norm=params.get('sion_norm'),
                company_ids=params.get('company_ids'),
                exclude_company_ids=params.get('exclude_company_ids'),
                min_balance=_safe_int(params.get('min_balance'), 200),
                license_status=params.get('license_status', 'active'),
                expiry_date_from=params.get('expiry_date_from'),
                expiry_date_to=params.get('expiry_date_to'),
                purchase_status=params.get('purchase_status'),
            )
        except Exception as exc:
            logger.exception("Error generating item pivot report")
            return Response({'error': str(exc)}, status=500)

        output_format = params.get('format', 'json').lower()
        if output_format == 'excel':
            try:
                return engine.export_to_excel_streaming(report_data)
            except Exception as exc:
                logger.exception("Error exporting item pivot report to Excel")
                return Response({'error': str(exc)}, status=500)

        return Response(report_data)

    @action(detail=False, methods=['get'], url_path='available-norms')
    def available_norms(self, request):
        """Return all active SION norm classes for the filter dropdown."""
        try:
            from apps.core.models import SionNormClassModel
            active_norms_data = SionNormClassModel.objects.filter(
                is_active=True
            ).values('norm_class', 'description').order_by('norm_class')
            result = [
                {
                    'norm_class': norm['norm_class'],
                    'description': norm['description'] or '',
                }
                for norm in active_norms_data
            ]
            return Response(result)
        except Exception as exc:
            logger.exception("Error fetching available norms")
            return Response({'error': str(exc)}, status=500)

    @action(detail=False, methods=['post', 'get'], url_path='generate-async')
    def generate_async(self, request):
        """
        Dispatch item pivot Excel generation as a Celery task.

        Returns: {task_id, status, message}
        """
        from apps.license.tasks import generate_item_pivot_task

        params = request.data if request.method == 'POST' else request.GET
        task = generate_item_pivot_task.delay(
            days=int(params.get('days', 30)),
            sion_norm=params.get('sion_norm'),
            company_ids=params.get('company_ids'),
            exclude_company_ids=params.get('exclude_company_ids'),
            min_balance=int(params.get('min_balance', 200)),
            license_status=params.get('license_status', 'active'),
        )
        return Response({
            'task_id': task.id,
            'status': 'PENDING',
            'message': 'Report generation started. Use the task_id to check status.',
        }, status=202)

    @action(detail=False, methods=['get'], url_path='task-status/(?P<task_id>[^/.]+)')
    def task_status(self, request, task_id=None):
        """Poll the status of an async Excel generation task."""
        from celery.result import AsyncResult
        task = AsyncResult(task_id)

        if task.state == 'PENDING':
            response = {'state': task.state, 'current': 0, 'total': 100, 'status': 'Pending...'}
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 100),
                'status': task.info.get('status', ''),
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'current': 100,
                'total': 100,
                'status': 'Completed!',
                'result': task.info,
            }
        else:
            response = {
                'state': task.state,
                'current': 100,
                'total': 100,
                'status': str(task.info) if task.info else 'Unknown error',
            }
        return Response(response)

    @action(detail=False, methods=['post'], url_path='update-balance')
    def update_balance(self, request):
        """
        Trigger high-priority balance update task (updates balance_cif, flags, restrictions).
        """
        from apps.license.tasks import update_all_license_balances_task

        license_status = request.data.get('license_status', 'all')
        task = update_all_license_balances_task.apply_async(
            args=[license_status],
            priority=9,
        )
        return Response({
            'task_id': task.id,
            'status': 'PENDING',
            'license_status': license_status,
            'message': (
                f'Balance update started for {license_status} licenses. '
                f'Use the task_id to check status.'
            ),
        }, status=202)
