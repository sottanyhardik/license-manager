"""Bulk (one sheet per licence) balance workbook builder. Split out of
``license_balance_excel.py``; behaviour unchanged.
"""


def build_bulk_balance_excel(request):
    """
    Generate a multi-sheet Excel with one sheet per license.
    Sheet name = license number. Same layout as balance_excel.
    POST body: {"license_numbers": ["3011007415", "3011007018", ...]}
    """
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from io import BytesIO
    from collections import defaultdict
    from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
    from apps.allotment.models import AllotmentItems
    from rest_framework.response import Response
    from apps.license.models import LicenseDetailsModel

    license_numbers = request.data.get('license_numbers')
    if not isinstance(license_numbers, list):
        return Response({'error': 'license_numbers must be a non-empty list of strings.'}, status=400)

    license_numbers = [item.strip() for item in license_numbers if isinstance(item, str) and item.strip()]
    if not license_numbers:
        return Response({'error': 'license_numbers must be a non-empty list of strings.'}, status=400)
    license_numbers = list(dict.fromkeys(license_numbers))

    licenses = LicenseDetailsModel.objects.filter(
        license_number__in=license_numbers
    ).prefetch_related('import_license', 'import_license__items')

    if not licenses.exists():
        return Response({'error': 'No matching licenses found.'}, status=404)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default empty sheet

    # ── Shared styles ──────────────────────────────────────────────────────
    HDR_FILL   = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    HDR_FONT   = Font(bold=True, color="FFFFFF", size=9)
    BOE_FILL   = PatternFill(start_color="DEEAF1", end_color="DEEAF1", fill_type="solid")
    ALLOT_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    TOTAL_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    YEL_FILL   = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    ALT_FILL   = PatternFill(start_color="F9F9F9", end_color="F9F9F9", fill_type="solid")
    BOLD       = Font(bold=True, size=9)
    NORM       = Font(size=9)
    THIN_BORDER = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    def _hdr(ws, row, col, value):
        c = ws.cell(row=row, column=col, value=value)
        c.fill = HDR_FILL; c.font = HDR_FONT
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        return c

    def _cell(ws, row, col, value, fill=None, bold=False, align='left', num_fmt=None):
        c = ws.cell(row=row, column=col, value=value)
        if fill: c.fill = fill
        c.font = BOLD if bold else NORM
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
        if num_fmt: c.number_format = num_fmt
        return c

    def _write_license_sheet(wb, license_obj):
        from datetime import date as _date_cls
        requested_sheet_name = str(license_obj.license_number or license_obj.pk)[:31]
        ws = wb.create_sheet(title=requested_sheet_name)
        sheet_name = ws.title

        license_date_str = license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-'
        license_expiry_str = license_obj.license_expiry_date.strftime('%d-%m-%Y') if license_obj.license_expiry_date else '-'
        ledger_date_str = license_obj.ledger_date.strftime('%d-%m-%Y') if license_obj.ledger_date else '-'
        lic_no = license_obj.license_number or '-'

        summary_rows = []
        total_cif = 0.0
        total_cif_inr = 0.0

        for item in license_obj.import_license.all():
            item_name = ', '.join(_nm) if (_nm := [i.name for i in item.items.all()]) else (item.description or '-')

            # Previous-owner "hidden" BOEs (genuinely hidden per audit
            # trail) are excluded — this bulk export is a balance/
            # financial figure, not the Customs History audit view.
            boes = annotate_and_exclude_hidden(
                RowDetails.objects.filter(sr_number_id=item.id, transaction_type='D'),
                boe_field="bill_of_entry",
            ).select_related('bill_of_entry', 'bill_of_entry__port', 'bill_of_entry__company')

            for rd in boes:
                qty  = float(rd.qty or 0)
                cif  = float(rd.cif_fc or 0)
                cif_inr = float(rd.cif_inr or 0)
                rate = cif / qty if qty else 0.0
                total_cif += cif
                total_cif_inr += cif_inr
                boe_company = rd.bill_of_entry.company.name if rd.bill_of_entry.company else '-'
                ref_no   = rd.bill_of_entry.bill_of_entry_number or '-'
                ref_date = rd.bill_of_entry.bill_of_entry_date.strftime('%d-%m-%Y') if rd.bill_of_entry.bill_of_entry_date else ''
                ref_str  = f"{ref_no} / {ref_date}" if ref_date else ref_no
                product  = rd.bill_of_entry.product_name or item_name
                _sort_dt = rd.bill_of_entry.bill_of_entry_date or _date_cls.min
                summary_rows.append((0, _sort_dt, {
                    'item': product, 'type': 'BOE', 'company': boe_company,
                    'reference': ref_str, 'qty': qty, 'rate': rate, 'cif': cif,
                    'cif_inr': cif_inr,
                }, True))

            allotments = AllotmentItems.objects.filter(
                item_id=item.id, allotment__bill_of_entry__isnull=True
            ).select_related('allotment', 'allotment__company')

            for ai in allotments:
                qty     = float(ai.qty or 0)
                cif     = float(ai.cif_fc or 0)
                cif_inr = float(ai.cif_inr or 0)
                rate    = cif / qty if qty else 0.0
                total_cif += cif
                total_cif_inr += cif_inr
                company = ai.allotment.company.name if ai.allotment.company else '-'
                invoice = ai.allotment.invoice or '-'
                eta     = ai.allotment.estimated_arrival_date.strftime('%d-%m-%Y') if ai.allotment.estimated_arrival_date else ''
                ref_str = f"{invoice} / ETA: {eta}" if eta else invoice
                product = ai.allotment.item_name or item_name
                _sort_dt = ai.allotment.estimated_arrival_date or _date_cls.min
                summary_rows.append((1, _sort_dt, {
                    'item': product, 'type': 'Allotment', 'company': company,
                    'reference': ref_str, 'qty': qty, 'rate': rate, 'cif': cif,
                    'cif_inr': cif_inr,
                }, False))

        # BOEs first (sorted by BOE date), then allotments (sorted by allotment date)
        summary_rows.sort(key=lambda x: (x[0], x[1]))

        # New restriction model: condition_type on LicenseImportItemsModel is
        # the source of truth. Percentage conditions share a pool computed
        # by compute_condition_pools(); AU / blank conditions use the full
        # licence balance.
        from apps.license.services.condition_pool import compute_condition_pools as _ccp
        _cond_pools = _ccp(license_obj)

        _bal_agg = defaultdict(lambda: {
            'qty': 0.0, 'total_qty': 0.0, 'sr_ids': [],
            'description': '', 'hs_code': '', 'condition_type': '',
            'qty_by_cond': {},
            'plan_qty': 0.0, 'plan_cif': 0.0,
        })
        # Pre-computed once for every exported license by the caller (see
        # `_balance_by_license` in `build_bulk_balance_excel`) — reused here
        # to avoid re-triggering `get_balance_cif` for every license.
        _license_balance = float(_balance_by_license.get(license_obj.id, 0) or 0)
        # Read persisted plan from LicenseItemPlan only (NO planner calls in read path).
        from apps.license.models import LicenseItemPlan
        from decimal import Decimal

        # Fetch persisted plans for this license
        persisted_plans = (
            LicenseItemPlan.objects
            .filter(license=license_obj)
            .select_related('import_item')
            .values('import_item_id', 'planned_quantity', 'planned_cif_fc')
        )

        # Build plan map: import_item_id -> {planned_quantity, planned_cif}
        _plan_map = {}
        _plan_source = ''
        for plan in persisted_plans:
            iid = plan['import_item_id']
            if iid not in _plan_map:
                _plan_map[iid] = {
                    'planned_quantity': Decimal('0'),
                    'planned_cif': Decimal('0'),
                }
            _plan_map[iid]['planned_quantity'] += Decimal(str(plan['planned_quantity'] or 0))
            _plan_map[iid]['planned_cif'] += Decimal(str(plan['planned_cif_fc'] or 0))

        # Set source if any plans exist
        if _plan_map:
            _plan_source = 'manual'
        else:
            _plan_map = {}
            _plan_source = ''
        for _item in license_obj.import_license.all():
            _key = ', '.join(_nm) if (_nm := sorted([i.name for i in _item.items.all()])) else (_item.description or '-')
            _avail = float(_item.available_quantity or 0)
            _bal_agg[_key]['qty'] += _avail
            _bal_agg[_key]['total_qty'] += float(_item.quantity or 0)
            _pl = _plan_map.get(_item.id)
            if _pl:
                # This aggregation feeds openpyxl numeric cells and the
                # surrounding balance fields are floats.  Keep the boundary
                # explicit: persisted plans are Decimal, but never mix the
                # two types in Python arithmetic.
                _bal_agg[_key]['plan_qty'] += float(_pl['planned_quantity'])
                _bal_agg[_key]['plan_cif'] += float(_pl['planned_cif'])
            _bal_agg[_key]['sr_ids'].append(_item.serial_number)
            if not _bal_agg[_key]['description']:
                _bal_agg[_key]['description'] = _item.description or _key
            if not _bal_agg[_key]['hs_code']:
                _bal_agg[_key]['hs_code'] = str(_item.hs_code.hs_code if _item.hs_code else '-')
            # Carry per-item licence-condition (AU / 2% / 3% / 5% / 10%)
            # through to the bulk-balance Excel cell.
            if _item.condition_type and not _bal_agg[_key]['condition_type']:
                _bal_agg[_key]['condition_type'] = _item.condition_type
            # Per-condition qty breakdown for E1's Display/Util-qty split.
            _ct = (_item.condition_type or '').strip()
            _bal_agg[_key]['qty_by_cond'][_ct] = _bal_agg[_key]['qty_by_cond'].get(_ct, 0.0) + _avail

        total_license_cif = total_cif + _license_balance

        r = 1
        _today = _date_cls.today()
        INFO_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        INFO_FONT = Font(bold=True, color="FFFFFF", size=9)
        if license_obj.license_expiry_date:
            _days = (license_obj.license_expiry_date - _today).days
            if _days < 0:
                EXPIRY_FILL = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
            elif _days <= 90:
                EXPIRY_FILL = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")
            else:
                EXPIRY_FILL = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        else:
            EXPIRY_FILL = INFO_FILL
        iec_val = license_obj.exporter.iec if license_obj.exporter else '-'
        for col, (label, val) in enumerate([
            ('License No', lic_no),
            ('IEC', iec_val),
            ('License Date', license_date_str),
            ('Expiry Date', license_expiry_str),
            ('Total CIF', f"{total_license_cif:,.2f}"),
            ('Ledger Date', ledger_date_str),
        ], 1):
            c = ws.cell(row=r, column=col, value=f"{label}: {val}")
            c.fill = EXPIRY_FILL if col == 4 else INFO_FILL
            c.font = INFO_FONT
            c.border = THIN_BORDER
            c.alignment = Alignment(horizontal='right' if col == 5 else 'left', vertical='center')
        r += 1

        ws.merge_cells(f'A{r}:H{r}')
        sh = ws[f'A{r}']
        sh.value = 'Summary (BOE & Allotments)'
        sh.fill = HDR_FILL; sh.font = Font(bold=True, color="FFFFFF", size=10)
        sh.alignment = Alignment(horizontal='center', vertical='center')
        r += 1

        SUMM_COLS = ['Item', 'Type', 'Company', 'Reference', 'Qty', 'Rate', 'CIF Value (FC)', 'CIF Value (INR)']
        for col, h in enumerate(SUMM_COLS, 1):
            _hdr(ws, r, col, h)
        r += 1

        for _s, _sd, row_data, is_boe in summary_rows:
            fill = BOE_FILL if is_boe else ALLOT_FILL
            _cell(ws, r, 1, row_data['item'],          fill=fill)
            _cell(ws, r, 2, row_data['type'],          fill=fill)
            _cell(ws, r, 3, row_data['company'],       fill=fill)
            _cell(ws, r, 4, row_data['reference'],     fill=fill)
            _cell(ws, r, 5, row_data['qty'],           fill=fill, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 6, row_data['rate'],          fill=fill, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 7, row_data['cif'],           fill=fill, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 8, row_data.get('cif_inr', 0), fill=fill, align='right', num_fmt='#,##0.00')
            r += 1

        if summary_rows:
            _cell(ws, r, 1, '', fill=TOTAL_FILL); _cell(ws, r, 2, '', fill=TOTAL_FILL)
            _cell(ws, r, 3, '', fill=TOTAL_FILL)
            _cell(ws, r, 4, 'TOTAL', fill=TOTAL_FILL, bold=True, align='right')
            _cell(ws, r, 5, '', fill=TOTAL_FILL); _cell(ws, r, 6, '', fill=TOTAL_FILL)
            _cell(ws, r, 7, total_cif, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 8, total_cif_inr, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            r += 1

        r += 1

        # ── Plan Utilization section (matches PlanTab UI) ───────────────────
        # Shared with the single-licence sheet above and with the
        # "Utilization Planning Summary" sheet — see
        # render_plan_utilization_section.
        from apps.license.services.plan_reporting import plan_map_for_license as _plan_map_fn_bulk
        from apps.license.services.exporters.planning_split_rows import render_plan_utilization_section
        from apps.license.services.plan_utilization import plan_utilization_rows as _plan_utilization_rows_bulk
        _user_plan_map_b = _plan_map_fn_bulk(license_obj.id)
        # Computed ONCE per license and reused by both this sheet's own
        # "Plan Utilization" table AND the "Utilization Planning Summary"
        # sheet's Planning Matrix pivot (`_license_pivot_data`, via
        # `_util_return['groups']` below) — that pivot used to call
        # `plan_utilization_rows()` a second, independent time per license,
        # doubling the whole plan_status_for/group_ids_of query cost for
        # every exported license.
        _groups_b = _plan_utilization_rows_bulk(license_obj, plan_map=_user_plan_map_b)

        _plan_totals_b = {}
        r = render_plan_utilization_section(
            ws, r, license_obj, _license_balance,
            plan_map=_user_plan_map_b, totals_out=_plan_totals_b, groups=_groups_b,
        )

        # _util_return — feeds the "Utilization Planning Summary" sheet. Carries
        # the already-fetched `license_obj`/`plan_map`/`groups` so that sheet
        # can build its pivot for the same license without re-querying
        # plan_map_for_license or re-running plan_utilization_rows.
        _exporter_name = license_obj.exporter.name if license_obj.exporter else ''
        _util_return = {
            'lic_no': lic_no,
            'license_obj': license_obj,
            'balance_cif': _license_balance,
            'total_license_cif': total_license_cif,
            'license_date': license_obj.license_date,
            'license_expiry_date': license_obj.license_expiry_date,
            'exporter_name': _exporter_name,
            'sheet_name': sheet_name,
            'plan_map': _user_plan_map_b,
            'plan_totals': _plan_totals_b,
            'groups': _groups_b,
        }

        ws.column_dimensions['A'].width = 38  # Item Description
        ws.column_dimensions['B'].width = 14  # HS Code
        ws.column_dimensions['C'].width = 14  # S.No
        ws.column_dimensions['D'].width = 14  # Status
        ws.column_dimensions['E'].width = 14  # Available Qty
        ws.column_dimensions['F'].width = 14  # Planned Qty
        ws.column_dimensions['G'].width = 14  # Remaining Qty
        ws.column_dimensions['H'].width = 16  # Planned CIF
        ws.column_dimensions['I'].width = 16  # Remaining CIF
        ws.column_dimensions['J'].width = 12
        ws.freeze_panes = 'A2'
        return _util_return

    def _norm_sort_key(lic):
        norms = list(lic.export_license.values_list('norm_class__norm_class', flat=True))
        norm_str = ', '.join(sorted(str(n) for n in norms if n)) or 'ZZZ'
        # Group order: E1 first, E5 second, rest alphabetically
        if any('E1' in str(n) and 'E126' not in str(n) and 'E132' not in str(n) for n in norms if n):
            return ('0_E1', norm_str)
        if any(str(n).strip() == 'E5' for n in norms if n):
            return ('1_E5', norm_str)
        return ('2_' + norm_str, norm_str)

    sorted_licenses = sorted(licenses, key=_norm_sort_key)

    # Batch-compute every exported license's final balance (== what
    # `license_obj.get_balance_cif` / `LicenseBalanceCalculator.calculate_balance`
    # would return) ONCE here, in 4 queries total, instead of `_write_license_sheet`
    # triggering `get_balance_cif` per license (4 queries: credit+debit+
    # allotment+trade). `_write_license_sheet` reads this dict via closure
    # instead of the model property. Plans are read directly from persisted
    # LicenseItemPlan (no planner calls in read path). Nothing outside this
    # bulk export is touched — `get_balance_cif` itself is unchanged.
    from apps.license.services.balance_calculator import LicenseBalanceCalculator as _LBC_bulk
    _bulk_lic_ids = [lic.id for lic in sorted_licenses]
    _balance_by_license = _LBC_bulk.calculate_balance_for_licenses(_bulk_lic_ids)

    _util_summaries = []
    for license_obj in sorted_licenses:
        _util_summaries.append(_write_license_sheet(wb, license_obj))

    # ── Create Utilization Planning Summary as first sheet ─────────────────
    # Norm-grouped planning MATRIX (third design of this sheet): one section
    # per distinct SION norm actually present among the exported licenses —
    # a Planning Matrix (one row per license, pivoted by Planning Item Name
    # into Available/Planned Qty/Planned CIF column groups), a Norm Total
    # row, and a Planning Item Summary (the same per-item totals,
    # transposed). After every norm section: a Grand Summary by Norm and a
    # Grand Total. No norm-specific or item-name-specific branching —
    # whatever norms/planning items exist in the data become
    # sections/columns automatically.
    #
    # Data source is exclusively `plan_utilization_rows()` (the same
    # function `render_plan_utilization_section()` calls for every
    # per-license sheet) plus `rows_for_splits()` for the visible-split
    # filter — no new planning calculation, no new split query.
    #
    # Two attribution rules that must NOT be conflated (see the docstrings
    # below for the derivation each one mirrors):
    #   - Planning-item pivot columns (matrix / Norm Total / Planning Item
    #     Summary): planned qty/CIF are split-exclusive (each visible split
    #     counted under exactly one item-name column, 'Unassigned' when
    #     untagged); available qty is the group's FULL available_quantity
    #     attributed to EVERY distinct item-name column with a visible split
    #     in that group — an intentional double count across columns,
    #     matching `item_pivot_report.py`'s `_build_license_row` convention
    #     (`for item in import_item.items.all(): item_quantities[item.id]
    #     ['available_quantity'] += ...` — a shared import item's
    #     availability is added under every attached item name, not
    #     divided).
    #   - Grand Summary by Norm / Grand Total: available/planned/CIF are
    #     GROUP-level totals (never derived from the pivot columns, which
    #     would inherit the available-qty double count above) — the exact
    #     same derivation `render_plan_utilization_section()` uses for its
    #     `totals_out` (Σ available_quantity across every group; Σ
    #     original_quantity/original_cif_fc across PLANNED groups only).
    from apps.license.services.plan_utilization import plan_utilization_rows
    from apps.license.services.exporters.planning_split_rows import rows_for_splits
    from apps.license.models import LicenseExportItemModel
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    from openpyxl.utils import get_column_letter

    _UNASSIGNED = 'Unassigned'

    # One batched query for every exported license's PRIMARY export norm
    # (mirrors norm_plan.detect_norm's own `export_license.first()` — i.e.
    # the lowest-pk export item — without querying per license in a loop).
    _lic_ids = _bulk_lic_ids
    _first_norm_by_license: dict = {}
    for _lic_id, _norm_code in (
        LicenseExportItemModel.objects
        .filter(license_id__in=_lic_ids)
        .order_by('license_id', 'pk')
        .values_list('license_id', 'norm_class__norm_class')
    ):
        _first_norm_by_license.setdefault(_lic_id, _norm_code)

    # One batched query each for Total CIF / Debited CIF across every
    # exported license, instead of `LicenseBalanceCalculator.calculate_credit`/
    # `calculate_boe_debit_total` being called once per license (2 queries x
    # 214 licenses in production) inside the per-license loop below. Raw,
    # unconditional BOE debit — matches the Balance CIF formula exactly
    # (`calculate_balance`), not the allocation-netted `calculate_debit`.
    _credit_by_license = LicenseBalanceCalculator.calculate_credit_for_licenses(_lic_ids)
    _debit_by_license = LicenseBalanceCalculator.calculate_boe_debit_total_for_licenses(_lic_ids)

    # Bucket licenses by norm, preserving the order they were exported in
    # (== `sorted_licenses` order, already E1-first/E5-second/alpha-rest).
    _licenses_by_norm: dict = {}
    _norm_order: list = []
    for _row in _util_summaries:
        _norm_code = (_first_norm_by_license.get(_row['license_obj'].id) or '').strip()
        _norm_label = _norm_code or 'Unclassified'
        if _norm_label not in _licenses_by_norm:
            _licenses_by_norm[_norm_label] = []
            _norm_order.append(_norm_label)
        _licenses_by_norm[_norm_label].append(_row)

    def _license_pivot_data(_lic_row):
        """One license's pivot data: `{item_name: {available, planned_qty,
        planned_cif}}` (floats, split-exclusive planned figures / doubled-up
        available per the module docstring above) plus this license's
        GROUP-level totals (`available_quantity`, `planned_quantity`,
        `planned_cif`) — derived exactly like
        `render_plan_utilization_section`'s own `_g_avail`/`_g_planned_qty`/
        `_g_planned_cif` (see that function for the proof these equal Σ of
        the group's unioned splits when the group has a plan).
        """
        _lic_obj = _lic_row['license_obj']
        # Reuse the SAME groups `_write_license_sheet` already computed for
        # this license (see `_util_return['groups']`) instead of calling
        # `plan_utilization_rows()` a second time — that used to double the
        # whole plan_status_for/group_ids_of query cost for every license.
        _groups = _lic_row.get('groups')
        if _groups is None:  # pragma: no cover - defensive; always set today
            _groups = plan_utilization_rows(_lic_obj, plan_map=_lic_row.get('plan_map'))
        _item_data: dict = {}
        _totals = {'available_quantity': 0.0, 'planned_quantity': 0.0, 'planned_cif': 0.0}
        for _grp in _groups:
            _avail = float(_grp.get('available_quantity') or 0)
            _totals['available_quantity'] += _avail
            _has_plan = bool(_grp.get('has_plan'))
            _totals['planned_quantity'] += float(_grp['original_quantity']) if _has_plan else 0.0
            _totals['planned_cif'] += float(_grp['original_cif_fc']) if _has_plan else 0.0

            _distinct_names_in_group = set()
            for _sp in rows_for_splits(_grp.get('splits') or []):
                _name = (_sp.get('item_name') or '').strip() or _UNASSIGNED
                _distinct_names_in_group.add(_name)
                _bucket = _item_data.setdefault(
                    _name, {'available': 0.0, 'planned_qty': 0.0, 'planned_cif': 0.0},
                )
                _bucket['planned_qty'] += float(_sp.get('planned_quantity') or 0)
                _bucket['planned_cif'] += float(_sp.get('planned_cif_fc') or 0)
            for _name in _distinct_names_in_group:
                _item_data.setdefault(
                    _name, {'available': 0.0, 'planned_qty': 0.0, 'planned_cif': 0.0},
                )['available'] += _avail
        return _item_data, _totals

    _sw = wb.create_sheet(title="Utilization Planning Summary")
    wb.move_sheet(_sw, offset=-(len(wb.worksheets) - 1))

    ITEM_HDR_FILL = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
    ITEM_HDR_FONT = Font(bold=True, color="FFFFFF", size=9)
    NORM_BANNER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")

    # ── Expiry traffic-light — computed once at export time (no conditional-
    # formatting formulas, so colors stay correct even with recalc disabled).
    # Applied only to a license's own Planning Matrix row (see the per-license
    # loop below) — never to section banners, header rows, Norm Total,
    # Planning Item Summary, Grand Summary by Norm, or Grand Total.
    EXPIRED_FILL      = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
    EXPIRED_FONT      = Font(bold=True, color="FFFFFF", size=9)
    EXPIRING_30_FILL  = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    EXPIRING_30_FONT  = Font(bold=True, color="000000", size=9)
    EXPIRING_60_FILL  = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    EXPIRING_60_FONT  = Font(bold=False, color="000000", size=9)
    from datetime import date as _expiry_date_cls
    _expiry_today = _expiry_date_cls.today()

    def _expiry_highlight(expiry_date):
        """(fill, font) override for a license row, or (None, None) when the
        license isn't within the expiry window — callers keep the normal
        alternating-row fill/font in that case."""
        if not expiry_date:
            return None, None
        days = (expiry_date - _expiry_today).days
        if days < 0:
            return EXPIRED_FILL, EXPIRED_FONT
        if days <= 30:
            return EXPIRING_30_FILL, EXPIRING_30_FONT
        if days <= 60:
            return EXPIRING_60_FILL, EXPIRING_60_FONT
        return None, None

    _sr = 1
    _max_matrix_cols = 5  # widened as sections are laid out; Grand Summary needs at least 5.

    # One row per norm: (norm_label, license_count, available, planned_qty, planned_cif) —
    # GROUP-level totals only, per the module docstring above.
    _grand_summary_by_norm: list = []

    for _norm_label in _norm_order:
        _norm_rows = _licenses_by_norm[_norm_label]

        # Pass 1: this norm's per-license pivot data/totals + the set of
        # distinct planning-item names present anywhere in this norm.
        _per_license = []
        _item_names_in_norm: set = set()
        for _row in _norm_rows:
            _item_data, _totals = _license_pivot_data(_row)
            _per_license.append((_row, _item_data, _totals))
            _item_names_in_norm.update(_item_data.keys())

        _ordered_item_names = sorted(
            (n for n in _item_names_in_norm if n != _UNASSIGNED), key=lambda s: s.casefold(),
        )
        if _UNASSIGNED in _item_names_in_norm:
            _ordered_item_names.append(_UNASSIGNED)

        _n_cols = 9 + 3 * len(_ordered_item_names)
        _max_matrix_cols = max(_max_matrix_cols, _n_cols)

        # ── 1. Section header ────────────────────────────────────────────
        _sw.merge_cells(start_row=_sr, start_column=1, end_row=_sr, end_column=_n_cols)
        _nh = _sw.cell(row=_sr, column=1, value=f"SION NORM : {_norm_label}")
        _nh.fill = NORM_BANNER_FILL
        _nh.font = Font(bold=True, color="FFFFFF", size=12)
        _nh.alignment = Alignment(horizontal='center', vertical='center')
        _sr += 1

        # ── 2. Planning Matrix — 2-row header + one row per license ─────
        _hdr_row1, _hdr_row2 = _sr, _sr + 1
        for _col, _label in enumerate([
            'License No', 'Issue Date', 'Expiry Date', 'Exporter', 'SION Norm',
            'Total CIF ($)', 'Debited CIF ($)', 'Allotted CIF ($)', 'Balance CIF ($)',
        ], 1):
            _sw.merge_cells(start_row=_hdr_row1, start_column=_col, end_row=_hdr_row2, end_column=_col)
            _hdr(_sw, _hdr_row1, _col, _label)
        for _i, _name in enumerate(_ordered_item_names):
            _base_col = 10 + _i * 3
            _sw.merge_cells(start_row=_hdr_row1, start_column=_base_col, end_row=_hdr_row1, end_column=_base_col + 2)
            _ic = _sw.cell(row=_hdr_row1, column=_base_col, value=_name)
            _ic.fill = ITEM_HDR_FILL; _ic.font = ITEM_HDR_FONT
            _ic.border = THIN_BORDER
            _ic.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            for _sub_col, _sub_label in enumerate(['Available Qty', 'Planned Qty', 'Planned CIF ($)']):
                _hdr(_sw, _hdr_row2, _base_col + _sub_col, _sub_label)
        _sr += 2

        _norm_item_totals = {
            _n: {'available': 0.0, 'planned_qty': 0.0, 'planned_cif': 0.0} for _n in _ordered_item_names
        }
        _norm_totals = {'available_quantity': 0.0, 'planned_quantity': 0.0, 'planned_cif': 0.0}
        _norm_cif_totals = {'total_cif': 0.0, 'debited_cif': 0.0, 'allotted_cif': 0.0, 'balance_cif': 0.0}

        for _idx, (_row, _item_data, _totals) in enumerate(_per_license):
            _rf = None if _idx % 2 == 0 else ALT_FILL
            _ld = _row.get('license_date')
            _ed = _row.get('license_expiry_date')
            _lic_obj = _row['license_obj']

            # Total CIF / Debited CIF — sourced directly from the centralized
            # LicenseBalanceCalculator (the same single source of truth
            # `get_balance_cif`/`calculate_balance` themselves compose from),
            # via the batched `_credit_by_license`/`_debit_by_license` maps
            # computed once above — same numbers `calculate_credit`/
            # `calculate_debit` would give per license (Coalesce'd to 0 when
            # a license has none), just without a query per license.
            # Deliberately NOT the ad-hoc `total_cif`/`total_license_cif`
            # computed earlier in `_write_license_sheet` from the raw
            # BOE/allotment summary-rows loop — that older calculation
            # doesn't exclude BOEs linked to trades and ignores
            # `calculate_trade()`.
            _total_cif = float(_credit_by_license.get(_lic_obj.id, 0))
            _debited_cif = float(_debit_by_license.get(_lic_obj.id, 0))
            # Allotted CIF — per product's explicit instruction, this is the
            # Plan Utilization "Planned CIF" figure (Σ this license's group
            # totals, same number feeding Grand Summary by Norm), NOT
            # LicenseBalanceCalculator.calculate_allotment()'s real-allotment
            # figure. The two can legitimately differ when a plan isn't
            # fully executed as real allotments yet.
            _allotted_cif = _totals['planned_cif']
            # Balance CIF — reuse the already-computed/cached value from
            # `_write_license_sheet` (== `license_obj.get_balance_cif`).
            # NOT recomputed as Total − Debited − Allotted: `get_balance_cif`
            # nets against real allotment transactions + trade CIF, neither
            # of which the other three columns expose, so the four columns
            # will not always reconcile arithmetically — that's expected.
            _balance_cif = _row['balance_cif']

            _cell(_sw, _sr, 1, _row['lic_no'], fill=_rf, bold=True)
            _cell(_sw, _sr, 2, _ld.strftime('%d-%m-%Y') if _ld else '-', fill=_rf, align='center')
            _cell(_sw, _sr, 3, _ed.strftime('%d-%m-%Y') if _ed else '-', fill=_rf, align='center')
            _cell(_sw, _sr, 4, _row.get('exporter_name') or '-', fill=_rf)
            _cell(_sw, _sr, 5, _norm_label, fill=_rf)
            _cell(_sw, _sr, 6, _total_cif, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(_sw, _sr, 7, _debited_cif, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(_sw, _sr, 8, _allotted_cif, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(_sw, _sr, 9, _balance_cif, fill=_rf, align='right', num_fmt='#,##0.00')
            _norm_cif_totals['total_cif'] += _total_cif
            _norm_cif_totals['debited_cif'] += _debited_cif
            _norm_cif_totals['allotted_cif'] += _allotted_cif
            _norm_cif_totals['balance_cif'] += _balance_cif
            for _i, _name in enumerate(_ordered_item_names):
                _base_col = 10 + _i * 3
                _vals = _item_data.get(_name) or {'available': 0.0, 'planned_qty': 0.0, 'planned_cif': 0.0}
                _cell(_sw, _sr, _base_col, _vals['available'], fill=_rf, align='right', num_fmt='#,##0.000')
                _cell(_sw, _sr, _base_col + 1, _vals['planned_qty'], fill=_rf, align='right', num_fmt='#,##0.000')
                _cell(_sw, _sr, _base_col + 2, _vals['planned_cif'], fill=_rf, align='right', num_fmt='#,##0.00')
                _norm_item_totals[_name]['available'] += _vals['available']
                _norm_item_totals[_name]['planned_qty'] += _vals['planned_qty']
                _norm_item_totals[_name]['planned_cif'] += _vals['planned_cif']
            for _k in _norm_totals:
                _norm_totals[_k] += _totals.get(_k, 0.0)

            # Expiry traffic-light — overrides this row's fill/font across
            # every column (License No through the last item's Planned CIF)
            # when the license is expired or expiring soon; otherwise the
            # normal alternating-row fill/font above is left untouched.
            _hl_fill, _hl_font = _expiry_highlight(_ed)
            if _hl_fill is not None:
                for _hc in range(1, _n_cols + 1):
                    _hcell = _sw.cell(row=_sr, column=_hc)
                    _hcell.fill = _hl_fill
                    _hcell.font = _hl_font

            _sr += 1

        # ── 3. Norm Total row ─────────────────────────────────────────────
        for _ci in range(1, _n_cols + 1):
            _sw.cell(row=_sr, column=_ci).fill = TOTAL_FILL
            _sw.cell(row=_sr, column=_ci).border = THIN_BORDER
        _cell(_sw, _sr, 1, 'NORM TOTAL', fill=TOTAL_FILL, bold=True)
        _cell(_sw, _sr, 2, '', fill=TOTAL_FILL); _cell(_sw, _sr, 3, '', fill=TOTAL_FILL); _cell(_sw, _sr, 4, '', fill=TOTAL_FILL)
        _cell(_sw, _sr, 5, '', fill=TOTAL_FILL)
        _cell(_sw, _sr, 6, _norm_cif_totals['total_cif'], fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _cell(_sw, _sr, 7, _norm_cif_totals['debited_cif'], fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _cell(_sw, _sr, 8, _norm_cif_totals['allotted_cif'], fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _cell(_sw, _sr, 9, _norm_cif_totals['balance_cif'], fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        for _i, _name in enumerate(_ordered_item_names):
            _base_col = 10 + _i * 3
            _t = _norm_item_totals[_name]
            _cell(_sw, _sr, _base_col, _t['available'], fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.000')
            _cell(_sw, _sr, _base_col + 1, _t['planned_qty'], fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.000')
            _cell(_sw, _sr, _base_col + 2, _t['planned_cif'], fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _sr += 2

        # ── 4. Planning Item Summary — same numbers, transposed ─────────
        _sw.merge_cells(start_row=_sr, start_column=1, end_row=_sr, end_column=4)
        _psh = _sw.cell(row=_sr, column=1, value='PLANNING ITEM SUMMARY')
        _psh.fill = HDR_FILL; _psh.font = Font(bold=True, color="FFFFFF", size=10)
        _psh.alignment = Alignment(horizontal='center', vertical='center')
        _sr += 1
        for _ci, _ch in enumerate(['Planning Item', 'Available Qty', 'Planned Qty', 'Planned CIF ($)'], 1):
            _hdr(_sw, _sr, _ci, _ch)
        _sr += 1
        for _i, _name in enumerate(_ordered_item_names):
            _rf = None if _i % 2 == 0 else ALT_FILL
            _t = _norm_item_totals[_name]
            _cell(_sw, _sr, 1, _name, fill=_rf, bold=True)
            _cell(_sw, _sr, 2, _t['available'], fill=_rf, align='right', num_fmt='#,##0.000')
            _cell(_sw, _sr, 3, _t['planned_qty'], fill=_rf, align='right', num_fmt='#,##0.000')
            _cell(_sw, _sr, 4, _t['planned_cif'], fill=_rf, align='right', num_fmt='#,##0.00')
            _sr += 1
        _sr += 2

        _grand_summary_by_norm.append((
            _norm_label, len(_norm_rows),
            _norm_totals['available_quantity'], _norm_totals['planned_quantity'], _norm_totals['planned_cif'],
        ))

    # ── 5. Grand Summary by Norm ──────────────────────────────────────────
    _sw.merge_cells(start_row=_sr, start_column=1, end_row=_sr, end_column=5)
    _gsh = _sw.cell(row=_sr, column=1, value='GRAND SUMMARY BY NORM')
    _gsh.fill = HDR_FILL; _gsh.font = Font(bold=True, color="FFFFFF", size=11)
    _gsh.alignment = Alignment(horizontal='center', vertical='center')
    _sr += 1
    for _ci, _ch in enumerate(['SION Norm', 'Licenses', 'Available Qty', 'Planned Qty', 'Planned CIF ($)'], 1):
        _hdr(_sw, _sr, _ci, _ch)
    _sr += 1

    _grand_total_licenses = 0
    _grand_total_available = 0.0
    _grand_total_planned_qty = 0.0
    _grand_total_planned_cif = 0.0
    for _i, (_norm_label, _lic_count, _avail, _pqty, _pcif) in enumerate(_grand_summary_by_norm):
        _rf = None if _i % 2 == 0 else ALT_FILL
        _cell(_sw, _sr, 1, _norm_label, fill=_rf, bold=True)
        _cell(_sw, _sr, 2, _lic_count, fill=_rf, align='center')
        _cell(_sw, _sr, 3, _avail, fill=_rf, align='right', num_fmt='#,##0.000')
        _cell(_sw, _sr, 4, _pqty, fill=_rf, align='right', num_fmt='#,##0.000')
        _cell(_sw, _sr, 5, _pcif, fill=_rf, align='right', num_fmt='#,##0.00')
        _grand_total_licenses += _lic_count
        _grand_total_available += _avail
        _grand_total_planned_qty += _pqty
        _grand_total_planned_cif += _pcif
        _sr += 1
    _sr += 1

    # ── 6. Grand Total ────────────────────────────────────────────────────
    for _ci in range(1, 6):
        _sw.cell(row=_sr, column=_ci).fill = TOTAL_FILL
        _sw.cell(row=_sr, column=_ci).border = THIN_BORDER
    _cell(_sw, _sr, 1, 'GRAND TOTAL', fill=TOTAL_FILL, bold=True)
    _cell(_sw, _sr, 2, _grand_total_licenses, fill=TOTAL_FILL, bold=True, align='center')
    _cell(_sw, _sr, 3, _grand_total_available, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.000')
    _cell(_sw, _sr, 4, _grand_total_planned_qty, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.000')
    _cell(_sw, _sr, 5, _grand_total_planned_cif, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')

    # ── Column widths ──────────────────────────────────────────────────────
    _sw.column_dimensions['A'].width = 22  # License No
    _sw.column_dimensions['B'].width = 14  # Issue Date
    _sw.column_dimensions['C'].width = 14  # Expiry Date
    _sw.column_dimensions['D'].width = 24  # Exporter
    _sw.column_dimensions['E'].width = 14  # SION Norm
    _sw.column_dimensions['F'].width = 16  # Total CIF ($)
    _sw.column_dimensions['G'].width = 16  # Debited CIF ($)
    _sw.column_dimensions['H'].width = 16  # Allotted CIF ($)
    _sw.column_dimensions['I'].width = 16  # Balance CIF ($)
    for _col in range(10, _max_matrix_cols + 1):
        _sw.column_dimensions[get_column_letter(_col)].width = 14

    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True

    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="bulk_license_summary.xlsx"'
    return response
