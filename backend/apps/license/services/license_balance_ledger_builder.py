"""
LicenseBalanceLedgerBuilder — the single source of truth for one licence's
Financial Ledger, Customs Ledger relationships (Invoice<->BOE, BOE<->Allotment),
and reconciliation summary.

This module does ONLY calculation/query work and returns plain Python data
(dicts/Decimals/dates) — no ReportLab, no openpyxl, no DRF serialization, no
React/JSON-specific shaping. The three consumers format this data three
different ways:
  - `apps/license/services/exporters/license_balance_pdf.py` (PDF)
  - `apps/license/services/exporters/license_balance_excel.py` (Excel)
  - `apps/license/views/license_balance_ledger.py` (JSON API for the
    Licence Balance & Financial Reconciliation Workspace UI)

Every number here is read from the SAME annotated querysets
`LicenseBalanceCalculator` itself sums (`get_debit_rows`/`get_allotment_rows`/
`get_trade_rows`/`calculate_balance`) — this builder is a row-level breakdown
of that authoritative data, never an independent recomputation, so it cannot
silently drift from the Balance Engine.
"""
from __future__ import annotations

import re
from datetime import date as _date
from decimal import Decimal

DEC_0 = Decimal("0.00")
TOLERANCE = Decimal("10.00")


# ---------------------------------------------------------------------------
# Small shared formatting/lookup helpers (also used by the PDF exporter)
# ---------------------------------------------------------------------------

def split_invoice_numbers(raw):
    """Split a free-text invoice field into a clean, ordered, deduped list.

    Only splits on comma/semicolon/newline — NOT '/', because this system's
    own generated invoice numbers (`LicenseTrade.next_invoice_number`) are
    themselves in `PREFIX/FY/NNNN` form (e.g. "LGL/2026-27/0016"); splitting
    on '/' would shred a single invoice number into three fragments.
    """
    if not raw:
        return []
    seen = []
    for part in re.split(r'[,\n;]+', str(raw)):
        part = part.strip()
        if part and part not in seen:
            seen.append(part)
    return seen


def item_display_name(license_import_item, fallback=''):
    """Same "join item names, else description" convention used throughout
    the balance PDF/Excel exporters."""
    if license_import_item is None:
        return fallback or '-'
    if license_import_item.items.exists():
        return ', '.join(i.name for i in license_import_item.items.all())
    return license_import_item.description or fallback or '-'


def boe_invoice_allocation_map(license_obj):
    """
    {row_details_id: [invoice_number, ...]} of invoice numbers reconciled to
    each BOE debit row via active `InvoiceBOEAllocation` matches. One query
    for the whole license, to stay cheap on licenses with hundreds of BOEs.
    """
    from apps.reconciliation.models import InvoiceBOEAllocation

    alloc_map = {}
    rows = InvoiceBOEAllocation.objects.filter(
        row_details__sr_number__license=license_obj,
        status=InvoiceBOEAllocation.STATUS_ACTIVE,
        is_current=True,
    ).values_list('row_details_id', 'trade_line__trade__invoice_number')
    for row_details_id, invoice_number in rows:
        if invoice_number:
            alloc_map.setdefault(row_details_id, []).append(invoice_number)
    return alloc_map


def boe_external_invoice_map(license_obj):
    """{row_details_id: [invoice_number, ...]} of ACTIVE, current
    `ExternalInvoiceLink` invoice numbers per BOE debit row."""
    from apps.reconciliation.models import ExternalInvoiceLink

    ext_map = {}
    rows = ExternalInvoiceLink.objects.filter(
        row_details__sr_number__license=license_obj,
        status=ExternalInvoiceLink.STATUS_ACTIVE,
        is_current=True,
    ).values_list('row_details_id', 'invoice_number')
    for row_details_id, invoice_number in rows:
        ext_map.setdefault(row_details_id, []).append(invoice_number)
    return ext_map


def _dedupe(values):
    seen = []
    for v in values:
        if v and v not in seen:
            seen.append(v)
    return seen


def build_invoice_allocation_groups(license_obj):
    """
    One entry per SALE `LicenseTradeLine` with >=1 ACTIVE, current
    `InvoiceBOEAllocation` — every BOE allocated to that invoice combined
    into a single group, for the Financial Ledger's consolidated "BOE
    Allocation" row (see `LicenseBalanceLedgerBuilder.build_financial_ledger`).

    Uses each allocation's OWN `allocated_qty`/`allocated_cif_fc`/
    `allocated_cif_inr` — NOT the underlying BOE row's raw totals — so a
    BOE that is only PARTIALLY allocated to this invoice contributes only
    its allocated slice to the group; the unallocated remainder of that
    same BOE still shows up as its own ordinary "BOE" ledger row (see
    `build_financial_ledger`), never lost, never double-counted.
    """
    from apps.reconciliation.models import InvoiceBOEAllocation

    groups_by_trade_line = {}
    allocations = (
        InvoiceBOEAllocation.objects.filter(
            trade_line__sr_number__license=license_obj,
            status=InvoiceBOEAllocation.STATUS_ACTIVE,
            is_current=True,
        )
        .select_related(
            'trade_line__trade__to_company', 'trade_line__sr_number',
            'row_details__bill_of_entry__company', 'row_details__sr_number',
        )
        .prefetch_related('trade_line__sr_number__items', 'row_details__sr_number__items')
        .order_by('row_details__bill_of_entry__bill_of_entry_date', 'row_details__bill_of_entry__bill_of_entry_number')
    )
    for alloc in allocations:
        group = groups_by_trade_line.setdefault(alloc.trade_line_id, {
            'trade_line': alloc.trade_line,
            'allocations': [],
            'boe_numbers': [],
            'boe_dates': [],
            'companies': [],
            'item_names': [],
            'total_qty': DEC_0,
            'total_cif_fc': DEC_0,
            'total_cif_inr': DEC_0,
        })
        boe = alloc.row_details.bill_of_entry
        group['allocations'].append(alloc)
        group['boe_numbers'].append(boe.bill_of_entry_number if boe else '-')
        group['boe_dates'].append(boe.bill_of_entry_date if boe else None)
        if boe and boe.company:
            group['companies'].append(boe.company.name)
        group['item_names'].append(item_display_name(alloc.row_details.sr_number))
        group['total_qty'] += alloc.allocated_qty
        group['total_cif_fc'] += alloc.allocated_cif_fc
        group['total_cif_inr'] += alloc.allocated_cif_inr

    result = []
    for group in groups_by_trade_line.values():
        dated = [d for d in group['boe_dates'] if d]
        group['companies'] = _dedupe(group['companies'])
        group['item_names'] = _dedupe(group['item_names'])
        group['earliest_boe_date'] = min(dated) if dated else None
        result.append(group)
    return result


