"""
Item Pivot Report - per-licence row assembly (_build_license_row).
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Any


from apps.core.constants import (
    DEC_0,
    DEC_000,
)
from apps.license.models import (
    LicenseDetailsModel,
)
from apps.license.services.plan_grouping import (
    merge_planned_import_items as _merge_planned_import_items,
)

logger = logging.getLogger(__name__)

from apps.license.api.views.item_pivot_helpers import (
    _effective_planned_cif,
    _effective_planned_quantity,
)


class ItemPivotRowMixin:
    """Mixin holding methods moved verbatim from ItemPivotReportView."""

    def _build_license_row(self, license_obj: LicenseDetailsModel, all_items: List[tuple],
                           item_plan_totals=None, document_types=None,
                           condition_pools=None, alloted_cif=None, balance_cif=None) -> Dict[str, Any]:
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

        # Fix #2: alloted_cif pre-computed by generate_report in a single batch query.
        # Standalone callers (e.g. Excel export called directly) fall back to the
        # per-licence query so behaviour is unchanged outside the main report path.
        if alloted_cif is None:
            from apps.allotment.models import AllotmentItems as _AI
            _alloted_cif = Decimal('0')
            for _ai in _AI.objects.filter(
                item__license=license_obj,
                allotment__is_allotted=True,
                allotment__bill_of_entry__isnull=True,
            ).values_list('cif_fc', flat=True):
                if _ai is not None:
                    _alloted_cif += Decimal(str(_ai))
            alloted_cif = _alloted_cif

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

        # Fix #1: plan_map_for_license was called per-licence here (N extra queries).
        # generate_report already batches all LicenseItemPlan rows and passes the
        # per-licence totals via item_plan_totals, so this extra call is redundant.
        # Standalone callers that pass item_plan_totals=None get _plan_map=None (same
        # as before — plan_source falls back to 'norm', which is correct).

        # Per condition_type pool — new restriction model. Each "N%" pool is
        # shared by every import item on this licence with that condition_type,
        # and provides the per-cell `restriction_value` shown in the pivot.
        # Use the report's batched pools when provided; else compute per-licence
        # (standalone callers).
        if condition_pools is None:
            from apps.license.services.condition_pool import compute_condition_pools
            condition_pools = compute_condition_pools(license_obj)
        # condition_pools = {"2%": Decimal(...), "3%": Decimal(...), ...}

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

        # `balance_cif` is pre-computed LIVE by `generate_report` in a single
        # batched `calculate_financial_balance_for_licenses` call (the
        # Financial Ledger formula, same shared Balance Engine used
        # everywhere else — see `LicenseDetailsModel.get_balance_cif`'s
        # docstring) and passed in here — never the denormalized
        # `license_obj.balance_cif` column directly, which is only
        # refreshed by a background task/manual trigger and can go stale.
        # Standalone callers (balance_cif=None) fall back to a live
        # per-licence calculation so behaviour is unchanged outside the main
        # report path — see `alloted_cif`'s identical fallback above.
        if balance_cif is None:
            from apps.license.services.balance_calculator import LicenseBalanceCalculator
            balance_cif = LicenseBalanceCalculator.calculate_financial_balance(license_obj)

        # Build row data
        # Handle blank/empty notification numbers
        notification_display = (license_obj.notification_number.code if license_obj.notification_number_id else '').strip()
        if not notification_display:
            notification_display = 'Unknown'

        # Check for document types — use the batched map when the report supplies it,
        # else fall back to a per-object query (standalone callers).
        if document_types is None:
            document_types = {d.type for d in license_obj.license_documents.all()}
        has_tl = 'TRANSFER LETTER' in document_types
        has_copy = 'LICENSE COPY' in document_types

        # Fix #5: use pre-ordered to_attr list — avoids re-querying with ORDER BY
        latest_transfer_text = ''
        _transfers = getattr(license_obj, 'transfers_ordered', None)
        if _transfers is None:
            # Standalone caller (no Prefetch to_attr) — fall back to queryset
            _transfers = list(license_obj.transfers.order_by('-transfer_date', '-id'))
        if _transfers:
            latest_transfer_text = str(_transfers[0])
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
            # plan line, else 'norm'. Uses the already-available item_plan_totals
            # so no extra query is needed (see Fix #1 above).
            'plan_source': 'manual' if item_plan_totals else 'norm',
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
            rutile_unit_price = float(max(balance_cif, Decimal('0')) / rutile_total_balance_qty)  # CAP clamp
        elif rutile_total_balance_qty > 0:
            rutile_unit_price = 0.0

        # ── Per-item Unit Price + Planned CIF (from persisted LicenseItemPlan) ──
        # Read ONLY from saved canonical LicenseItemPlan. No planner calls.
        # If a license has no persisted plan: show 0 / not planned.
        # This separates read paths (reports) from write paths (planning).
        from apps.license.models import LicenseItemPlan

        # `item_plan_data[item_name]` → {'planned_cif': float, 'unit_price': float, 'planned_import_items': [...]}
        item_plan_data: Dict[str, Dict[str, float]] = {}

        # Read persisted plans for this license grouped by item name
        plans = (
            LicenseItemPlan.objects
            .filter(license=license_obj)
            .select_related('import_item', 'item_name')
            .values('import_item_id', 'item_name__name', 'planned_quantity', 'planned_cif_fc', 'unit_price')
        )

        if plans.exists():
            # Aggregate persisted plans by item name
            plan_by_item_name: Dict[str, dict] = {}
            import_item_data: Dict[int, dict] = {}

            # Build ledger for import items
            for ii in license_obj.import_license.all():
                import_item_data[ii.id] = {
                    'hs_code': ii.hs_code.hs_code if ii.hs_code else '',
                    'description': ii.description or '',
                    'quantity': float(ii.quantity or 0),
                    'allotted_quantity': float(ii.allotted_quantity or 0),
                    'debited_quantity': float(ii.debited_quantity or 0),
                    'available_quantity': float(ii.available_quantity or 0),
                }

            # Aggregate plans by item name
            for plan in plans:
                item_name = plan['item_name__name'] or "Unspecified"
                if item_name not in plan_by_item_name:
                    plan_by_item_name[item_name] = {
                        'total_qty': Decimal('0'),
                        'total_cif': Decimal('0'),
                        'items_by_import_id': {},
                        'count': 0,
                    }

                iid = plan['import_item_id']
                qty = Decimal(str(plan['planned_quantity'] or 0))
                cif = Decimal(str(plan['planned_cif_fc'] or 0))

                plan_by_item_name[item_name]['total_qty'] += qty
                plan_by_item_name[item_name]['total_cif'] += cif
                plan_by_item_name[item_name]['count'] += 1

                # Track per-import-item plan
                if iid not in plan_by_item_name[item_name]['items_by_import_id']:
                    ledger = import_item_data.get(iid, {})
                    plan_by_item_name[item_name]['items_by_import_id'][iid] = {
                        'import_item_id': iid,
                        'hs_code': ledger.get('hs_code', ''),
                        'description': ledger.get('description', ''),
                        'quantity': ledger.get('quantity', 0.0),
                        'allotted_quantity': ledger.get('allotted_quantity', 0.0),
                        'debited_quantity': ledger.get('debited_quantity', 0.0),
                        'available_quantity': ledger.get('available_quantity', 0.0),
                        'planned_quantity': 0.0,
                        'planned_cif_fc': 0.0,
                    }

                plan_by_item_name[item_name]['items_by_import_id'][iid]['planned_quantity'] += float(qty)
                plan_by_item_name[item_name]['items_by_import_id'][iid]['planned_cif_fc'] += float(cif)

            # Build item_plan_data from aggregated persisted plans
            for item_name, data in plan_by_item_name.items():
                total_qty = float(data['total_qty'])
                total_cif = float(data['total_cif'])
                unit_price = round(total_cif / total_qty, 2) if total_qty else 0.0

                item_plan_data[item_name] = {
                    'unit_price': unit_price,
                    'planned_cif': round(total_cif, 2),
                    'planned_import_items': _merge_planned_import_items(
                        data['items_by_import_id'].values(),
                    ),
                }

        # If no plans exist for this license: item_plan_data stays empty
        # This causes all planned_quantity/planned_cif values to be 0 in the output

        # If no plans exist for this license: item_plan_data stays empty,
        # resulting in all planned_quantity/planned_cif values being 0 in the report.
        # This is correct behavior — no explicit plan means NOT_PLANNED.

        # E132/E126 have been migrated to read-only from LicenseItemPlan as well.
        # Legacy planner logic removed. All norms now read from persisted plans only.
        item_e132_data: Dict[str, Dict[str, Any]] = {}

        # Visibility logic: which items to show in the pivot grid.
        # All planning is now read-only from persisted LicenseItemPlan.
        # No on-the-fly planning or E132 auto-classification in read paths.
        e132_planned_names = None

        # Add item columns
        planned_item_ids = set(item_plan_totals) if item_plan_totals is not None else None
        for item_id, item_name in all_items:
            # Per-product visibility — two priorities:
            #
            # 1. Explicit persisted plan (LicenseItemPlan rows) → show ONLY the
            #    explicitly planned items. Planned items may be ItemNameModel
            #    entries not linked to the import via M2M (e.g. "SWP - E1"
            #    planned from a "Milk Powder" import item) so the `item_id in
            #    item_quantities` guard is intentionally dropped; the cell falls
            #    back to zero import quantities for such items, which is correct.
            #
            # 2. No persisted plan → show all items that have import data
            #    OR persisted plan data (now reading from LicenseItemPlan only,
            #    never from on-the-fly planning).
            _has_manual = planned_item_ids is not None and item_id in planned_item_ids
            _has_persisted_plan = bool(item_plan_data.get(item_name))

            if item_plan_totals is not None:
                # Priority 1 — explicit persisted plan: show only planned items
                show_item = _has_manual
            else:
                # Priority 2 — no persisted plan: show items with import data
                # or persisted plan data
                show_item = item_id in item_quantities or _has_persisted_plan

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
                    # E132 reuses the Unit Price / Planned CIF columns to show the
                    # classified planning item's fixed unit price and planned value
                    # (balance-capped). Unit Price is None and Planned CIF 0 for any
                    # item whose price is still To-Be-Defined.
                    _e132_up = _e132.get('unit_price')
                    _e132_cif = _e132.get('planned_cif')
                    unit_price = float(_e132_up) if _e132_up is not None else None
                    planned_cif = float(_e132_cif) if _e132_cif is not None else 0.0
                else:
                    unit_price = planner.get('unit_price')
                    planned_cif = planner.get('planned_cif', 0.0)

                # Verification data (Item Pivot Report enhancement): when this
                # cell has actual LicenseItemPlan rows behind it, HSN/
                # Description/ledger quantities must come from the EXACT
                # import item(s) those plan lines reference — never the
                # cross-item-name-merged `item_data` aggregate above. Exactly
                # one planned import item (the overwhelming common case,
                # since Auto-Plan/manual plans normally anchor on one
                # representative item) is used directly; several distinct
                # import items are never merged into one ledger record — the
                # scalar columns are left blank and every one of them is
                # exposed, unmerged, via `planned_import_items` instead.
                # Cells with NO plan line (E132 auto-classification, or no
                # planning context at all) keep the existing aggregate
                # behaviour unchanged — this is a verification aid for
                # planned items only, not a report redesign.
                #
                # Persisted `LicenseItemPlan` rows (`_item_plan`) take
                # priority when present (exact DB rows). Licences that were
                # never explicitly Auto-Plan-"saved" have no such rows, but
                # still show a LIVE norm-waterfall recompute for CIF/rate
                # (`planner`, built above from `item_plan_data`) — that path
                # carries its own `planned_import_items` built the same way,
                # so it must be checked too or a never-saved licence's cells
                # fall back to the old cross-item-name-merged aggregate.
                _pit_list = _item_plan.get('planned_import_items') or planner.get('planned_import_items') or []
                if len(_pit_list) == 1:
                    _pit = _pit_list[0]
                    _hs_code = _pit['hs_code']
                    _description = _pit['description']
                    _quantity = _pit['quantity']
                    _allotted_quantity = _pit['allotted_quantity']
                    _debited_quantity = _pit['debited_quantity']
                    _available_quantity = _pit['available_quantity']
                elif len(_pit_list) > 1:
                    # Genuinely ambiguous — distinct import items were planned
                    # under the same item-name. HSN/Description are STRINGS:
                    # there is no correct single value, so they are left
                    # blank rather than merged, glued, or picked arbitrarily;
                    # the frontend renders each entry from
                    # `planned_import_items` instead. Quantities are NOT
                    # ambiguous the same way — summing them across the
                    # distinct import items sharing this column is factually
                    # correct (identical to the unplanned-cell aggregate
                    # below) and keeps this report's own on-screen totals and
                    # the Excel TOTAL row accurate; zeroing them out here
                    # would silently under-count both.
                    _hs_code = ''
                    _description = ''
                    _quantity = sum((p['quantity'] for p in _pit_list), 0.0)
                    _allotted_quantity = sum((p['allotted_quantity'] for p in _pit_list), 0.0)
                    _debited_quantity = sum((p['debited_quantity'] for p in _pit_list), 0.0)
                    _available_quantity = sum((p['available_quantity'] for p in _pit_list), 0.0)
                else:
                    _hs_code = item_data['hs_code']
                    _description = item_data['description']
                    _quantity = float(item_data['quantity'])
                    _allotted_quantity = float(item_data['allotted_quantity'])
                    _debited_quantity = float(item_data['debited_quantity'])
                    _available_quantity = float(item_data['available_quantity'])

                # A saved plan references one representative import row even
                # when its SION rule matched a larger source group. Replace
                # only the ledger quantity columns with the canonical group
                # snapshot; plan and reconciliation columns remain separate.
                _snapshot = _item_plan.get('operational_snapshot')
                if _snapshot:
                    _quantity = float(_snapshot['original_total_qty'])
                    _allotted_quantity = float(_snapshot['unlinked_allotment_qty'])
                    _debited_quantity = float(_snapshot['boe_debited_qty'])
                    _available_quantity = float(_snapshot['balance_qty'])

                row_data['items'][item_name] = {
                    'hs_code': _hs_code,
                    'description': _description,
                    'quantity': _quantity,
                    'allotted_quantity': _allotted_quantity,
                    'debited_quantity': _debited_quantity,
                    'available_quantity': _available_quantity,
                    # Verification list: the exact import item(s) behind this
                    # cell's plan lines (empty when the cell has no plan).
                    # Always the authoritative per-item source — HSN/
                    # Description/ledger quantities never mixed across items.
                    'planned_import_items': _pit_list,
                    'restriction': restriction_value,
                    'restriction_value': float(available_cif),
                    'unit_price': unit_price,
                    'planned_cif': planned_cif,
                    # User-authored plan (distinct from the norm-derived
                    # planned_cif), sourced per plan-line item_name.
                    'plan_quantity': float(_item_plan.get('q') or 0),
                    'plan_cif': float(_item_plan.get('cif') or 0),
                    'theoretical_plan_quantity': float(_item_plan.get('theoretical_q') or 0),
                    'theoretical_plan_cif': float(_item_plan.get('theoretical_cif') or 0),
                    'original_total_qty': float(_snapshot['original_total_qty']) if _snapshot else _quantity,
                    'boe_debited_qty': float(_snapshot['boe_debited_qty']) if _snapshot else _debited_quantity,
                    'unlinked_allotment_qty': float(_snapshot['unlinked_allotment_qty']) if _snapshot else _allotted_quantity,
                    'balance_qty': float(_snapshot['balance_qty']) if _snapshot else _available_quantity,
                    # The single manual-vs-norm selection rule — see
                    # _effective_planned_cif's docstring. Every consumer
                    # should read this instead of re-deriving the rule.
                    'effective_planned_cif': (
                        float(_item_plan.get('cif') or 0)
                        if _has_manual else _effective_planned_cif(0, 0, planned_cif)
                    ),
                    # Quantity counterpart to effective_planned_cif — see
                    # _effective_planned_quantity's docstring. First consumer
                    # is _build_notification_summary's Pass 3 (Phase 2B.2B).
                    'effective_planned_quantity': (
                        float(_item_plan.get('q') or 0)
                        if _has_manual else _effective_planned_quantity(0, 0, _available_quantity)
                    ),
                    # Raw per-line split breakdown (item_name/qty/unit_price/
                    # cif) for the "Planning Splits" sheet — same source as
                    # plan_quantity/plan_cif above, just not summed.
                    'splits': _item_plan.get('splits', []),
                    'condition_type': cond_type,
                    # E132 sequential-debit fields (None for non-E132 norms).
                    'product_code': _e132.get('product_code'),
                    'unit_rate': _e132.get('unit_rate'),
                    'debit_amount': _e132.get('debit_amount'),
                    'previous_balance': _e132.get('previous_balance'),
                    'new_balance': _e132.get('new_balance'),
                    'debit_status': _e132.get('status'),
                    # Import reference — always from the original import item.
                    # For planned licences the import_item_name/quantity come from
                    # the plan cell; for unplanned licences fall back to the
                    # column name and the import quantity already in item_data.
                    'import_item_name': _item_plan.get('import_item_name') or item_name,
                    'import_quantity': (
                        _item_plan['import_quantity']
                        if 'import_quantity' in _item_plan
                        else float(item_data['quantity'])
                    ),
                }
            else:
                row_data['items'][item_name] = {
                    'hs_code': '',
                    'description': '',
                    'quantity': 0,
                    'allotted_quantity': 0,
                    'debited_quantity': 0,
                    'available_quantity': 0,
                    'planned_import_items': [],
                    'restriction': None,
                    'restriction_value': 0,
                    'unit_price': None,
                    'planned_cif': 0,
                    'plan_quantity': 0,
                    'plan_cif': 0,
                    'effective_planned_cif': 0,
                    'effective_planned_quantity': 0,
                    'splits': [],
                    'condition_type': '',
                    'product_code': None,
                    'unit_rate': None,
                    'debit_amount': None,
                    'previous_balance': None,
                    'new_balance': None,
                    'debit_status': None,
                    'import_item_name': '',
                    'import_quantity': 0,
                }

        # This license's Planned CIF row-total — sum of each item's already-
        # resolved `effective_planned_cif` (Phase 2B.2A). Zero-valued items
        # (no data for this license) don't affect the sum, so this equals
        # summing over any narrower "items with data" subset a consumer
        # might otherwise have filtered to first.
        row_data['total_effective_planned_cif'] = sum(
            item.get('effective_planned_cif', 0) or 0 for item in row_data['items'].values()
        )

        return row_data
