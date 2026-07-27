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
        Opening Balance -> BOE debits (oldest to newest) -> Active
        Allotments -> Licence Trade (Sold) debits -> Current Balance.

        `summary` carries the numbers needed by the Financial Summary and
        the Final Reconciliation Summary.
        """
        from apps.license.services.balance_calculator import LicenseBalanceCalculator, quantize_2dp

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

        boe_rows = (
            LicenseBalanceCalculator.get_debit_rows(license_obj)
            .select_related('bill_of_entry__company', 'sr_number')
            .prefetch_related('sr_number__items')
            .order_by('bill_of_entry__bill_of_entry_date', 'bill_of_entry__bill_of_entry_number')
        )
        total_boe_debit = DEC_0
        for row in boe_rows:
            boe = row.bill_of_entry
            debit = row.contributed
            total_boe_debit += debit
            running -= debit

            invoices = boe_row_invoice_numbers(row, alloc_map, ext_map)
            remarks = 'Matched Invoice(s)' if invoices else '-'
            if debit < row.cif_fc:
                note = f"Reconciled ${row.cif_fc - debit:,.2f} via Trade"
                remarks = f"{remarks} | {note}" if remarks != '-' else note

            rows.append({
                'sr': sr,
                'date': boe.bill_of_entry_date if boe else None,
                'type': 'BOE',
                'document_number': boe.bill_of_entry_number if boe else '-',
                'boe_number': boe.bill_of_entry_number if boe else '-',
                'boe_date': boe.bill_of_entry_date if boe else None,
                'company': boe.company.name if (boe and boe.company) else '-',
                'item_name': item_display_name(row.sr_number, fallback=(boe.product_name if boe else '')),
                'invoice_numbers': invoices,
                'qty': row.qty, 'cif_usd': row.cif_fc, 'cif_inr': row.cif_inr,
                'credit': DEC_0, 'debit': debit, 'running_balance': running,
                'remarks': remarks, 'row_kind': 'boe',
                'row_details_id': row.id,
            })
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

        # Licence Trade (Sold) debits — required for exact reconciliation:
        # calculate_balance() subtracts calculate_trade() too, so omitting
        # this would make the ledger's own arithmetic disagree with the
        # Balance Engine whenever part of this licence's BOE utilisation has
        # been resold onward. Rendered only when non-empty by consumers.
        trade_rows = (
            LicenseBalanceCalculator.get_trade_rows(license_obj)
            .select_related('trade__to_company', 'sr_number')
            .prefetch_related('sr_number__items')
            .order_by('trade__invoice_date', 'trade__invoice_number')
        )
        total_trade_debit = DEC_0
        for t_row in trade_rows:
            trade = t_row.trade
            debit = t_row.cif_fc
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
                'qty': t_row.qty_kg if t_row.mode == t_row.MODE_QTY else None,
                'cif_usd': None, 'cif_inr': None,
                'credit': DEC_0, 'debit': debit, 'running_balance': running,
                'remarks': 'Reconciled Sale (see Invoice ↔ BOE Reconciliation)', 'row_kind': 'trade',
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
    def build_reconciliation_summary(license_obj, financial_summary):
        """Compares the Financial Ledger's own balance against BOTH
        `license_obj.balance_cif` (denormalized) and the live Balance
        Engine — catches a stale denormalized value, not just a bug in the
        ledger itself."""
        financial_balance = financial_summary['computed_balance']
        engine_balance = financial_summary['engine_balance']
        tolerance = financial_summary['tolerance']
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
    # Warnings
    # ------------------------------------------------------------------

    @staticmethod
    def build_warnings(license_obj, financial_summary, reconciliation_summary, invoice_boe, boe_allotment):
        warnings = []
        if financial_summary['mismatched']:
            warnings.append(
                f"Financial Ledger balance (${financial_summary['computed_balance']:,.2f}) differs from the "
                f"Balance Engine (${financial_summary['engine_balance']:,.2f}) by more than the "
                f"${financial_summary['tolerance']:,.2f} tolerance."
            )
        if not reconciliation_summary['matched']:
            warnings.append(
                f"Customs Ledger balance (${reconciliation_summary['customs_ledger_balance']:,.2f}) differs from "
                f"the Balance Engine by ${reconciliation_summary['difference']:,.2f} — the stored balance_cif may "
                "be stale; recalculate this licence."
            )
        for inv in invoice_boe:
            if inv['status'] == 'UNMATCHED':
                warnings.append(f"Invoice {inv['invoice_number']} has no BOE linked yet.")
        for boe in boe_allotment:
            if boe['status'] == 'UNSOURCED' and boe['remaining_cif'] > DEC_0:
                warnings.append(
                    f"BOE {boe['bill_of_entry_number']} has ${boe['remaining_cif']:,.2f} not sourced from any allotment."
                )
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
        invoice_boe = cls.build_invoice_boe_relationships(license_obj)
        boe_allotment = cls.build_boe_allotment_relationships(license_obj)
        reconciliation = cls.build_reconciliation_summary(license_obj, financial_summary)
        warnings = cls.build_warnings(license_obj, financial_summary, reconciliation, invoice_boe, boe_allotment)

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
            'invoice_boe': invoice_boe,
            'boe_allotment': boe_allotment,
            'reconciliation': reconciliation,
            'warnings': warnings,
        }