def boe_row_invoice_numbers(row_details, alloc_map, ext_map=None):
    """Union of the BOE's own free-text invoice(s), any invoice numbers
    matched via the reconciliation panel, and any external invoice marks."""
    boe = row_details.bill_of_entry
    numbers = split_invoice_numbers(boe.invoice_no if boe else None)
    for invoice_number in alloc_map.get(row_details.id, []):
        for piece in split_invoice_numbers(invoice_number):
            if piece not in numbers:
                numbers.append(piece)
    for invoice_number in (ext_map or {}).get(row_details.id, []):
        label = f"{invoice_number} (OTHER)"
        if label not in numbers:
            numbers.append(label)
    return numbers


class LicenseBalanceLedgerBuilder:
    """One entry point: `LicenseBalanceLedgerBuilder.build(license_obj)`."""

    # ------------------------------------------------------------------
    # Financial Ledger — bank-statement rows + summary
    # ------------------------------------------------------------------

    @staticmethod
    def build_financial_ledger(license_obj, alloc_map=None, ext_map=None):
        """
        Returns `(rows, summary)`.

        `rows` is a list of plain dicts (see keys below) in ledger order:
        Opening Balance -> [BOE debits AND consolidated Invoice/BOE
        Allocation transactions, merged and sorted by date] -> Active
        Allotments -> Licence Trade (Sold) debits (unallocated remainder
        only) -> Current Balance.

        Multiple BOEs allocated to the SAME invoice are combined into ONE
        "BOE Allocation" row (see `build_invoice_allocation_groups`) instead
        of one row per BOE — the Financial Ledger represents the
        reconciled financial transaction against the invoice, not the raw
        Customs data (the Customs Ledger elsewhere in the report still
        shows every individual BOE, unchanged). A BOE's UNALLOCATED
        remainder (if only partially matched) still appears as its own
        ordinary "BOE" row so no CIF is ever lost or double-counted — see
        the module-level proof in `build_invoice_allocation_groups`'s
        docstring: allocated + remaining == the BOE's/invoice's full
        amount, always.

        `summary` carries the numbers needed by the Financial Summary and
        the Final Reconciliation Summary.
        """
        from apps.license.services.balance_calculator import LicenseBalanceCalculator, quantize_2dp
        from apps.reconciliation.services.allocation_service import remaining_for_trade_line

        if alloc_map is None:
            alloc_map = boe_invoice_allocation_map(license_obj)
        if ext_map is None:
            ext_map = boe_external_invoice_map(license_obj)

        opening_balance = license_obj.opening_balance  # = calculate_credit(): total export CIF
        rows = []
        sr = 1
        running = opening_balance

        rows.append({
            'sr': sr, 'date': license_obj.license_date, 'type': 'Opening Balance',
            'document_number': license_obj.license_number or '-',
            'boe_number': None, 'boe_date': None, 'company': None, 'item_name': None,
            'invoice_numbers': [], 'qty': None, 'cif_usd': None, 'cif_inr': None,
            'credit': opening_balance, 'debit': DEC_0, 'running_balance': running,
            'remarks': 'Licence Issued', 'row_kind': 'opening',
        })
        sr += 1

        # ---- BOE debits (unallocated / partially-allocated remainder only) ----
        # A BOE with an active allocation contributes ONLY its allocated
        # slice to `contributed` (see get_debit_rows/calculate_debit) — once
        # fully allocated, contributed == 0 and the row carries no further
        # debit, so it is skipped here entirely (its full amount is
        # represented by the consolidated "BOE Allocation" row below).
        boe_rows = (
            LicenseBalanceCalculator.get_debit_rows(license_obj)
            .select_related('bill_of_entry__company', 'sr_number')
            .prefetch_related('sr_number__items')
        )
        total_boe_debit = DEC_0
        dated_entries = []  # (sort_date, sort_tiebreak, row_dict_without_sr_or_running)
        for row in boe_rows:
            boe = row.bill_of_entry
            debit = row.contributed
            if debit <= DEC_0:
                continue
            total_boe_debit += debit

            invoices = boe_row_invoice_numbers(row, alloc_map, ext_map)
            remarks = 'Matched Invoice(s)' if invoices else '-'
            if debit < row.cif_fc:
                note = f"Reconciled ${row.cif_fc - debit:,.2f} via Trade"
                remarks = f"{remarks} | {note}" if remarks != '-' else note

            boe_date = boe.bill_of_entry_date if boe else None
            dated_entries.append((boe_date or _date.max, boe.bill_of_entry_number if boe else '', {
                'type': 'BOE',
                'document_number': boe.bill_of_entry_number if boe else '-',
                'boe_number': boe.bill_of_entry_number if boe else '-',
                'boe_date': boe_date,
                'company': boe.company.name if (boe and boe.company) else '-',
                'item_name': item_display_name(row.sr_number, fallback=(boe.product_name if boe else '')),
                'invoice_numbers': invoices,
                'qty': row.qty, 'cif_usd': row.cif_fc, 'cif_inr': row.cif_inr,
                'credit': DEC_0, 'debit': debit,
                'remarks': remarks, 'row_kind': 'boe',
                'row_details_id': row.id,
            }))

        # ---- Consolidated Invoice/BOE Allocation transactions ----
        total_invoice_allocation_debit = DEC_0
        for group in build_invoice_allocation_groups(license_obj):
            trade_line = group['trade_line']
            trade = trade_line.trade
            debit = group['total_cif_fc']
            total_invoice_allocation_debit += debit

            boe_count = len(group['boe_numbers'])
            remarks = 'Matched Invoice(s)' if boe_count == 1 else f"Invoice allocated to {boe_count} BOEs"

            # Child rows — one per underlying BOE allocation, informational
            # only. They explain HOW the parent's debit is made up; they
            # never carry their own credit/debit/running_balance (the
            # parent already IS the accounting impact — showing it again on
            # each child would double-count visually, even though it can't
            # double-count arithmetically since children are never summed).
            children = []
            for alloc in group['allocations']:
                boe = alloc.row_details.bill_of_entry
                fully_matched = alloc.allocated_cif_fc >= alloc.row_details.cif_fc
                children.append({
                    'type': 'BOE', 'row_kind': 'boe_child',
                    'boe_number': boe.bill_of_entry_number if boe else '-',
                    'boe_date': boe.bill_of_entry_date if boe else None,
                    'company': boe.company.name if (boe and boe.company) else '-',
                    'item_name': item_display_name(alloc.row_details.sr_number),
                    'invoice_numbers': split_invoice_numbers(trade.invoice_number if trade else None),
                    'qty': alloc.allocated_qty, 'cif_usd': alloc.allocated_cif_fc, 'cif_inr': alloc.allocated_cif_inr,
                    'status': 'Matched' if fully_matched else 'Partially Matched',
                    'remarks': 'Fully allocated' if fully_matched else 'Partially allocated — remainder unmatched',
                    'row_details_id': alloc.row_details_id, 'allocation_id': alloc.id,
                    # Blank on purpose — the parent already contains the
                    # accounting impact (Section 1 spec: "Leave Credit,
                    # Debit, Running Balance blank on child rows").
                    'credit': None, 'debit': None, 'running_balance': None,
                })

            dated_entries.append((group['earliest_boe_date'] or _date.max, group['boe_numbers'][0] if group['boe_numbers'] else '', {
                'type': 'Licence Trade (Sold)',
                'document_number': trade.invoice_number if trade else '-',
                # `boe_number`/`boe_date_display` are pre-joined display
                # strings (matching the DISPLAY RULES spec verbatim, e.g.
                # "7650222, 7650224"); `boe_date` stays a single date (the
                # earliest linked BOE) for type-consistency with 'boe' rows
                # and for chronological sorting. `linked_boe_numbers`/
                # `linked_boe_dates` give the UI the raw list for smarter
                # truncation ("7650222 (+1)") with a tooltip.
                'boe_number': ', '.join(group['boe_numbers']),
                'boe_date': group['earliest_boe_date'],
                'boe_date_display': ', '.join(
                    d.strftime('%d-%m-%Y') if d else '-' for d in group['boe_dates']
                ),
                'company': ', '.join(group['companies']) if group['companies'] else '-',
                'item_name': ', '.join(group['item_names']) if group['item_names'] else '-',
                'invoice_numbers': split_invoice_numbers(trade.invoice_number if trade else None),
                'qty': group['total_qty'], 'cif_usd': group['total_cif_fc'], 'cif_inr': group['total_cif_inr'],
                'credit': DEC_0, 'debit': debit,
                'remarks': remarks, 'row_kind': 'boe_allocation',
                'linked_boe_numbers': group['boe_numbers'],
                'linked_boe_dates': [d.isoformat() if d else None for d in group['boe_dates']],
                'trade_line_id': trade_line.id,
                'expandable': True,
                'children': children,
            }))

        # Merge BOE rows and consolidated allocation rows into one
        # chronological sequence (oldest first), assign date/sr/running
        # balance in that merged order.
        dated_entries.sort(key=lambda entry: (entry[0], entry[1]))
        for sort_date, _, entry in dated_entries:
            running -= entry['debit']
            entry['sr'] = sr
            entry['date'] = None if sort_date == _date.max else sort_date
            entry['running_balance'] = running
            rows.append(entry)
            sr += 1

        allot_rows = (
            LicenseBalanceCalculator.get_allotment_rows(license_obj)
            .filter(contributed__gt=DEC_0)
            .select_related('allotment__company', 'item')
            .prefetch_related('item__items')
            .order_by('allotment__estimated_arrival_date')
        )
        total_allotment_debit = DEC_0
        for a_row in allot_rows:
            allotment = a_row.allotment
            debit = a_row.contributed
            total_allotment_debit += debit
            running -= debit

            rows.append({
                'sr': sr,
                'date': allotment.estimated_arrival_date if allotment else None,
                'type': 'Active Allotment',
                'document_number': f"ALT-{allotment.id}" if allotment else '-',
                'boe_number': None, 'boe_date': None,
                'company': allotment.company.name if (allotment and allotment.company) else '-',
                'item_name': item_display_name(a_row.item, fallback=(allotment.item_name if allotment else '')),
                'invoice_numbers': split_invoice_numbers(allotment.invoice if allotment else None),
                'qty': a_row.qty, 'cif_usd': None, 'cif_inr': None,
                'credit': DEC_0, 'debit': debit, 'running_balance': running,
                'remarks': 'Outstanding Commitment', 'row_kind': 'allotment',
                'allotment_item_id': a_row.id,
            })
            sr += 1

        # Licence Trade (Sold) debits — the UNALLOCATED remainder only.
        # calculate_balance() subtracts calculate_trade()'s FULL cif_fc per
        # SALE trade line unconditionally, but any portion already
        # represented by a consolidated "BOE Allocation" row above must not
        # be counted here again. `remaining_for_trade_line` (allocated_cif
        # subtracted) gives exactly the leftover: for a trade line with NO
        # allocations, remaining == the full cif_fc (identical to the old
        # unconditional behaviour); for one FULLY allocated, remaining == 0
        # and it is omitted entirely (its full amount is already shown via
        # the consolidated row); for a PARTIALLY allocated one, only the
        # genuinely-unmatched slice shows here. allocated + remaining ==
        # the trade line's own cif_fc always (allocations can never exceed
        # it — enforced at allocation-creation time), so total debit across
        # the consolidated rows + this section is unchanged from before.
        trade_rows = (
            LicenseBalanceCalculator.get_trade_rows(license_obj)
            .select_related('trade__to_company', 'sr_number')
            .prefetch_related('sr_number__items')
            .order_by('trade__invoice_date', 'trade__invoice_number')
        )
        total_trade_debit = DEC_0
        for t_row in trade_rows:
            trade = t_row.trade
            remaining_qty, remaining_cif, _remaining_cif_inr = remaining_for_trade_line(t_row)
            if remaining_cif <= DEC_0:
                continue
            debit = remaining_cif
            total_trade_debit += debit
            running -= debit

            rows.append({
                'sr': sr,
                'date': trade.invoice_date if trade else None,
                'type': 'Licence Trade (Sold)',
                'document_number': trade.invoice_number if trade else '-',
                'boe_number': None, 'boe_date': None,
                'company': trade.to_company.name if (trade and trade.to_company) else '-',
                'item_name': item_display_name(t_row.sr_number),
                'invoice_numbers': split_invoice_numbers(trade.invoice_number if trade else None),
                'qty': remaining_qty if t_row.mode == t_row.MODE_QTY else None,
                'cif_usd': None, 'cif_inr': None,
                'credit': DEC_0, 'debit': debit, 'running_balance': running,
                'remarks': 'Reconciled Sale — unmatched remainder (see Invoice ↔ BOE Reconciliation)', 'row_kind': 'trade',
            })
            sr += 1

        engine_balance = LicenseBalanceCalculator.calculate_balance(license_obj)
        computed_balance = quantize_2dp(running)
        computed_balance = computed_balance if computed_balance >= DEC_0 else DEC_0

        difference = abs(computed_balance - engine_balance)
        mismatched = difference > TOLERANCE

        rows.append({
            'sr': sr, 'date': None, 'type': 'Current Balance',
            'document_number': None, 'boe_number': None, 'boe_date': None,
            'company': None, 'item_name': None, 'invoice_numbers': [],
            'qty': None, 'cif_usd': None, 'cif_inr': None,
            'credit': DEC_0, 'debit': DEC_0, 'running_balance': computed_balance,
            'remarks': 'Balance Engine' if not mismatched else f"MISMATCH vs Balance Engine (Δ ${difference:,.2f})",
            'row_kind': 'final', 'mismatched': mismatched,
        })

        summary = {
            'opening_balance': opening_balance,
            'total_boe_debit': total_boe_debit,
            'total_invoice_allocation_debit': total_invoice_allocation_debit,
            'total_allotment_debit': total_allotment_debit,
            'total_trade_debit': total_trade_debit,
            'computed_balance': computed_balance,
            'engine_balance': engine_balance,
            'difference': difference,
            'mismatched': mismatched,
            'tolerance': TOLERANCE,
        }
        return rows, summary

    # ------------------------------------------------------------------
    # Customs Ledger — running CUSTOMS utilisation statement
    # ------------------------------------------------------------------

    @staticmethod
    def build_customs_ledger(license_obj):
        """
        A SEPARATE running-balance statement from `build_financial_ledger`,
        representing raw customs utilisation: every BOE debits the licence
        at its FULL `cif_fc`, unconditionally — regardless of whether that
        BOE has since been matched to an invoice via `InvoiceBOEAllocation`.

        This is intentional, not a bug: the Customs Ledger answers "what
        physically came through customs against this licence" (the
        Customs/Accounts view); the Financial Ledger answers "how has that
        been reconciled financially" (it uses the allocation-adjusted
        `contributed` amount specifically to avoid double-counting against
        `calculate_trade()`'s SALE-line debit — see that method's
        docstring). The two are expected to land on the same final number
        ONLY when every BOE/invoice relationship on this licence is fully
        reconciled with no dangling remainder on either side; whenever they
        diverge, that gap IS the actionable reconciliation signal this
        workspace exists to surface (see `build_reconciliation_summary`,
        which now compares Financial vs Customs vs Balance Engine
        three-way) — never silently forced to match.

        The Final "Current Balance" row's `running_balance` is always the
        live Balance Engine value itself (the authoritative anchor a reader
        can trust at a glance); THIS ledger's own accumulated total is
        returned separately as `summary['computed_balance']` for explicit
        side-by-side comparison in the Customs Summary.
        """
        from apps.license.services.balance_calculator import LicenseBalanceCalculator, quantize_2dp
        from apps.reconciliation.models import InvoiceBOEAllocation

        opening_balance = license_obj.opening_balance
        rows = []
        sr = 1
        running = opening_balance

        rows.append({
            'sr': sr, 'date': license_obj.license_date, 'type': 'Opening Balance',
            'document_number': license_obj.license_number or '-',
            'boe_number': None, 'boe_date': None, 'company': None, 'item_name': None,
            'invoice_numbers': [], 'qty': None, 'cif_usd': None, 'cif_inr': None,
            'credit': opening_balance, 'debit': DEC_0, 'running_balance': running,
            'status': '-', 'remarks': 'Licence Issued', 'row_kind': 'customs_opening',
        })
        sr += 1

        # Any BOE with >=1 active InvoiceBOEAllocation is "Matched" here —
        # unlike the Financial Ledger, partial vs full match doesn't change
        # what's debited (always the full cif_fc), only the displayed status.
        matched_row_ids = set(
            InvoiceBOEAllocation.objects.filter(
                row_details__sr_number__license=license_obj,
                status=InvoiceBOEAllocation.STATUS_ACTIVE,
                is_current=True,
            ).values_list('row_details_id', flat=True)
        )

        boe_rows = (
            LicenseBalanceCalculator.get_debit_rows(license_obj)
            .select_related('bill_of_entry__company', 'sr_number')
            .prefetch_related('sr_number__items')
            .order_by('bill_of_entry__bill_of_entry_date', 'bill_of_entry__bill_of_entry_number')
        )
        total_boe_cif = DEC_0
        for row in boe_rows:
            boe = row.bill_of_entry
            debit = row.cif_fc  # FULL amount — unconditional, see docstring.
            total_boe_cif += debit
            running -= debit
            matched = row.id in matched_row_ids

            rows.append({
                'sr': sr,
                'date': boe.bill_of_entry_date if boe else None,
                'type': 'BOE',
                'document_number': boe.bill_of_entry_number if boe else '-',
                'boe_number': boe.bill_of_entry_number if boe else '-',
                'boe_date': boe.bill_of_entry_date if boe else None,
                'company': boe.company.name if (boe and boe.company) else '-',
                'item_name': item_display_name(row.sr_number, fallback=(boe.product_name if boe else '')),
                'invoice_numbers': [],
                'qty': row.qty, 'cif_usd': row.cif_fc, 'cif_inr': row.cif_inr,
                'credit': DEC_0, 'debit': debit, 'running_balance': running,
                'status': 'Matched' if matched else 'Unmatched',
                'remarks': 'Matched to Invoice' if matched else '-',
                'row_kind': 'customs_boe', 'row_details_id': row.id,
            })
            sr += 1

        allot_rows = (
            LicenseBalanceCalculator.get_allotment_rows(license_obj)
            .filter(contributed__gt=DEC_0)
            .select_related('allotment__company', 'item')
            .prefetch_related('item__items')
            .order_by('allotment__estimated_arrival_date')
        )
        total_pending_allotment_cif = DEC_0
        for a_row in allot_rows:
            allotment = a_row.allotment
            debit = a_row.contributed
            total_pending_allotment_cif += debit
            running -= debit

            rows.append({
                'sr': sr,
                'date': allotment.estimated_arrival_date if allotment else None,
                'type': 'Pending Allotment',
                'document_number': f"ALT-{allotment.id}" if allotment else '-',
                'boe_number': None, 'boe_date': None,
                'company': allotment.company.name if (allotment and allotment.company) else '-',
                'item_name': item_display_name(a_row.item, fallback=(allotment.item_name if allotment else '')),
                'invoice_numbers': [],
                'qty': a_row.qty, 'cif_usd': a_row.contributed, 'cif_inr': None,
                'credit': DEC_0, 'debit': debit, 'running_balance': running,
                'status': 'Pending', 'remarks': 'Awaiting BOE',
                'row_kind': 'customs_pending_allotment', 'allotment_item_id': a_row.id,
            })
            sr += 1

        engine_balance = LicenseBalanceCalculator.calculate_balance(license_obj)
        computed_balance = quantize_2dp(running)
        computed_balance = computed_balance if computed_balance >= DEC_0 else DEC_0

        difference = abs(computed_balance - engine_balance)
        mismatched = difference > TOLERANCE

        rows.append({
            'sr': sr, 'date': None, 'type': 'Current Balance',
            'document_number': None, 'boe_number': None, 'boe_date': None,
            'company': None, 'item_name': None, 'invoice_numbers': [],
            'qty': None, 'cif_usd': None, 'cif_inr': None,
            'credit': DEC_0, 'debit': DEC_0,
            # Anchor: always the live engine value, not this ledger's own
            # (possibly-diverging) running total — see docstring.
            'running_balance': engine_balance,
            'status': 'Balance Engine',
            'remarks': 'Licence Available CIF' if not mismatched else f"MISMATCH vs this ledger's own total (Δ ${difference:,.2f})",
            'row_kind': 'final', 'mismatched': mismatched,
        })

        summary = {
            'opening_balance': opening_balance,
            'total_boe_cif': total_boe_cif,
            'total_pending_allotment_cif': total_pending_allotment_cif,
            'computed_balance': computed_balance,
            'engine_balance': engine_balance,
            'difference': difference,
            'mismatched': mismatched,
            'tolerance': TOLERANCE,
        }
        return rows, summary

    # ------------------------------------------------------------------
    # Invoice <-> BOE relationships
    # ------------------------------------------------------------------

    @staticmethod
    def build_invoice_boe_relationships(license_obj):
        """
        One entry per SALE `LicenseTradeLine` ("invoice") belonging to this
        licence, with its matched `InvoiceBOEAllocation` rows (linked BOEs)
        and remaining qty/CIF still to be allocated. Plus one synthetic
        group per distinct external invoice number (BOEs marked via
        `mark_boe_as_external_invoice` with no system trade line).
        """
        from apps.reconciliation.models import ExternalInvoiceLink, InvoiceBOEAllocation
        from apps.reconciliation.services.allocation_service import remaining_for_trade_line
        from apps.license.services.balance_calculator import LicenseBalanceCalculator

        invoices = []
        trade_lines = (
            LicenseBalanceCalculator.get_trade_rows(license_obj)
            .select_related('trade__to_company', 'sr_number')
        )
        for line in trade_lines:
            trade = line.trade
            allocations = list(
                InvoiceBOEAllocation.objects.filter(
                    trade_line=line, status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True,
                ).select_related('row_details__bill_of_entry')
            )
            remaining_qty, remaining_cif_fc, remaining_cif_inr = remaining_for_trade_line(line)
            invoices.append({
                'kind': 'system',
                'trade_line_id': line.id,
                'invoice_number': trade.invoice_number if trade else '-',
                'supplier': trade.to_company.name if (trade and trade.to_company) else '-',
                'purchase_date': trade.invoice_date if trade else None,
                'invoice_qty': line.qty_kg,
                'invoice_cif': line.cif_fc,
                'matched_qty': (line.qty_kg or DEC_0) - remaining_qty,
                'matched_cif': line.cif_fc - remaining_cif_fc,
                'remaining_qty': remaining_qty,
                'remaining_cif': remaining_cif_fc,
                'status': 'FULLY_MATCHED' if remaining_cif_fc <= DEC_0 else (
                    'PARTIALLY_MATCHED' if allocations else 'UNMATCHED'
                ),
                'linked_boes': [
                    {
                        'allocation_id': alloc.id,
                        'row_details_id': alloc.row_details_id,
                        'bill_of_entry_number': (
                            alloc.row_details.bill_of_entry.bill_of_entry_number
                            if alloc.row_details.bill_of_entry else '-'
                        ),
                        'allocated_qty': alloc.allocated_qty,
                        'allocated_cif_fc': alloc.allocated_cif_fc,
                    }
                    for alloc in allocations
                ],
            })

        # External invoices: group ACTIVE, current links by invoice_number.
        ext_groups = {}
        ext_links = ExternalInvoiceLink.objects.filter(
            row_details__sr_number__license=license_obj,
            status=ExternalInvoiceLink.STATUS_ACTIVE,
            is_current=True,
        ).select_related('row_details__bill_of_entry')
        for link in ext_links:
            group = ext_groups.setdefault(link.invoice_number, {
                'kind': 'external',
                'invoice_number': link.invoice_number,
                'supplier': None,
                'purchase_date': None,
                'invoice_qty': DEC_0,
                'invoice_cif': DEC_0,
                'matched_qty': DEC_0,
                'matched_cif': DEC_0,
                'remaining_qty': DEC_0,
                'remaining_cif': DEC_0,
                'status': 'EXTERNAL',
                'linked_boes': [],
            })
            group['invoice_qty'] += link.qty
            group['invoice_cif'] += link.cif_fc
            group['matched_qty'] += link.qty
            group['matched_cif'] += link.cif_fc
            group['linked_boes'].append({
                'link_id': link.id,
                'row_details_id': link.row_details_id,
                'bill_of_entry_number': (
                    link.row_details.bill_of_entry.bill_of_entry_number
                    if link.row_details.bill_of_entry else '-'
                ),
                'allocated_qty': link.qty,
                'allocated_cif_fc': link.cif_fc,
            })
        invoices.extend(ext_groups.values())
        return invoices

    # ------------------------------------------------------------------
    # Candidate lists for the allocation drawers
    # ------------------------------------------------------------------

    @staticmethod
    def build_boe_invoice_candidates(license_obj):
        """
        One entry per BOE debit row on this licence, with its INVOICE-SIDE
        remaining capacity (`remaining_for_row_details_invoice_side`) — the
        correct candidate list for the "Find BOE" drawer when allocating an
        INVOICE against BOEs.

        Deliberately NOT the same list as `build_boe_allotment_relationships`
        (which exposes the ALLOTMENT-side remaining — an independent
        consumption track). Reusing that list here was the root cause of a
        reported false "over allocation" validation error: a BOE's
        allotment-side remaining and invoice-side remaining are two
        different numbers that are only coincidentally equal when neither
        track has any allocations yet on that row.
        """
        from apps.reconciliation.services.allocation_service import remaining_for_row_details_invoice_side
        from apps.license.services.balance_calculator import LicenseBalanceCalculator

        candidates = []
        rows = (
            LicenseBalanceCalculator.get_debit_rows(license_obj)
            .select_related('bill_of_entry__company', 'bill_of_entry__port', 'sr_number')
            .prefetch_related('sr_number__items')
        )
        for row in rows:
            boe = row.bill_of_entry
            remaining_qty, remaining_cif_fc, remaining_cif_inr = remaining_for_row_details_invoice_side(row)
            candidates.append({
                'row_details_id': row.id,
                'bill_of_entry_number': boe.bill_of_entry_number if boe else '-',
                'bill_of_entry_date': boe.bill_of_entry_date if boe else None,
                'company': boe.company.name if (boe and boe.company) else '-',
                'item_name': item_display_name(row.sr_number, fallback=(boe.product_name if boe else '')),
                'boe_qty': row.qty,
                'boe_cif': row.cif_fc,
                'boe_cif_inr': row.cif_inr,
                'remaining_qty': remaining_qty,
                'remaining_cif': remaining_cif_fc,
                'remaining_cif_inr': remaining_cif_inr,
            })
        return candidates

    @staticmethod
    def build_allotment_candidates(license_obj):
        """
        One entry per `AllotmentItems` row on this licence with remaining
        capacity to be sourced BY a BOE (`remaining_for_allotment_item`) —
        the correct candidate list for the "Find Allotment" drawer. Filters
        out allotment items with zero remaining qty AND CIF (fully
        consumed already).
        """
        from apps.allotment.models import AllotmentItems
        from apps.reconciliation.services.allocation_service import remaining_for_allotment_item

        candidates = []
        items = (
            AllotmentItems.objects.filter(item__license=license_obj)
            .select_related('allotment__company', 'item')
            .prefetch_related('item__items')
        )
        for allotment_item in items:
            remaining_qty, remaining_cif_fc, remaining_cif_inr = remaining_for_allotment_item(allotment_item)
            if remaining_qty <= DEC_0 and remaining_cif_fc <= DEC_0:
                continue
            allotment = allotment_item.allotment
            candidates.append({
                'allotment_item_id': allotment_item.id,
                'allotment_number': f"ALT-{allotment.id}" if allotment else '-',
                'company': allotment.company.name if (allotment and allotment.company) else '-',
                'item_name': item_display_name(allotment_item.item, fallback=(allotment.item_name if allotment else '')),
                'estimated_arrival_date': allotment.estimated_arrival_date if allotment else None,
                'allotment_qty': allotment_item.qty,
                'allotment_cif': allotment_item.cif_fc,
                'remaining_qty': remaining_qty,
                'remaining_cif': remaining_cif_fc,
                'remaining_cif_inr': remaining_cif_inr,
            })
        return candidates

    # ------------------------------------------------------------------
    # BOE <-> Allotment relationships
    # ------------------------------------------------------------------

    @staticmethod
    def build_boe_allotment_relationships(license_obj):
        """One entry per BOE debit row on this licence, with its matched
        `BOEAllotmentAllocation` rows (linked allotments) and remaining
        qty/CIF still available to source from an allotment."""
        from apps.reconciliation.models import BOEAllotmentAllocation
        from apps.reconciliation.services.allocation_service import remaining_for_row_details_allotment_side
        from apps.license.services.balance_calculator import LicenseBalanceCalculator

        boes = []
        rows = (
            LicenseBalanceCalculator.get_debit_rows(license_obj)
            .select_related('bill_of_entry__company', 'sr_number')
        )
        for row in rows:
            boe = row.bill_of_entry
            allocations = list(
                BOEAllotmentAllocation.objects.filter(
                    row_details=row, status=BOEAllotmentAllocation.STATUS_ACTIVE, is_current=True,
                ).select_related('allotment_item__allotment')
            )
            remaining_qty, remaining_cif_fc, remaining_cif_inr = remaining_for_row_details_allotment_side(row)
            boes.append({
                'row_details_id': row.id,
                'bill_of_entry_number': boe.bill_of_entry_number if boe else '-',
                'bill_of_entry_date': boe.bill_of_entry_date if boe else None,
                'company': boe.company.name if (boe and boe.company) else '-',
                'boe_qty': row.qty,
                'boe_cif': row.cif_fc,
                'matched_qty': (row.qty or DEC_0) - remaining_qty,
                'matched_cif': row.cif_fc - remaining_cif_fc,
                'remaining_qty': remaining_qty,
                'remaining_cif': remaining_cif_fc,
                'status': 'FULLY_SOURCED' if remaining_cif_fc <= DEC_0 else (
                    'PARTIALLY_SOURCED' if allocations else 'UNSOURCED'
                ),
                'linked_allotments': [
                    {
                        'allocation_id': alloc.id,
                        'allotment_item_id': alloc.allotment_item_id,
                        'allotment_number': (
                            f"ALT-{alloc.allotment_item.allotment_id}"
                            if alloc.allotment_item and alloc.allotment_item.allotment_id else '-'
                        ),
                        'allocated_qty': alloc.allocated_qty,
                        'allocated_cif_fc': alloc.allocated_cif_fc,
                    }
                    for alloc in allocations
                ],
            })
        return boes

    # ------------------------------------------------------------------
    # Reconciliation summary
    # ------------------------------------------------------------------

    @staticmethod
    def build_reconciliation_summary(license_obj, financial_summary, customs_summary=None):
        """
        Three-way comparison: Financial Ledger balance vs. Customs Ledger
        balance vs. the live Balance Engine.

        `customs_summary` is `build_customs_ledger()`'s own summary dict —
        when omitted (back-compat for callers that only need the financial
        side), falls back to the denormalized `license_obj.balance_cif`,
        which also catches a stale denormalized value specifically.
        """
        financial_balance = financial_summary['computed_balance']
        engine_balance = financial_summary['engine_balance']
        tolerance = financial_summary['tolerance']
        if customs_summary is not None:
            customs_balance = customs_summary['computed_balance']
        else:
            customs_balance = Decimal(str(license_obj.balance_cif or 0)).quantize(Decimal('0.01'))

        diff_financial = abs(financial_balance - engine_balance)
        diff_customs = abs(customs_balance - engine_balance)
        worst_diff = max(diff_financial, diff_customs)

        return {
            'financial_ledger_balance': financial_balance,
            'customs_ledger_balance': customs_balance,
            'balance_engine': engine_balance,
            'difference': worst_diff,
            'tolerance': tolerance,
            'matched': worst_diff <= tolerance,
        }

    # ------------------------------------------------------------------
    # Timeline — real business-lifecycle events only, never fabricated
    # ------------------------------------------------------------------

    _TIMELINE_COLORS = {
        'purchase_trade': 'blue', 'sale_trade': 'blue',
        'allotment_created': 'orange',
        'boe_filed': 'green',
        'invoice_boe_reconciled': 'purple',
        'boe_allotment_reconciled': 'teal',
        'external_invoice_marked': 'purple',
        'manual_adjustment': 'grey',
        'reconciliation_action': 'grey',
    }

    @classmethod
    def build_timeline(cls, license_obj):
        """
        Chronological business-lifecycle timeline built ENTIRELY from real,
        persisted records — no synthesized or inferred events, and nothing
        included unless a real row backs it. Sourced from:
          - `LicenseTrade.created_on` (Purchase / Sale trade created) —
            one event per distinct trade header on this licence (a trade
            can carry several `LicenseTradeLine`s, but the header is the
            real recorded event; grouped, not repeated per line).
          - `AllotmentItems.created_on` (Allotment Created).
          - `RowDetails.created_on` (BOE Filed) — the debit posts at this
            same moment, so "Licence Debit Posted" is folded into this
            event's own remarks rather than synthesized as a second event.
          - `InvoiceBOEAllocation.created_on` (Invoice<->BOE Reconciled),
            grouped by trade line exactly like `build_invoice_allocation_
            groups` — one parent event per invoice, with one child event
            per underlying BOE allocation (hierarchical, same pattern as
            the Financial Ledger's consolidated rows).
          - `BOEAllotmentAllocation.created_on` (BOE<->Allotment
            Reconciled), grouped by BOE row — one parent per BOE, children
            per allotment allocation.
          - `ExternalInvoiceLink.created_on` (External Invoice Marked).
          - `ReconciliationLog` (every allocate/edit/reverse/mark-external/
            recalculate action already recorded by this workspace's own
            write endpoints) — this IS the existing audit trail; reused
            here as "Manual Adjustments" / reconciliation-action events,
            never duplicated into a second logging mechanism.

        Scope note: this system has no "Purchase Order" entity distinct
        from a PURCHASE-direction `LicenseTrade` — so "Purchase Order" is
        represented by that same trade record, not fabricated as a
        separate step. If a licence has no PURCHASE-direction trade at
        all, no such event appears (never inferred).
        """
        from django.db.models import Sum as _Sum

        from apps.reconciliation.models import BOEAllotmentAllocation, ExternalInvoiceLink, ReconciliationLog
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        from apps.trade.models import LicenseTrade

        def user_label(user):
            if not user:
                return None
            return getattr(user, 'get_full_name', lambda: None)() or getattr(user, 'username', None)

        dated = []  # (datetime_for_sort, event_dict)

        def add(dt, event_type, **fields):
            if dt is None:
                return
            event = {
                'event_type': event_type,
                'label': fields.pop('label'),
                'date': dt,
                'document_number': fields.get('document_number'),
                'company': fields.get('company'),
                'quantity': fields.get('quantity'),
                'cif': fields.get('cif'),
                'user': fields.get('user'),
                'status': fields.get('status', '-'),
                'remarks': fields.get('remarks', ''),
                'entity_reference': fields.get('entity_reference'),
                'event_source': fields.get('event_source'),
                'color': cls._TIMELINE_COLORS.get(event_type, 'grey'),
                'expandable': bool(fields.get('children')),
                'children': fields.get('children', []),
            }
            dated.append((dt, event))

        # ---- Trades (Purchase / Sale) — one event per trade header ----
        trades = (
            LicenseTrade.objects.filter(lines__sr_number__license=license_obj)
            .distinct()
            .select_related('to_company', 'from_company')
        )
        for trade in trades:
            is_purchase = trade.direction in (LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE)
            line_totals = trade.lines.filter(sr_number__license=license_obj).aggregate(
                qty=_Sum('qty_kg'), cif=_Sum('cif_fc'),
            )
            add(
                trade.created_on, 'purchase_trade' if is_purchase else 'sale_trade',
                label='Purchase Invoice' if is_purchase else 'Invoice Recorded',
                document_number=trade.invoice_number or '-',
                company=(trade.from_company.name if trade.from_company else None) if is_purchase else (
                    trade.to_company.name if trade.to_company else None
                ),
                quantity=line_totals['qty'], cif=line_totals['cif'],
                user=user_label(getattr(trade, 'created_by', None)),
                status=trade.direction, remarks=f"{trade.get_direction_display()} trade recorded",
                entity_reference=f"trade:{trade.id}", event_source='LicenseTrade',
            )

        # ---- Allotments ----
        allot_items = (
            LicenseBalanceCalculator.get_allotment_rows(license_obj)
            .select_related('allotment__company', 'item')
        )
        for a_row in allot_items:
            allotment = a_row.allotment
            add(
                getattr(a_row, 'created_on', None), 'allotment_created', label='Allotment Created',
                document_number=f"ALT-{allotment.id}" if allotment else '-',
                company=allotment.company.name if (allotment and allotment.company) else None,
                quantity=a_row.qty, cif=a_row.cif_fc,
                user=user_label(getattr(a_row, 'created_by', None)),
                status='Active', remarks='Allotment recorded against this licence',
                entity_reference=f"allotment_item:{a_row.id}", event_source='AllotmentItems',
            )

        # ---- BOEs filed ----
        boe_rows = (
            LicenseBalanceCalculator.get_debit_rows(license_obj)
            .select_related('bill_of_entry__company', 'sr_number')
        )
        for row in boe_rows:
            boe = row.bill_of_entry
            add(
                getattr(row, 'created_on', None), 'boe_filed', label='BOE Filed',
                document_number=boe.bill_of_entry_number if boe else '-',
                company=boe.company.name if (boe and boe.company) else None,
                quantity=row.qty, cif=row.cif_fc,
                user=user_label(getattr(row, 'created_by', None)),
                status='Filed',
                remarks=f"Debits licence ${row.cif_fc:,.2f} (BOE date {boe.bill_of_entry_date if boe else '-'})",
                entity_reference=f"row_details:{row.id}", event_source='RowDetails',
            )

        # ---- Invoice <-> BOE reconciliation (hierarchical) ----
        for group in build_invoice_allocation_groups(license_obj):
            trade_line = group['trade_line']
            trade = trade_line.trade
            children = []
            for alloc in group['allocations']:
                boe = alloc.row_details.bill_of_entry
                children.append({
                    'event_type': 'invoice_boe_reconciled', 'label': 'BOE Allocation',
                    'date': alloc.created_on, 'document_number': boe.bill_of_entry_number if boe else '-',
                    'company': boe.company.name if (boe and boe.company) else None,
                    'quantity': alloc.allocated_qty, 'cif': alloc.allocated_cif_fc,
                    'user': user_label(alloc.created_by), 'status': alloc.status,
                    'remarks': alloc.notes or 'Matched to invoice',
                    'entity_reference': f"invoice_boe_allocation:{alloc.id}", 'event_source': 'InvoiceBOEAllocation',
                    'color': cls._TIMELINE_COLORS['invoice_boe_reconciled'],
                })
            latest = max((a.created_on for a in group['allocations']), default=None)
            add(
                latest, 'invoice_boe_reconciled', label='Invoice ↔ BOE Reconciled',
                document_number=trade.invoice_number if trade else '-',
                company=trade.to_company.name if (trade and trade.to_company) else None,
                quantity=group['total_qty'], cif=group['total_cif_fc'],
                status='Reconciled',
                remarks=f"Matched to {len(group['boe_numbers'])} BOE(s)",
                entity_reference=f"trade_line:{trade_line.id}", event_source='InvoiceBOEAllocation',
                children=children,
            )

        # ---- BOE <-> Allotment reconciliation (hierarchical) ----
        allotment_allocations = (
            BOEAllotmentAllocation.objects.filter(
                row_details__sr_number__license=license_obj,
                status=BOEAllotmentAllocation.STATUS_ACTIVE, is_current=True,
            ).select_related('row_details__bill_of_entry__company', 'allotment_item__allotment__company')
        )
        by_row_details = {}
        for alloc in allotment_allocations:
            by_row_details.setdefault(alloc.row_details_id, []).append(alloc)
        for row_details_id, allocs in by_row_details.items():
            boe = allocs[0].row_details.bill_of_entry
            children = []
            for alloc in allocs:
                allotment = alloc.allotment_item.allotment
                children.append({
                    'event_type': 'boe_allotment_reconciled', 'label': 'Allotment Allocation',
                    'date': alloc.created_on,
                    'document_number': f"ALT-{allotment.id}" if allotment else '-',
                    'company': allotment.company.name if (allotment and allotment.company) else None,
                    'quantity': alloc.allocated_qty, 'cif': alloc.allocated_cif_fc,
                    'user': user_label(alloc.created_by), 'status': alloc.status,
                    'remarks': alloc.notes or 'Sourced from allotment',
                    'entity_reference': f"boe_allotment_allocation:{alloc.id}", 'event_source': 'BOEAllotmentAllocation',
                    'color': cls._TIMELINE_COLORS['boe_allotment_reconciled'],
                })
            latest = max((a.created_on for a in allocs), default=None)
            add(
                latest, 'boe_allotment_reconciled', label='BOE ↔ Allotment Reconciled',
                document_number=boe.bill_of_entry_number if boe else '-',
                company=boe.company.name if (boe and boe.company) else None,
                quantity=sum((a.allocated_qty for a in allocs), DEC_0),
                cif=sum((a.allocated_cif_fc for a in allocs), DEC_0),
                status='Reconciled', remarks=f"Sourced from {len(allocs)} allotment(s)",
                entity_reference=f"row_details:{row_details_id}", event_source='BOEAllotmentAllocation',
                children=children,
            )

        # ---- External invoice marks ----
        for link in ExternalInvoiceLink.objects.filter(
            row_details__sr_number__license=license_obj,
        ).select_related('row_details__bill_of_entry__company'):
            boe = link.row_details.bill_of_entry
            add(
                link.created_on, 'external_invoice_marked', label='External Invoice Marked',
                document_number=link.invoice_number,
                company=boe.company.name if (boe and boe.company) else None,
                quantity=link.qty, cif=link.cif_fc,
                user=user_label(link.created_by), status=link.status,
                remarks=link.notes or 'Marked as external/out-of-system invoice',
                entity_reference=f"external_invoice_link:{link.id}", event_source='ExternalInvoiceLink',
            )

        # ---- Manual adjustments / reconciliation actions (existing audit log) ----
        for log in ReconciliationLog.objects.filter(license_item__license=license_obj).select_related('user'):
            add(
                log.created_on,
                'manual_adjustment' if log.action == ReconciliationLog.ACTION_RECALCULATE else 'reconciliation_action',
                label=log.get_action_display(),
                document_number=None, company=None, quantity=None, cif=None,
                user=user_label(log.user), status=log.action,
                remarks=log.reason or '-',
                entity_reference=f"reconciliation_log:{log.id}", event_source='ReconciliationLog',
            )

        dated.sort(key=lambda pair: pair[0])
        events = []
        for i, (_, event) in enumerate(dated, start=1):
            event['sr'] = i
            events.append(event)
        return events

    # ------------------------------------------------------------------
    # Warnings
    # ------------------------------------------------------------------

    @staticmethod
    def build_warnings(license_obj, financial_summary, reconciliation_summary, invoice_boe, boe_allotment):
        """
        Each warning carries a STABLE identity (`warning_type`,
        `entity_type`, `entity_id`) — recomputed fresh every call, but
        deterministic, so it can be matched against a persisted
        `IgnoredWarning` row across requests. `ignored`/`ignored_by`/
        `ignored_at`/`reason` are populated from that model purely for
        display; ignoring a warning NEVER changes any value elsewhere in
        this dataset (financial_ledger/customs_ledger/reconciliation are
        computed before this method runs and are never re-touched here).
        """
        from apps.reconciliation.models import IgnoredWarning

        warnings = []

        def add(warning_type, entity_type, entity_id, message):
            warnings.append({
                'warning_type': warning_type, 'entity_type': entity_type, 'entity_id': str(entity_id),
                'message': message, 'ignored': False, 'ignored_by': None, 'ignored_at': None, 'reason': '',
            })

        if financial_summary['mismatched']:
            add(
                'FINANCIAL_MISMATCH', 'LICENSE', license_obj.id,
                f"Financial Ledger balance (${financial_summary['computed_balance']:,.2f}) differs from the "
                f"Balance Engine (${financial_summary['engine_balance']:,.2f}) by more than the "
                f"${financial_summary['tolerance']:,.2f} tolerance.",
            )
        if not reconciliation_summary['matched']:
            add(
                'CUSTOMS_MISMATCH', 'LICENSE', license_obj.id,
                f"Customs Ledger balance (${reconciliation_summary['customs_ledger_balance']:,.2f}) differs from "
                f"the Balance Engine by ${reconciliation_summary['difference']:,.2f} — the stored balance_cif may "
                "be stale; recalculate this licence.",
            )
        for inv in invoice_boe:
            if inv['status'] == 'UNMATCHED':
                add(
                    'UNMATCHED_INVOICE', 'TRADE_LINE', inv['trade_line_id'],
                    f"Invoice {inv['invoice_number']} has no BOE linked yet.",
                )
        for boe in boe_allotment:
            if boe['status'] == 'UNSOURCED' and boe['remaining_cif'] > DEC_0:
                add(
                    'UNSOURCED_BOE', 'ROW_DETAILS', boe['row_details_id'],
                    f"BOE {boe['bill_of_entry_number']} has ${boe['remaining_cif']:,.2f} not sourced from any allotment.",
                )

        if warnings:
            ignored_map = {
                (row.warning_type, row.entity_type, row.entity_id): row
                for row in IgnoredWarning.objects.filter(license=license_obj)
            }
            for w in warnings:
                row = ignored_map.get((w['warning_type'], w['entity_type'], w['entity_id']))
                if row and row.ignored:
                    w['ignored'] = True
                    w['ignored_by'] = row.ignored_by.get_username() if row.ignored_by else None
                    w['ignored_at'] = row.ignored_at
                    w['reason'] = row.reason

        return warnings

    # ------------------------------------------------------------------
    # Top-level entrypoint
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, license_obj):
        """Returns the full `LicenseLedgerData` dict — the single dataset
        the workspace UI, PDF, and Excel exporters all render from."""
        alloc_map = boe_invoice_allocation_map(license_obj)
        ext_map = boe_external_invoice_map(license_obj)

        financial_rows, financial_summary = cls.build_financial_ledger(license_obj, alloc_map, ext_map)
        customs_rows, customs_summary = cls.build_customs_ledger(license_obj)
        invoice_boe = cls.build_invoice_boe_relationships(license_obj)
        boe_allotment = cls.build_boe_allotment_relationships(license_obj)
        boe_invoice_candidates = cls.build_boe_invoice_candidates(license_obj)
        allotment_candidates = cls.build_allotment_candidates(license_obj)
        reconciliation = cls.build_reconciliation_summary(license_obj, financial_summary, customs_summary)
        warnings = cls.build_warnings(license_obj, financial_summary, reconciliation, invoice_boe, boe_allotment)
        timeline = cls.build_timeline(license_obj)

        original_qty = sum(
            (item.quantity or DEC_0) for item in license_obj.import_license.all()
        ) or DEC_0
        current_qty = sum(
            (item.available_quantity or DEC_0) for item in license_obj.import_license.all()
        ) or DEC_0

        engine_balance = financial_summary['engine_balance']
        integrity_score = Decimal('100') if reconciliation['matched'] else max(
            Decimal('0'),
            Decimal('100') - (reconciliation['difference'] / max(engine_balance, Decimal('1')) * Decimal('100')),
        )

        return {
            'license': {
                'id': license_obj.id,
                'license_number': license_obj.license_number,
                'license_date': license_obj.license_date,
                'license_expiry_date': license_obj.license_expiry_date,
                'exporter': license_obj.exporter.name if license_obj.exporter else None,
                'original_cif': financial_summary['opening_balance'],
                'original_qty': original_qty,
                'current_balance_cif': engine_balance,
                'current_balance_qty': current_qty,
                'financial_integrity_score': integrity_score.quantize(Decimal('0.1')),
                'difference': reconciliation['difference'],
            },
            'financial_ledger': {'rows': financial_rows, 'summary': financial_summary},
            'customs_ledger': {'rows': customs_rows, 'summary': customs_summary},
            'invoice_boe': invoice_boe,
            'boe_allotment': boe_allotment,
            'boe_invoice_candidates': boe_invoice_candidates,
            'allotment_candidates': allotment_candidates,
            'reconciliation': reconciliation,
            'warnings': warnings,
            'timeline': timeline,
        }
