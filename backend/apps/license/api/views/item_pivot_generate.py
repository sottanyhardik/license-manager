"""
Item Pivot Report - JSON report assembly (generate_report).
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import (
    Dict,
    Any,
)

from django.db.models import Prefetch

from apps.core.constants import (
    GE,
    MI,
    CO,
)
from apps.core.models import ItemNameModel
from apps.license.models import (
    LicenseDetailsModel, LicenseImportItemsModel,
    LicenseExportItemModel, LicenseTransferModel,
)
from apps.license.services.plan_grouping import (
    merge_planned_import_items as _merge_planned_import_items,
)

logger = logging.getLogger(__name__)

from apps.license.api.views.item_pivot_helpers import (
    _build_notification_summary,
)


class ItemPivotGenerateMixin:
    """Mixin holding methods moved verbatim from ItemPivotReportView."""

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

        # Filter by min_balance against the LIVE, batched-computed balance
        # instead of the cached `balance__balance_cif` column (BL-LEDGER-02:
        # the cache has no signal on reconciliation-allocation changes and
        # can go stale) -- same fix already applied to the License List /
        # Item Report / other report views. Still a fixed number of
        # queries regardless of how many candidate licenses there are.
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        candidate_ids = list(licenses.values_list('id', flat=True))
        live_balance_by_license = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(candidate_ids)
        min_balance_dec = Decimal(str(min_balance))
        matching_ids = [
            i for i in candidate_ids
            if live_balance_by_license.get(i, Decimal('0')) >= min_balance_dec
        ]
        licenses = licenses.filter(id__in=matching_ids)

        # Build filtered prefetch querysets based on sion_norm
        import_items_qs = LicenseImportItemsModel.objects.select_related('hs_code')
        export_items_qs = LicenseExportItemModel.objects.select_related('norm_class')
        # NOTE: do NOT filter is_active here. Inactive item names are still needed
        # so a manually-planned-but-inactive item (e.g. WALNUT planned on an E132
        # DFIA) gets its quantities into item_quantities and renders. The column
        # set (all_items) still hides inactive items via its own is_active check,
        # except those that are explicitly planned (added back below).
        item_names_qs = ItemNameModel.objects.select_related('sion_norm_class')

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
            'notification_number',   # Fix #6: was lazy-loaded per licence (~2×N extra queries)
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
            # Fix #5: ordered Prefetch avoids re-querying with ORDER BY inside _build_license_row
            Prefetch('transfers',
                     queryset=LicenseTransferModel.objects.order_by('-transfer_date', '-id'),
                     to_attr='transfers_ordered'),
        ).order_by('license_expiry_date', 'license_date')

        # Collect all unique items across all licenses
        # Use list() with prefetch_related for optimal performance (iterator breaks prefetch)
        all_items = {}  # Changed to dict to store item object for sorting
        valid_licenses = list(licenses)  # Licenses already filtered by LIVE balance above

        # The legacy report below derives cells from a first attached item and
        # cached per-item ledger columns.  That is not a safe representation
        # for canonical percentage children.  The pivot now has a dedicated
        # report projection built from persisted effective plans plus the
        # item-linked BOE/allotment population.
        from apps.license.services.item_pivot_service import ItemPivotService
        return ItemPivotService.build(valid_licenses)

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
        from apps.license.services.planning_operational_snapshot import planning_operational_snapshots
        from apps.license.services.planning_usage_reconciliation import reconcile_license_plans

        # import_item_id -> first attached item id, mirroring how a plan's
        # totals are attributed to a single item name in _build_license_row().
        first_item_of_import = {}
        for _lo in valid_licenses:
            for _ii in _lo.import_license.all():
                for _it in _ii.items.all():
                    first_item_of_import[_ii.id] = _it.id
                    break

        # Import-reference helpers (use already-prefetched data — no extra queries).
        # item_name_str_by_id: ItemNameModel.id → name str
        # import_qty_by_import_item: LicenseImportItemsModel.id → quantity
        item_name_str_by_id = {}
        import_qty_by_import_item = {}
        # import_item_ledger_by_id: LicenseImportItemsModel.id -> that ONE
        # import item's own HSN/description/ledger quantities. Built from
        # data already prefetched above (no extra queries) — this is the
        # single source of truth a planned cell's HSN/Description/Total/
        # Allotted/Debited/Balance must come from, never a cross-item merge.
        import_item_ledger_by_id = {}
        # Map item_name_id -> first import_item_id tagged with that item_name.
        # Used to infer import_item_id when LicenseItemPlan.import_item_id is NULL.
        item_name_to_import_item_id = {}
        for _lo in valid_licenses:
            for _ii in _lo.import_license.all():
                import_qty_by_import_item[_ii.id] = _ii.quantity
                import_item_ledger_by_id[_ii.id] = {
                    'hs_code': _ii.hs_code.hs_code if _ii.hs_code else '',
                    'description': _ii.description or '',
                    'quantity': float(_ii.quantity or 0),
                    'allotted_quantity': float(_ii.allotted_quantity or 0),
                    'debited_quantity': float(_ii.debited_quantity or 0),
                    'available_quantity': float(_ii.available_quantity or 0),
                }
                for _it in _ii.items.all():
                    if _it.id not in item_name_str_by_id:
                        item_name_str_by_id[_it.id] = _it.name
                    # Map: if this is the FIRST import item tagged with this item_name,
                    # record it (for NULL import_item_id inference later).
                    if _it.id not in item_name_to_import_item_id:
                        item_name_to_import_item_id[_it.id] = _ii.id

        # license_id -> {item_id: {'q': planned qty, 'cif': planned CIF-FC}}.
        # Attributed to the plan LINE's own item_name (not the import item's
        # first attached name) so e.g. a RUTILE plan line on a BORAX+RUTILE
        # import item lands on RUTILE. Untagged split lines fall back to the
        # import item's first attached name. The key set doubles as "which
        # items this DFIA planned" for the per-row filter below.
        plan_totals_by_license = defaultdict(
            lambda: defaultdict(lambda: {
                'q': Decimal('0.000'), 'cif': Decimal('0.00'),
                'theoretical_q': Decimal('0.000'), 'theoretical_cif': Decimal('0.00'),
            })
        )
        # Operational summaries must use the same group reconciliation as the
        # Plan tab. Keep theoretical totals alongside them for audit; never
        # derive utilization-driven reallocations independently in this report.
        reconciliation_by_plan_id = {}
        operational_snapshot_by_plan_id = {}
        for _lo in valid_licenses:
            _reconciliation = reconcile_license_plans(_lo.id)
            reconciliation_by_plan_id.update(_reconciliation['plans'])
            operational_snapshot_by_plan_id.update(
                planning_operational_snapshots(_lo.id, reconciliation=_reconciliation)
            )
        planned_item_ids_all = set()
        # Same query already fetches every LicenseItemPlan row for this page —
        # also keep the raw per-line split (item_name/qty/price/cif) so a
        # "Planning Splits" sheet can be rendered later without a second
        # query. item_name is resolved (id -> name string) once all_items is
        # fully populated, below.
        for _pl in (LicenseItemPlan.objects
                    .filter(license_id__in=[_lo.id for _lo in valid_licenses])
                    .values('id', 'license_id', 'import_item_id', 'item_name_id',
                            'planned_quantity', 'unit_price', 'planned_cif_fc')):
            _iname = _pl['item_name_id'] or first_item_of_import.get(_pl['import_item_id'])
            if _iname is None:
                continue
            _cell = plan_totals_by_license[_pl['license_id']][_iname]
            _cell['operational_snapshot'] = operational_snapshot_by_plan_id.get(_pl['id'])
            _reconciled = reconciliation_by_plan_id.get(_pl['id'], {})
            _operational_qty = _reconciled.get(
                'remaining_quantity', _pl['planned_quantity'] or Decimal('0'),
            )
            _operational_cif = _reconciled.get(
                'remaining_cif', _pl['planned_cif_fc'] or Decimal('0'),
            )
            _cell['q'] += _operational_qty
            _cell['cif'] += _operational_cif
            _cell['theoretical_q'] += _pl['planned_quantity'] or Decimal('0')
            _cell['theoretical_cif'] += _pl['planned_cif_fc'] or Decimal('0')
            _cell.setdefault('splits', []).append({
                # Resolved to a name string in the pass below, once all_items
                # (including manually-planned-but-inactive items) is complete.
                '_item_name_id': _pl['item_name_id'],
                'planned_quantity': float(_pl['planned_quantity'] or 0),
                'unit_price': float(_pl['unit_price'] or 0),
                'planned_cif_fc': float(_pl['planned_cif_fc'] or 0),
                'remaining_quantity': float(_operational_qty),
                'remaining_cif': float(_operational_cif),
            })
            planned_item_ids_all.add(_iname)
            # Track import reference once per planned-item cell (first plan line wins).
            if 'import_item_name' not in _cell:
                _imp_name_id = first_item_of_import.get(_pl['import_item_id'])
                _cell['import_item_name'] = (
                    item_name_str_by_id.get(_imp_name_id, '') if _imp_name_id else ''
                )
                _cell['import_quantity'] = float(
                    import_qty_by_import_item.get(_pl['import_item_id']) or 0
                )

            # Verification data: the EXACT import item(s) this cell's plan
            # lines actually reference, keyed by import_item id so distinct
            # import items sharing this item-name are never merged into one
            # ledger record. Each entry's HSN/Description/ledger quantities
            # come straight from that ONE import item (import_item_ledger_by_id
            # above) — never summed or "first wins" across import items.
            _iid = _pl['import_item_id']

            # FIX: If import_item_id is NULL (legacy plans or split items),
            # infer it from the item_name tag. Look up the first import item
            # that's tagged with this item_name — that's the source being planned.
            if _iid is None and _iname is not None:
                _iid = item_name_to_import_item_id.get(_iname)
                # If no mapping found, _iid stays None (correct for purely synthetic
                # items like "Split Item Name" with no corresponding import item).

            _planned_items = _cell.setdefault('planned_import_items', {})
            if _iid not in _planned_items:
                _ledger = import_item_ledger_by_id.get(_iid, {})
                _planned_items[_iid] = {
                    'import_item_id': _iid,
                    'hs_code': _ledger.get('hs_code', ''),
                    'description': _ledger.get('description', ''),
                    'quantity': _ledger.get('quantity', 0.0),
                    'allotted_quantity': _ledger.get('allotted_quantity', 0.0),
                    'debited_quantity': _ledger.get('debited_quantity', 0.0),
                    'available_quantity': _ledger.get('available_quantity', 0.0),
                    'planned_quantity': Decimal('0'),
                    'planned_cif_fc': Decimal('0'),
                }
            # Multiple plan lines can reference the same import item (e.g. a
            # milk item's DWP + SWP split) — sum ONLY the planned qty/CIF,
            # never the ledger fields, which belong to the item itself.
            _planned_items[_iid]['planned_quantity'] += _operational_qty
            _planned_items[_iid]['planned_cif_fc'] += _operational_cif

        # A manually-planned item must appear as a column even if it is INACTIVE
        # in the master (is_active=False) — the user explicitly planned it, so it
        # would otherwise vanish (the column builder above skips inactive items).
        # Add any planned item ids missing from all_items, honouring the norm filter.
        _missing_planned = [iid for iid in planned_item_ids_all if iid not in all_items]
        if _missing_planned:
            for _it in ItemNameModel.objects.filter(id__in=_missing_planned).select_related('sion_norm_class'):
                if not _it.name:
                    continue
                if sion_norm and not (_it.sion_norm_class and _it.sion_norm_class.norm_class == sion_norm):
                    continue
                all_items[_it.id] = _it

        # Resolve each split's own item_name tag (id -> name string) now that
        # all_items includes every planned item, even inactive/filtered ones
        # not directly M2M-attached to their import item. No new query — just
        # a dict merge of data already fetched above. Falls back to None
        # (→ "Split N" badge, same as plan_reporting._build_map) for the rare
        # id that still isn't resolvable (e.g. filtered out by sion_norm).
        _split_item_name_lookup = dict(item_name_str_by_id)
        _split_item_name_lookup.update({iid: (it.name or '') for iid, it in all_items.items()})
        for _lic_cells in plan_totals_by_license.values():
            for _cell in _lic_cells.values():
                for _sp in _cell.get('splits', []):
                    _nid = _sp.pop('_item_name_id', None)
                    _sp['item_name'] = _split_item_name_lookup.get(_nid) if _nid is not None else None

                # planned_import_items: dict-of-dicts (keyed by import_item id,
                # for O(1) accumulation above) -> plain list, Decimal -> float.
                # This is the per-cell verification data: each entry is a real
                # import item a plan line referenced. Distinct import items are
                # then consolidated by `merge_planned_import_items` (HSN +
                # normalized description) purely for readability — e.g. three
                # "PP - E1" import items that are really one physical product
                # split across serial numbers render as one row instead of
                # three; import items that are genuinely different products
                # (different HSN or description) are never merged.
                _pit_map = _cell.get('planned_import_items')
                if _pit_map:
                    _cell['planned_import_items'] = _merge_planned_import_items(
                        {
                            **_pit,
                            'planned_quantity': float(_pit['planned_quantity']),
                            'planned_cif_fc': float(_pit['planned_cif_fc']),
                        }
                        for _pit in _pit_map.values()
                    )
                else:
                    _cell['planned_import_items'] = []

        # Sort items by display_order first, then by name for consistent column order
        sorted_items = sorted(
            [(item.id, item.name) for item in all_items.values()],
            key=lambda x: (all_items[x[0]].display_order, x[1] or '')
        )

        # Batch document-type lookups: one query for the whole page instead of two
        # .exists() calls per licence inside _build_license_row (an N+1 over the report).
        from apps.license.models import LicenseDocumentModel
        doc_types_by_license = defaultdict(set)
        for _lid, _dt in (LicenseDocumentModel.objects
                          .filter(license_id__in=[_lo.id for _lo in valid_licenses])
                          .values_list('license_id', 'type')):
            doc_types_by_license[_lid].add(_dt)

        # Batch the condition-pool computation (was ~13 queries PER licence inside
        # _build_license_row — the report's dominant N+1) into a handful of queries.
        from apps.license.services.condition_pool import compute_condition_pools_bulk
        cond_pools_by_license = compute_condition_pools_bulk([_lo.id for _lo in valid_licenses])

        # Fix #2: batch AllotmentItems query — was 1 query PER licence (N+1).
        # One query returns cif_fc sums keyed by license_id. NOTE: this is a
        # DFIA-specific "Alloted CIF" column (`is_allotted=True` is the DFIA
        # allotment flag, see AllotmentModel's help_text) — a narrower,
        # separate metric from the shared Balance CIF's allotment component
        # (`LicenseBalanceCalculator.calculate_allotment`), not a duplicate
        # of it; left as-is.
        from apps.allotment.models import AllotmentItems as _AllotmentItems
        _license_ids = [_lo.id for _lo in valid_licenses]
        alloted_cif_by_license: dict = defaultdict(lambda: Decimal('0'))
        for _row in _AllotmentItems.objects.filter(
            item__license_id__in=_license_ids,
            allotment__is_allotted=True,
            allotment__bill_of_entry__isnull=True,
        ).values('item__license_id', 'cif_fc'):
            if _row['cif_fc'] is not None:
                alloted_cif_by_license[_row['item__license_id']] += Decimal(str(_row['cif_fc']))

        # Balance CIF must be identical everywhere in the app — read LIVE via
        # the shared `LicenseBalanceCalculator` (same batched method the
        # License List view uses), never the denormalized `balance_cif`
        # column directly, which is only refreshed by a background task/
        # manual trigger and can go stale relative to the live calculation
        # (e.g. right after a Balance Engine formula change, or any edit
        # that doesn't happen to fire a recalculation signal).
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        # Financial Ledger formula -- see `LicenseDetailsModel.
        # get_balance_cif`'s docstring; must match every other "Balance
        # CIF" in the app.
        live_balance_by_license = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(_license_ids)

        # Build license data with item columns, grouped by norm first, then notification
        # (defaultdict is imported at module level).
        licenses_by_norm_notification = defaultdict(lambda: defaultdict(list))

        for license_obj in valid_licenses:
            license_row = self._build_license_row(
                license_obj, sorted_items,
                item_plan_totals=plan_totals_by_license.get(license_obj.id),
                document_types=doc_types_by_license.get(license_obj.id, frozenset()),
                condition_pools=cond_pools_by_license.get(license_obj.id, {}),
                alloted_cif=alloted_cif_by_license.get(license_obj.id, Decimal('0')),
                balance_cif=live_balance_by_license.get(license_obj.id, Decimal('0')),
            )

            if license_row:
                # Handle blank/empty notification numbers
                notification = (license_obj.notification_number.code if license_obj.notification_number_id else '').strip()
                if not notification:
                    notification = 'Unknown'

                # Fix #4: use prefetch cache — .exists()/.first() bypass it and re-query
                norm_class = 'Unknown'
                _exports = list(license_obj.export_license.all())
                if _exports and _exports[0].norm_class:
                    norm_class = _exports[0].norm_class.norm_class or 'Unknown'

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

        # Grand totals per (norm, notification) group — the single backend-
        # owned computation of what used to be independently re-summed by
        # both the React page and the Excel exporter's totals row (Phase
        # 2B.2A; see docs/architecture/ITEM_PIVOT_DISPLAY_DATASET_DESIGN.md).
        # Additive top-level key — `licenses_by_norm_notification`'s existing
        # shape is unchanged, no API field renamed.
        # Notification/Norm Summary — the backend-owned translation of the
        # frontend's `calculateNotificationSummary` (Phase 2B.2B; see
        # docs/architecture/ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md).
        # Built in the same pass over the same `licenses_list`s as
        # `notification_totals` above — no second full iteration needed.
        # Purely additive: nothing in `ItemPivotReport.tsx` reads these keys
        # yet (that is a later, separate phase per the design doc's §7).
        notification_totals = {}
        notification_summary = {}
        norm_summary = {}
        for norm, notification_dict in result_dict.items():
            notification_totals[norm] = {}
            notification_summary[norm] = {}
            for notification_key, licenses_list in notification_dict.items():
                item_totals = {}
                for item_id, item_name in sorted_items:
                    item_totals[item_name] = {
                        'quantity': sum(
                            lic['items'].get(item_name, {}).get('quantity', 0) or 0
                            for lic in licenses_list
                        ),
                        'allotted_quantity': sum(
                            lic['items'].get(item_name, {}).get('allotted_quantity', 0) or 0
                            for lic in licenses_list
                        ),
                        'debited_quantity': sum(
                            lic['items'].get(item_name, {}).get('debited_quantity', 0) or 0
                            for lic in licenses_list
                        ),
                        'available_quantity': sum(
                            lic['items'].get(item_name, {}).get('available_quantity', 0) or 0
                            for lic in licenses_list
                        ),
                        'restriction_value': sum(
                            lic['items'].get(item_name, {}).get('restriction_value', 0) or 0
                            for lic in licenses_list
                        ),
                        # Literal sum of manual plan_quantity only — matches
                        # the on-screen/Excel `totalPlanQty` convention: rows
                        # with no manual plan (norm-derived, shown as a
                        # unit-price rate per-row) contribute 0 here rather
                        # than being folded into a blended rate.
                        'plan_quantity': sum(
                            lic['items'].get(item_name, {}).get('plan_quantity', 0) or 0
                            for lic in licenses_list
                        ),
                        # Manual-vs-norm selection already resolved per cell
                        # by _effective_planned_cif — just sum it here.
                        'effective_planned_cif': sum(
                            lic['items'].get(item_name, {}).get('effective_planned_cif', 0) or 0
                            for lic in licenses_list
                        ),
                    }
                notification_totals[norm][notification_key] = {
                    'total_cif': sum(lic['total_cif'] for lic in licenses_list),
                    'debited_cif': sum(lic.get('debited_cif', 0) for lic in licenses_list),
                    'alloted_cif': sum(lic['alloted_cif'] for lic in licenses_list),
                    'balance_cif': sum(lic['balance_cif'] for lic in licenses_list),
                    # Grand Planned CIF across every item column — equals
                    # summing `total_effective_planned_cif` across licenses,
                    # or summing `effective_planned_cif` across items; kept
                    # as its own field so consumers never need to reduce
                    # either axis themselves.
                    'total_effective_planned_cif': sum(
                        lic.get('total_effective_planned_cif', 0) for lic in licenses_list
                    ),
                    'items': item_totals,
                }

                notification_summary[norm][notification_key] = _build_notification_summary(
                    licenses_list, sorted_items,
                )

            # Norm-level summary: same builder, flattened across every
            # notification group under this norm — mirrors the frontend's
            # `:1531` call site (`Object.values(...).flat()`).
            norm_summary[norm] = _build_notification_summary(
                [lic for licenses_list in notification_dict.values() for lic in licenses_list],
                sorted_items,
            )

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
            'notification_totals': notification_totals,
            'notification_summary': notification_summary,
            'norm_summary': norm_summary,
            'norm_notes_conditions': norm_notes_conditions,
            'report_date': today.isoformat(),
        }
