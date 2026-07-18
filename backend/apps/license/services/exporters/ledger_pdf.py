"""PDF renderers for the License Ledger reports.

Extracted verbatim from LicenseLedgerViewSet (export_all / company_ledger_export)
as part of the clean-architecture refactor: the viewset delegates rendering here.
Behaviour is unchanged.
"""
import logging
from decimal import Decimal
from io import BytesIO
from datetime import datetime

from django.utils import timezone
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

from apps.license.models import LicenseDetailsModel, IncentiveLicense

# Shared PDF infrastructure — no apps.* imports inside shared/
from shared.pdf.builders import (
    format_indian_number,
    make_landscape_doc,
    make_title_style,
    make_subtitle_style,
    make_wrap_style,
    make_section_title_style,
    make_header_table_style_commands,
    make_data_grid_commands,
    append_generated_footer,
    pl_color_name,
    pl_paragraph,
)

logger = logging.getLogger(__name__)



def get_license_transactions(lic_data, company_id=None):
    """
    Fetch detailed transactions for a single license.
    Returns list of transaction dictionaries with all details.

    When company_id is provided, uses direction-aware filtering (same logic as ledger_detail):
    - PURCHASE/COMMISSION_PURCHASE: only show if company is the BUYER (to_company)
    - SALE/COMMISSION_SALE: only show if company is the SELLER (from_company)
    """
    from apps.trade.models import LicenseTrade
    from django.utils import timezone
    from django.db.models import Q

    license_type = lic_data.get('license_type')
    lic_id = lic_data.get('id')

    if not lic_id:
        return []

    try:
        # Get the actual license object
        if license_type == 'DFIA':
            license_obj = LicenseDetailsModel.objects.get(id=lic_id)
        elif license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
            license_obj = IncentiveLicense.objects.get(id=lic_id)
        else:
            return []

        # Direction-aware company filter:
        # - PURCHASE: company is the BUYER (to_company)
        # - SALE: company is the SELLER (from_company)
        company_filter = Q()
        if company_id:
            try:
                company_id_int = int(company_id)
                company_filter = (
                    Q(direction__in=['PURCHASE', 'COMMISSION_PURCHASE'], to_company_id=company_id_int) |
                    Q(direction__in=['SALE', 'COMMISSION_SALE'], from_company_id=company_id_int)
                )
            except (ValueError, TypeError):
                pass

        if license_type == 'DFIA':
            trades = LicenseTrade.objects.filter(
                company_filter,
                license_type='DFIA',
                lines__sr_number__license=license_obj
            ).prefetch_related('lines__sr_number').distinct().order_by('invoice_date', 'id')
        else:
            # For Incentive licenses, use incentive_lines relationship
            trades = LicenseTrade.objects.filter(
                company_filter,
                license_type='INCENTIVE',
                incentive_lines__incentive_license=license_obj
            ).prefetch_related('incentive_lines').distinct().order_by('invoice_date', 'id')

        transactions = []
        running_balance = 0
        total_purchase_cif = 0
        total_purchase_amount = 0
        total_sales_amount = 0

        # Sort: all purchases before sales so P/L is computed correctly
        all_trans = []
        for trade in trades:
            all_trans.append((trade.direction, trade.invoice_date or timezone.now().date(), trade))

        all_trans.sort(key=lambda x: (x[0] not in ['PURCHASE', 'COMMISSION_PURCHASE'], x[1]))

        # Add opening balance if exists
        if len(all_trans) == 0 and license_type == 'DFIA':
            opening_bal = float(license_obj.opening_balance or 0)
            if opening_bal > 0:
                running_balance = opening_bal
                total_purchase_cif = opening_bal
                transactions.append({
                    'date': license_obj.license_date,
                    'type': 'OPENING',
                    'particular': f'Opening Balance - Original DFIA License',
                    'invoice_number': license_obj.license_number,
                    'cif_usd': opening_bal,
                    'debit_cif': opening_bal,
                    'credit_cif': 0,
                    'rate': 0,
                    'amount': 0,
                    'debit_amount': 0,
                    'credit_amount': 0,
                    'balance': round(running_balance, 2),
                    'profit_loss': 0,
                })

        # Process each transaction
        for idx, (trans_type, trans_date, trans_obj) in enumerate(all_trans):
            total_cif_usd = 0
            total_amount = 0

            # Get lines for this license only
            if license_type == 'DFIA':
                lines = trans_obj.lines.filter(sr_number__license_id=lic_id)

                for line in lines:
                    try:
                        if line.exc_rate and line.cif_inr:
                            exc_rate = float(line.exc_rate)
                            if exc_rate > 0:
                                cif_usd = float(line.cif_inr) / exc_rate
                            else:
                                cif_usd = float(line.cif_fc or 0)
                        else:
                            cif_usd = float(line.cif_fc or 0)
                    except (ValueError, TypeError, ZeroDivisionError):
                        cif_usd = 0

                    total_cif_usd += cif_usd
                    total_amount += float(line.amount_inr or 0)
            else:
                # For Incentive licenses, use incentive_lines
                incentive_line = trans_obj.incentive_lines.filter(incentive_license_id=lic_id).first()

                if incentive_line:
                    total_cif_usd = float(incentive_line.license_value or 0)
                    total_amount = float(incentive_line.amount_inr or 0)
                else:
                    # No line for this license in this trade, skip
                    continue

            # Skip if no value
            if total_cif_usd == 0 and total_amount == 0:
                continue

            # Calculate rate and update balance
            try:
                rate = total_amount / total_cif_usd if total_cif_usd != 0 else 0
            except (ZeroDivisionError, ValueError):
                rate = 0

            debit_cif = 0
            credit_cif = 0
            debit_amount = 0
            credit_amount = 0

            if trans_type in ['PURCHASE', 'COMMISSION_PURCHASE']:
                debit_cif = total_cif_usd
                debit_amount = total_amount
                running_balance += total_cif_usd
                total_purchase_cif += total_cif_usd
                total_purchase_amount += total_amount
            elif trans_type in ['SALE', 'COMMISSION_SALE']:
                credit_cif = total_cif_usd
                credit_amount = total_amount
                running_balance -= total_cif_usd
                total_sales_amount += total_amount

            # Calculate profit/loss for sales
            profit_loss = 0
            if trans_type in ['SALE', 'COMMISSION_SALE'] and total_purchase_cif > 0:
                avg_purchase_rate = total_purchase_amount / total_purchase_cif
                purchase_amount_for_this_sale = total_cif_usd * avg_purchase_rate
                sale_amount_inr = total_amount
                profit_loss = sale_amount_inr - purchase_amount_for_this_sale

            # Get company names
            from_company = trans_obj.from_company.name if trans_obj.from_company else 'Unknown'
            to_company = trans_obj.to_company.name if trans_obj.to_company else 'Unknown'

            if trans_type in ['PURCHASE', 'COMMISSION_PURCHASE']:
                particular = f"Purchase from {from_company}"
            else:
                particular = f"Sale to {to_company}"

            transactions.append({
                'date': trans_date,
                'type': trans_type.replace('_', ' ').title(),
                'particular': particular,
                'invoice_number': trans_obj.invoice_number or '-',
                'cif_usd': total_cif_usd,
                'debit_cif': debit_cif,
                'credit_cif': credit_cif,
                'rate': rate,
                'amount': total_amount,
                'debit_amount': debit_amount,
                'credit_amount': credit_amount,
                'balance': round(running_balance, 2),
                'profit_loss': round(profit_loss, 2),
            })

        return transactions

    except Exception as e:
        logger.error(f"Error fetching transactions for license {lic_id}: {e}")
        return []



def generate_detailed_licenses_pdf(licenses_data, query_params):
    """
    Generate a detailed PDF showing all transactions for each license with profit/loss.
    Groups by license and shows purchase/sale transactions chronologically.
    """
    buffer = BytesIO()
    doc = make_landscape_doc(buffer)

    elements = []
    styles = getSampleStyleSheet()

    title = Paragraph("LICENSE LEDGER - DETAILED TRANSACTIONS", make_title_style(styles))
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))

    if not licenses_data:
        no_data = Paragraph("<i>No licenses found</i>", styles['Normal'])
        elements.append(no_data)
    else:
        # Process each license
        for idx, lic_data in enumerate(licenses_data):
            if idx > 0:
                elements.append(PageBreak())  # New page for each license

            # License Header
            lic_number = lic_data.get('license_number', 'N/A')
            exporter = lic_data.get('exporter_name', 'N/A')
            lic_type = lic_data.get('license_type', 'N/A')

            header_text = f"License: {lic_number} | Exporter: {exporter} | Type: {lic_type}"
            lic_header = Paragraph(header_text, make_section_title_style(styles, spaceAfter=8))
            elements.append(lic_header)

            # License Info Table
            # Fetch transactions first (direction-aware company filter applied inside)
            company_id = query_params.get('company')
            transactions = get_license_transactions(lic_data, company_id=company_id)

            lic_date = lic_data.get('license_date')
            exp_date = lic_data.get('license_expiry_date')
            lic_date_str = lic_date.strftime('%d-%b-%Y') if lic_date else '-'
            exp_date_str = exp_date.strftime('%d-%b-%Y') if exp_date else '-'

            total_val = lic_data.get('total_value', 0)
            balance_val = lic_data.get('balance_value', 0)
            currency = lic_data.get('currency', 'USD')

            if company_id and transactions:
                purchase_amt = sum(t.get('debit_amount', 0) for t in transactions)
                sale_amt = sum(t.get('credit_amount', 0) for t in transactions)
                profit_loss = sale_amt - purchase_amt
            else:
                purchase_amt = lic_data.get('purchase_amount', 0)
                sale_amt = lic_data.get('sale_amount', 0)
                profit_loss = lic_data.get('profit_loss', 0)

            info_data = [
                ['License Date:', lic_date_str, 'Expiry Date:', exp_date_str],
                [f'Total Value ({currency}):', format_indian_number(total_val, 2),
                 f'Balance ({currency}):', format_indian_number(balance_val, 2)],
                ['Purchase Amt (INR):', format_indian_number(purchase_amt, 2),
                 'Sale Amt (INR):', format_indian_number(sale_amt, 2)],
            ]

            info_table = Table(info_data, colWidths=[1.5*inch, 2.2*inch, 1.5*inch, 2.2*inch])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
                ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#ecf0f1')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))

            elements.append(info_table)
            elements.append(Spacer(1, 0.15 * inch))

            # Profit/Loss Summary
            pl_color = colors.green if profit_loss >= 0 else colors.red
            pl_text = f"Profit: ₹{format_indian_number(profit_loss, 2)}" if profit_loss >= 0 else f"Loss: ₹{format_indian_number(abs(profit_loss), 2)}"

            pl_style = ParagraphStyle(
                '_DetailPLStyle',
                parent=styles['Normal'],
                fontSize=12,
                textColor=pl_color,
                fontName='Helvetica-Bold',
                alignment=TA_RIGHT,
            )

            pl_para = Paragraph(pl_text, pl_style)
            elements.append(pl_para)
            elements.append(Spacer(1, 0.15 * inch))

            if transactions:
                # Transaction table header
                txn_title = Paragraph(
                    "Transaction Details",
                    make_section_title_style(styles, fontSize=11, spaceAfter=6),
                )
                elements.append(txn_title)

                # Create transaction table with proper wrapping
                wrap_style = make_wrap_style(styles)

                txn_data = [[
                    'Date', 'Type', 'Particulars', 'Invoice No.',
                    'Debit CIF', 'Credit CIF', 'Balance',
                    'Debit Amt', 'Credit Amt', 'P/L'
                ]]

                for txn in transactions:
                    # Format values
                    date_str = txn['date'].strftime('%d-%b-%y') if txn.get('date') else '-'
                    txn_type = txn.get('type', '-')
                    particular = txn.get('particular', '-')
                    invoice = txn.get('invoice_number', '-')

                    debit_cif = txn.get('debit_cif', 0)
                    credit_cif = txn.get('credit_cif', 0)
                    balance = txn.get('balance', 0)
                    debit_amt = txn.get('debit_amount', 0)
                    credit_amt = txn.get('credit_amount', 0)
                    pl = txn.get('profit_loss', 0)

                    # Color code profit/loss
                    if pl != 0:
                        pl_para = pl_paragraph(pl, wrap_style)
                    else:
                        pl_para = '-'

                    # Wrap all text fields in Paragraph for proper text wrapping
                    txn_data.append([
                        Paragraph(date_str, wrap_style),
                        Paragraph(txn_type, wrap_style),
                        Paragraph(particular, wrap_style),
                        Paragraph(invoice, wrap_style),
                        Paragraph(format_indian_number(debit_cif, 2) if debit_cif > 0 else '-', wrap_style),
                        Paragraph(format_indian_number(credit_cif, 2) if credit_cif > 0 else '-', wrap_style),
                        Paragraph(format_indian_number(balance, 2), wrap_style),
                        Paragraph(format_indian_number(debit_amt, 2) if debit_amt > 0 else '-', wrap_style),
                        Paragraph(format_indian_number(credit_amt, 2) if credit_amt > 0 else '-', wrap_style),
                        pl_para
                    ])

                # Create table with expanded widths (landscape A4: ~10.5 inches available)
                txn_table = Table(txn_data, colWidths=[
                    0.7*inch,   # Date
                    0.8*inch,   # Type
                    2.2*inch,   # Particulars (expanded)
                    0.9*inch,   # Invoice No.
                    0.85*inch,  # Debit CIF
                    0.85*inch,  # Credit CIF
                    0.85*inch,  # Balance
                    0.95*inch,  # Debit Amt
                    0.95*inch,  # Credit Amt
                    0.85*inch   # P/L
                ], repeatRows=1)

                txn_table.setStyle(TableStyle(
                    make_header_table_style_commands(header_bg='#34495e', header_fontsize=7)
                    + make_data_grid_commands()
                    + [
                        ('ALIGN',  (0, 1), (3, -1), 'LEFT'),
                        ('ALIGN',  (4, 1), (-1, -1), 'RIGHT'),
                        ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                    ]
                ))

                elements.append(txn_table)
            else:
                no_txn = Paragraph("<i>No transactions found for this license</i>", styles['Normal'])
                elements.append(no_txn)

            elements.append(Spacer(1, 0.2 * inch))

    # ── Summary page ──────────────────────────────────────────────────────
    if licenses_data:
        elements.append(PageBreak())

        elements.append(Paragraph(
            "LICENSE PROFIT / LOSS SUMMARY",
            make_title_style(styles, fontSize=16, spaceAfter=14),
        ))
        elements.append(Spacer(1, 0.15 * inch))

        summary_header = [
            'License No.', 'License Date', 'Expiry Date', 'Type', 'Exporter',
            'CIF $ Purchase', 'CIF $ Sold', 'Balance $',
            'Purchase Amt (₹)', 'Sale Amt (₹)', 'P/L (₹)'
        ]

        summary_rows = [summary_header]
        total_purchase = 0
        total_sale = 0
        total_pl = 0
        total_cif_purchase = 0
        total_cif_sold = 0
        total_cif_balance = 0

        company_id_summary = query_params.get('company')

        for lic_data in licenses_data:
            txns = get_license_transactions(lic_data, company_id=company_id_summary)
            if company_id_summary and txns:
                pur = sum(t.get('debit_amount', 0) for t in txns)
                sal = sum(t.get('credit_amount', 0) for t in txns)
                pl  = sal - pur
            else:
                pur = lic_data.get('purchase_amount', 0)
                sal = lic_data.get('sale_amount', 0)
                pl  = lic_data.get('profit_loss', 0)

            cif_purchase = lic_data.get('total_value', 0) or 0
            cif_sold = lic_data.get('sold_value', 0) or 0
            cif_balance = lic_data.get('balance_value', 0) or 0
            currency = lic_data.get('currency', 'USD')

            total_purchase += pur
            total_sale     += sal
            total_pl       += pl
            total_cif_purchase += cif_purchase
            total_cif_sold     += cif_sold
            total_cif_balance  += cif_balance

            pl_color = 'green' if pl >= 0 else 'red'
            pl_sign  = '+' if pl >= 0 else ''
            pl_cell  = Paragraph(
                f'<font color="{pl_color}">{pl_sign}{format_indian_number(pl, 2)}</font>',
                ParagraphStyle('plcell', fontSize=7, fontName='Helvetica', alignment=1)
            )

            lic_date = lic_data.get('license_date')
            exp_date = lic_data.get('license_expiry_date')
            lic_date_str = lic_date.strftime('%d-%b-%Y') if lic_date else '-'
            exp_date_str = exp_date.strftime('%d-%b-%Y') if exp_date else '-'

            summary_rows.append([
                lic_data.get('license_number', '-'),
                lic_date_str,
                exp_date_str,
                lic_data.get('license_type', '-'),
                lic_data.get('exporter_name', '-'),
                f"{currency} {format_indian_number(cif_purchase, 2)}",
                f"{currency} {format_indian_number(cif_sold, 2)}",
                f"{currency} {format_indian_number(cif_balance, 2)}",
                format_indian_number(pur, 2),
                format_indian_number(sal, 2),
                pl_cell,
            ])

        # Totals row
        total_pl_color = 'green' if total_pl >= 0 else 'red'
        total_pl_sign  = '+' if total_pl >= 0 else ''
        total_pl_cell  = Paragraph(
            f'<font color="{total_pl_color}"><b>{total_pl_sign}{format_indian_number(total_pl, 2)}</b></font>',
            ParagraphStyle('tplcell', fontSize=7, fontName='Helvetica-Bold', alignment=1)
        )
        summary_rows.append([
            Paragraph('<b>TOTAL</b>', ParagraphStyle('tot', fontSize=7, fontName='Helvetica-Bold')),
            '', '', '', '',
            Paragraph(f'<b>{format_indian_number(total_cif_purchase, 2)}</b>', ParagraphStyle('tcp', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
            Paragraph(f'<b>{format_indian_number(total_cif_sold, 2)}</b>',     ParagraphStyle('tcs', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
            Paragraph(f'<b>{format_indian_number(total_cif_balance, 2)}</b>',  ParagraphStyle('tcb', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
            Paragraph(f'<b>{format_indian_number(total_purchase, 2)}</b>', ParagraphStyle('tp', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
            Paragraph(f'<b>{format_indian_number(total_sale, 2)}</b>',     ParagraphStyle('ts', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
            total_pl_cell,
        ])

        summary_table = Table(summary_rows, colWidths=[
            1.3*inch, 0.85*inch, 0.85*inch, 0.6*inch, 1.6*inch,
            1.0*inch, 1.0*inch, 1.0*inch,
            1.1*inch, 1.1*inch, 1.0*inch
        ], repeatRows=1)

        summary_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 7),
            ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, 0), 'MIDDLE'),
            # Data
            ('FONTNAME',   (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE',   (0, 1), (-1, -1), 7),
            ('ALIGN',      (5, 1), (-1, -1), 'RIGHT'),
            ('ALIGN',      (0, 1), (4, -1), 'LEFT'),
            ('VALIGN',     (0, 1), (-1, -1), 'MIDDLE'),
            # Highlight CIF $ columns
            ('BACKGROUND', (5, 1), (5, -2), colors.HexColor('#fdebd0')),
            ('BACKGROUND', (6, 1), (6, -2), colors.HexColor('#d5f4e6')),
            ('BACKGROUND', (7, 1), (7, -2), colors.HexColor('#e8f5e9')),
            ('FONTNAME',   (7, 1), (7, -2), 'Helvetica-Bold'),
            # Totals row
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
            # Grid
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ]))

        elements.append(summary_table)

    doc.build(elements)
    pdf_content = buffer.getvalue()
    buffer.close()
    return pdf_content



def generate_all_licenses_pdf(licenses_data, query_params):
    """
    Generate a PDF containing all licenses in a tabular format.
    """
    buffer = None
    try:
        buffer = BytesIO()

        doc = make_landscape_doc(buffer)

        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("LICENSE LEDGER - ALL LICENSES", make_title_style(styles)))

        # Add filter information
        license_type = query_params.get('license_type', 'ALL')
        active_only = query_params.get('active_only', 'true').lower() == 'true'

        filter_info = f"License Type: {license_type} | Status: {'Active Only' if active_only else 'All'} | Total: {len(licenses_data)} licenses"
        elements.append(Paragraph(filter_info, make_subtitle_style(styles)))
        elements.append(Spacer(1, 0.2 * inch))

        if not licenses_data:
            no_data = Paragraph("<i>No licenses found matching the criteria</i>", styles['Normal'])
            elements.append(no_data)
        else:
            wrap_style = make_wrap_style(styles)
            profit_style = ParagraphStyle('_ProfitStyle', parent=wrap_style, textColor=colors.green)
            loss_style = ParagraphStyle('_LossStyle', parent=wrap_style, textColor=colors.red)

            # Separate licenses into profit and loss groups
            profit_licenses = [lic for lic in licenses_data if lic.get('profit_loss', 0) >= 0]
            loss_licenses = [lic for lic in licenses_data if lic.get('profit_loss', 0) < 0]

            # Helper function to process table for a set of licenses
            def create_license_table(licenses_list, table_title):
                if not licenses_list:
                    return None, {}

                # Table header
                header = [[
                    'License No.',
                    'Type',
                    'Exporter',
                    'License Date',
                    'Expiry',
                    'Purchase\n($)',
                    'Sold\n($)',
                    'Balance\n($)',
                    'Purchase\nAmt (INR)',
                    'Sale\nAmt (INR)',
                    'P/L\n(INR)',
                    'Status'
                ]]

                table_data = header[:]
                no_purchase_rows = []
                negative_balance_rows = []

                for idx, license in enumerate(licenses_list):
                    row_num = idx + 1  # +1 for header

                    # Extract data
                    lic_date = license.get('license_date')
                    exp_date = license.get('license_expiry_date')
                    lic_date_str = lic_date.strftime('%d-%b-%y') if lic_date else '-'
                    exp_date_str = exp_date.strftime('%d-%b-%y') if exp_date else '-'

                    total_val = license.get('total_value', 0)
                    sold_val = license.get('sold_value', 0)
                    purchase_amt = license.get('purchase_amount', 0)
                    sale_amt = license.get('sale_amount', 0)
                    profit_loss = license.get('profit_loss', 0)
                    currency = license.get('currency', 'USD')
                    status = 'Active' if license.get('is_active', False) else 'Expired'

                    # Wrap exporter name - always use Paragraph for multi-line support
                    exporter_name = license.get('exporter_name') or 'N/A'
                    exporter_para = Paragraph(str(exporter_name), wrap_style)

                    # Calculate balance
                    purchase_usd = total_val
                    sold_usd = sold_val
                    calculated_balance = purchase_usd - sold_usd

                    # Format with Indian number system
                    if currency == 'USD':
                        purchase_str = f"${format_indian_number(purchase_usd, 2)}"
                        sold_str = f"${format_indian_number(sold_usd, 2)}"
                        balance_str = f"${format_indian_number(calculated_balance, 2)}"
                    else:
                        purchase_str = f"INR {format_indian_number(purchase_usd, 2)}"
                        sold_str = f"INR {format_indian_number(sold_usd, 2)}"
                        balance_str = f"INR {format_indian_number(calculated_balance, 2)}"

                    # Track special rows
                    if not purchase_amt or purchase_amt == 0:
                        no_purchase_rows.append(row_num)
                    if calculated_balance < 0:
                        negative_balance_rows.append(row_num)

                    # Wrap all monetary values in Paragraph for text wrapping
                    purchase_amt_str = f"INR {format_indian_number(purchase_amt, 2)}" if purchase_amt else 'No Purchase'
                    sale_amt_str = f"INR {format_indian_number(sale_amt, 2)}" if sale_amt else '-'
                    pl_str = f"INR {format_indian_number(profit_loss, 2)}"

                    # Use green for profit, red for loss
                    pl_paragraph_style = profit_style if profit_loss >= 0 else loss_style

                    # Ensure all values are strings before creating Paragraphs
                    license_number = str(license.get('license_number') or 'N/A')[:14]
                    license_type = str(license.get('license_type') or 'N/A')[:6]

                    table_data.append([
                        Paragraph(license_number, wrap_style),
                        Paragraph(license_type, wrap_style),
                        exporter_para,
                        Paragraph(str(lic_date_str), wrap_style),
                        Paragraph(str(exp_date_str), wrap_style),
                        Paragraph(str(purchase_str), wrap_style),
                        Paragraph(str(sold_str), wrap_style),
                        Paragraph(str(balance_str), wrap_style),
                        Paragraph(str(purchase_amt_str), wrap_style),
                        Paragraph(str(sale_amt_str), wrap_style),
                        Paragraph(str(pl_str), pl_paragraph_style),
                        Paragraph(str(status[:3]), wrap_style)
                    ])

                # Calculate totals for this group
                total_purchase_usd = sum(lic.get('total_value', 0) for lic in licenses_list if lic.get('currency') == 'USD')
                total_sold_usd = sum(lic.get('sold_value', 0) for lic in licenses_list if lic.get('currency') == 'USD')
                total_balance_usd = sum(lic.get('balance_value', 0) for lic in licenses_list if lic.get('currency') == 'USD')

                total_purchase_inr_val = sum(lic.get('total_value', 0) for lic in licenses_list if lic.get('currency') == 'INR')
                total_sold_inr_val = sum(lic.get('sold_value', 0) for lic in licenses_list if lic.get('currency') == 'INR')
                total_balance_inr_val = sum(lic.get('balance_value', 0) for lic in licenses_list if lic.get('currency') == 'INR')

                total_purchase_amt = sum(lic.get('purchase_amount', 0) for lic in licenses_list)
                total_sale_amt = sum(lic.get('sale_amount', 0) for lic in licenses_list)
                total_pl = sum(lic.get('profit_loss', 0) for lic in licenses_list)

                # Create bold style for total row
                total_style = ParagraphStyle(
                    'TotalStyle',
                    parent=wrap_style,
                    fontSize=7.5,
                    leading=9.5,
                    fontName='Helvetica-Bold',
                    wordWrap='CJK',
                    splitLongWords=True
                )

                # Create bold profit/loss styles for total row
                total_profit_style = ParagraphStyle(
                    'TotalProfitStyle',
                    parent=total_style,
                    textColor=colors.green
                )

                total_loss_style = ParagraphStyle(
                    'TotalLossStyle',
                    parent=total_style,
                    textColor=colors.red
                )

                # Format total values with Paragraph for multi-line support
                purchase_total_str = f"${format_indian_number(total_purchase_usd, 2)}" if total_purchase_usd else (f"INR {format_indian_number(total_purchase_inr_val, 2)}" if total_purchase_inr_val else '-')
                sold_total_str = f"${format_indian_number(total_sold_usd, 2)}" if total_sold_usd else (f"INR {format_indian_number(total_sold_inr_val, 2)}" if total_sold_inr_val else '-')
                balance_total_str = f"${format_indian_number(total_balance_usd, 2)}" if total_balance_usd else (f"INR {format_indian_number(total_balance_inr_val, 2)}" if total_balance_inr_val else '-')

                # Use green/red for total P/L
                total_pl_style = total_profit_style if total_pl >= 0 else total_loss_style

                # Add total row with Paragraphs
                table_data.append([
                    Paragraph('<b>TOTAL</b>', total_style),
                    '',
                    '',
                    '',
                    '',
                    Paragraph(f'<b>{purchase_total_str}</b>', total_style),
                    Paragraph(f'<b>{sold_total_str}</b>', total_style),
                    Paragraph(f'<b>{balance_total_str}</b>', total_style),
                    Paragraph(f'<b>INR {format_indian_number(total_purchase_amt, 2)}</b>', total_style),
                    Paragraph(f'<b>INR {format_indian_number(total_sale_amt, 2)}</b>', total_style),
                    Paragraph(f'<b>INR {format_indian_number(total_pl, 2)}</b>', total_pl_style),
                    ''
                ])

                return table_data, {'no_purchase': no_purchase_rows, 'negative_balance': negative_balance_rows, 'licenses': licenses_list, 'has_total_row': True}

            # Helper function to style and append a table
            def style_and_append_table(table_data, metadata, table_title, title_color):
                if not table_data:
                    return

                # Add section title
                elements.append(Paragraph(
                    table_title,
                    make_section_title_style(styles, color_hex=title_color),
                ))

                # Create table with appropriate column widths for landscape A4
                # Landscape A4 width: ~11 inches minus margins = ~10.5 inches available
                col_widths = [
                    0.9*inch,   # License No.
                    0.55*inch,  # Type
                    1.4*inch,   # Exporter (wider for multi-line)
                    0.7*inch,   # License Date
                    0.7*inch,   # Expiry
                    0.9*inch,   # Purchase ($)
                    0.9*inch,   # Sold ($)
                    0.9*inch,   # Balance ($)
                    0.85*inch,  # Purchase Amt (INR)
                    0.85*inch,  # Sale Amt (INR)
                    0.75*inch,  # P/L (INR)
                    0.5*inch    # Status
                ]
                table = Table(table_data, colWidths=col_widths, repeatRows=1)

                # Style the table
                no_purchase_rows = metadata.get('no_purchase', [])
                negative_balance_rows = metadata.get('negative_balance', [])
                licenses_list = metadata.get('licenses', [])

                table_style = [
                    # Header row
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

                    # Data rows
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('ALIGN', (0, 1), (2, -1), 'LEFT'),
                    ('ALIGN', (3, 1), (4, -1), 'CENTER'),
                    ('ALIGN', (5, 1), (-1, -1), 'RIGHT'),

                    # Grid and borders
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Align to top for multi-line
                    ('TOPPADDING', (0, 0), (-1, -1), 5),   # Increased padding
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ]

                # Check if table has total row
                has_total_row = metadata.get('has_total_row', False)
                total_row_idx = len(table_data) - 1 if has_total_row else -1

                # Alternate row colors and highlights
                for i in range(1, len(table_data)):
                    # Style total row differently
                    if has_total_row and i == total_row_idx:
                        table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#e8eaf6')))
                        table_style.append(('LINEABOVE', (0, i), (-1, i), 2, colors.HexColor('#34495e')))
                        table_style.append(('VALIGN', (0, i), (-1, i), 'TOP'))  # Top align for wrapped totals
                        # Note: Font styling handled by Paragraph objects
                        continue

                    if i % 2 == 0:
                        table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8f9fa')))

                    if i in negative_balance_rows:
                        table_style.append(('BACKGROUND', (7, i), (7, i), colors.HexColor('#d32f2f')))
                        table_style.append(('TEXTCOLOR', (7, i), (7, i), colors.whitesmoke))
                        table_style.append(('FONTNAME', (7, i), (7, i), 'Helvetica-Bold'))

                    if i in no_purchase_rows:
                        table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#ffebee')))
                        table_style.append(('TEXTCOLOR', (8, i), (8, i), colors.HexColor('#c62828')))
                        table_style.append(('FONTNAME', (8, i), (8, i), 'Helvetica-Bold'))

                    if i - 1 < len(licenses_list):
                        license = licenses_list[i - 1]
                        if not license.get('is_active', False) and i not in no_purchase_rows:
                            table_style.append(('TEXTCOLOR', (0, i), (-1, i), colors.HexColor('#999999')))

                        profit_loss = license.get('profit_loss', 0)
                        if profit_loss > 0:
                            table_style.append(('TEXTCOLOR', (10, i), (10, i), colors.HexColor('#2e7d32')))
                        elif profit_loss < 0:
                            table_style.append(('TEXTCOLOR', (10, i), (10, i), colors.HexColor('#d32f2f')))

                table.setStyle(TableStyle(table_style))
                elements.append(table)
                elements.append(Spacer(1, 0.3 * inch))

            # Create PROFIT licenses table
            if profit_licenses:
                profit_table_data, profit_metadata = create_license_table(profit_licenses, "PROFIT LICENSES")
                style_and_append_table(profit_table_data, profit_metadata, f"PROFIT LICENSES ({len(profit_licenses)} licenses)", '#2e7d32')

            # Create LOSS licenses table
            if loss_licenses:
                loss_table_data, loss_metadata = create_license_table(loss_licenses, "LOSS LICENSES")
                style_and_append_table(loss_table_data, loss_metadata, f"LOSS LICENSES ({len(loss_licenses)} licenses)", '#d32f2f')

            # Add summary section
            elements.append(Spacer(1, 0.3 * inch))

            # Calculate totals
            total_balance_dfia = sum(lic.get('balance_value', 0) for lic in licenses_data if lic.get('currency') == 'USD')
            total_balance_inr = sum(lic.get('balance_value', 0) for lic in licenses_data if lic.get('currency') == 'INR')
            total_purchase = sum(lic.get('purchase_amount', 0) for lic in licenses_data)
            total_sale = sum(lic.get('sale_amount', 0) for lic in licenses_data)
            total_profit_loss = sum(lic.get('profit_loss', 0) for lic in licenses_data)

            # Summary title
            elements.append(Paragraph(
                "SUMMARY",
                make_section_title_style(styles, fontSize=12, spaceAfter=8),
            ))

            # Summary data with Indian number format
            summary_data = [
                ['Total Licenses', 'Profit Licenses', 'Loss Licenses', 'Balance (USD)', 'Balance (INR)', 'Purchase (INR)', 'Sale (INR)', 'Net P/L (INR)'],
                [
                    str(len(licenses_data)),
                    str(len(profit_licenses)),
                    str(len(loss_licenses)),
                    f"${format_indian_number(total_balance_dfia, 2)}" if total_balance_dfia else '-',
                    f"INR {format_indian_number(total_balance_inr, 2)}" if total_balance_inr else '-',
                    f"INR {format_indian_number(total_purchase, 2)}",
                    f"INR {format_indian_number(total_sale, 2)}",
                    f"INR {format_indian_number(total_profit_loss, 2)}"
                ]
            ]

            summary_table = Table(summary_data, colWidths=[1*inch, 1*inch, 1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch])
            summary_table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ecf0f1')),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 9),
                ('ALIGN', (0, 1), (0, 1), 'CENTER'),
                ('ALIGN', (1, 1), (-1, 1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]

            # Color code profit/loss in summary
            if total_profit_loss > 0:
                summary_table_style.append(('TEXTCOLOR', (5, 1), (5, 1), colors.HexColor('#2e7d32')))
            elif total_profit_loss < 0:
                summary_table_style.append(('TEXTCOLOR', (5, 1), (5, 1), colors.HexColor('#d32f2f')))

            summary_table.setStyle(TableStyle(summary_table_style))
            elements.append(summary_table)

        # Footer
        append_generated_footer(elements, styles)

        # Build PDF
        doc.build(elements)

        pdf = buffer.getvalue()
        return pdf

    except Exception as e:
        logger.exception(f"Failed to generate licenses PDF: {e}")
        raise
    finally:
        if buffer:
            try:
                buffer.close()
            except Exception:
                pass



def generate_company_ledger_pdf(licenses_data, company_name, query_params):
    """Generate PDF for company-specific ledger."""
    buffer = None
    try:
        buffer = BytesIO()

        doc = make_landscape_doc(buffer)

        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph(
            f"COMPANY LEDGER - {company_name.upper()}",
            make_title_style(styles),
        ))

        # Filter info
        license_type = query_params.get('license_type', 'ALL')
        active_only = query_params.get('active_only', 'true').lower() == 'true'

        filter_info = f"License Type: {license_type} | Status: {'Active Only' if active_only else 'All'} | Total: {len(licenses_data)} licenses"
        elements.append(Paragraph(filter_info, make_subtitle_style(styles)))
        elements.append(Spacer(1, 0.3 * inch))

        # Table data
        table_data = [[
            'License No.',
            'Type',
            'Exporter',
            'Date',
            'Expiry',
            'Total Value',
            'Balance'
        ]]

        for lic in licenses_data:
            currency = 'USD' if lic.get('license_type') == 'DFIA' else 'INR'
            table_data.append([
                lic.get('license_number', '-'),
                lic.get('license_type', '-'),
                (lic.get('exporter_name', '-') or '-')[:25],
                lic.get('license_date', '-') if lic.get('license_date') else '-',
                lic.get('expiry_date', '-') if lic.get('expiry_date') else '-',
                f"{currency} {format_indian_number(lic.get('total_value', 0))}",
                f"{currency} {format_indian_number(lic.get('available_balance', 0))}"
            ])

        # Create table
        table = Table(table_data, colWidths=[90, 50, 150, 70, 70, 100, 100])
        table.setStyle(TableStyle(
            make_header_table_style_commands(header_bg='#4a5568', header_fontsize=10)
            + make_data_grid_commands(font_size=8)
            + [
                ('ALIGN',          (0, 0), (-1, -1), 'CENTER'),
                ('BOTTOMPADDING',  (0, 0), (-1, 0),  12),
                ('BACKGROUND',     (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
                ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
            ]
        ))

        elements.append(table)

        # Build PDF
        doc.build(elements)

        pdf = buffer.getvalue()
        return pdf

    except Exception as e:
        logger.exception(f"Failed to generate company ledger PDF: {e}")
        raise
    finally:
        if buffer:
            try:
                buffer.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Ledger-detail transaction builders
#
# Extracted from LicenseLedgerViewSet.ledger_detail so the viewset method
# becomes a thin coordinator.  Both functions return plain dicts — callers
# wrap them in Response().
# ---------------------------------------------------------------------------

def build_dfia_ledger_detail(license, company_id=None):
    """
    Build the DFIA ledger-detail payload for *license* (LicenseDetailsModel).

    Returns a dict ready for ``Response(…)``.

    *company_id* applies direction-aware filtering:
    - PURCHASE / COMMISSION_PURCHASE  → company must be the BUYER  (to_company)
    - SALE / COMMISSION_SALE          → company must be the SELLER (from_company)
    """
    from apps.trade.models import LicenseTrade
    from django.db.models import Q

    trades_query = LicenseTrade.objects.filter(
        license_type='DFIA',
        lines__sr_number__license=license,
    )

    if company_id:
        trades_query = trades_query.filter(
            Q(direction__in=['PURCHASE', 'COMMISSION_PURCHASE'], to_company_id=company_id)
            | Q(direction__in=['SALE', 'COMMISSION_SALE'], from_company_id=company_id)
        )

    trades = trades_query.prefetch_related(
        'lines__sr_number__items__sion_norm_class',
        'from_company',
        'to_company',
    ).distinct().order_by('invoice_date', 'id')

    transactions = []
    running_balance = 0
    total_purchase_cif = 0
    total_purchase_amount = 0
    total_sales_amount = 0
    company_purchase_cif: dict = {}
    company_purchase_amount: dict = {}

    all_trans = [
        (t.direction, t.invoice_date or timezone.now().date(), t)
        for t in trades
    ]
    all_trans.sort(key=lambda x: (x[0] not in ['PURCHASE', 'COMMISSION_PURCHASE'], x[1]))

    # Opening balance (no trades)
    if not all_trans and float(license.opening_balance or 0) > 0:
        opening_cif = float(license.opening_balance)
        running_balance = opening_cif
        total_purchase_cif = opening_cif
        transactions.append({
            'date': license.license_date,
            'type': 'OPENING',
            'particular': 'Opening Balance - Original DFIA License',
            'invoice_number': license.license_number,
            'cif_usd': opening_cif,
            'debit_cif': opening_cif,
            'credit_cif': 0,
            'rate': 0,
            'amount': 0,
            'debit_amount': 0,
            'credit_amount': 0,
            'balance': round(running_balance, 2),
            'profit_loss': 0,
        })

    for idx, (trans_type, trans_date, trans_obj) in enumerate(all_trans):
        total_cif_usd = 0
        total_amount = 0
        items_desc: list = []
        sion_norms: list = []
        qty_kg_total = 0.0

        for line in trans_obj.lines.all():
            if line.sr_number and line.sr_number.license_id != license.id:
                continue
            try:
                if line.exc_rate and line.cif_inr:
                    exc_rate = float(line.exc_rate)
                    cif_usd = float(line.cif_inr) / exc_rate if exc_rate > 0 else float(line.cif_fc or 0)
                else:
                    cif_usd = float(line.cif_fc or 0)
            except (ValueError, TypeError, ZeroDivisionError):
                cif_usd = 0

            total_cif_usd += cif_usd
            total_amount += float(line.amount_inr or 0)
            if line.sr_number:
                qty_kg_total += float(line.qty_kg or 0)
                for item in line.sr_number.items.all():
                    if item.name:
                        items_desc.append(item.name)
                    if item.sion_norm_class:
                        norm = item.sion_norm_class.norm_class
                        if norm and norm not in sion_norms:
                            sion_norms.append(norm)

        try:
            rate = total_amount / total_cif_usd if total_cif_usd > 0 else 0
        except (ZeroDivisionError, TypeError, ValueError):
            rate = 0

        if trans_type in ['PURCHASE', 'COMMISSION_PURCHASE']:
            running_balance += total_cif_usd
            total_purchase_cif += total_cif_usd
            total_purchase_amount += total_amount

            _buyer_id = trans_obj.to_company.id if trans_obj.to_company else None
            if _buyer_id and trans_type == 'PURCHASE':
                company_purchase_cif[_buyer_id] = company_purchase_cif.get(_buyer_id, 0) + total_cif_usd
                company_purchase_amount[_buyer_id] = company_purchase_amount.get(_buyer_id, 0) + total_amount

            is_commission = trans_type == 'COMMISSION_PURCHASE'
            txn_type = 'COMMISSION' if is_commission else 'PURCHASE'
            particular_prefix = 'Commission Paid to' if is_commission else 'Purchase DFIA -'
            _co = trans_obj.to_company

            if idx == 0 and not transactions and not is_commission:
                transactions.append({
                    'date': trans_date,
                    'type': 'OPENING',
                    'particular': f'Opening Balance - Purchase from {trans_obj.from_company.name if trans_obj.from_company else "N/A"}',
                    'invoice_number': trans_obj.invoice_number or '',
                    'cif_usd': total_cif_usd,
                    'debit_cif': total_cif_usd,
                    'credit_cif': 0,
                    'rate': round(rate, 2),
                    'amount': total_amount,
                    'debit_amount': total_amount,
                    'credit_amount': 0,
                    'balance': round(running_balance, 2),
                    'profit_loss': 0,
                    'company_id': _co.id if _co else None,
                    'company_name': _co.name if _co else 'N/A',
                    'trade_id': trans_obj.id,
                })
            else:
                transactions.append({
                    'date': trans_date,
                    'type': txn_type,
                    'particular': f'{particular_prefix} {trans_obj.from_company.name if trans_obj.from_company else "N/A"}',
                    'invoice_number': trans_obj.invoice_number or '',
                    'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                    'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                    'qty': qty_kg_total,
                    'cif_usd': total_cif_usd,
                    'debit_cif': total_cif_usd,
                    'credit_cif': 0,
                    'rate': round(rate, 2),
                    'amount': total_amount,
                    'debit_amount': total_amount,
                    'credit_amount': 0,
                    'balance': round(running_balance, 2),
                    'profit_loss': 0,
                    'company_id': _co.id if _co else None,
                    'company_name': _co.name if _co else 'N/A',
                    'trade_id': trans_obj.id,
                })

        elif trans_type in ['SALE', 'COMMISSION_SALE']:
            is_commission = trans_type == 'COMMISSION_SALE'
            _co = trans_obj.from_company

            if is_commission:
                running_balance += total_cif_usd
                total_purchase_amount += total_amount
                transactions.append({
                    'date': trans_date,
                    'type': 'COMMISSION',
                    'particular': f'Commission Paid to {trans_obj.to_company.name if trans_obj.to_company else "N/A"}',
                    'invoice_number': trans_obj.invoice_number or '',
                    'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                    'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                    'qty': qty_kg_total,
                    'cif_usd': total_cif_usd,
                    'debit_cif': total_cif_usd,
                    'credit_cif': 0,
                    'rate': round(rate, 2),
                    'amount': total_amount,
                    'debit_amount': total_amount,
                    'credit_amount': 0,
                    'balance': round(running_balance, 2),
                    'profit_loss': 0,
                    'company_id': _co.id if _co else None,
                    'company_name': _co.name if _co else 'N/A',
                    'trade_id': trans_obj.id,
                })
            else:
                running_balance -= total_cif_usd
                total_sales_amount += total_amount

                _seller_id = trans_obj.from_company.id if trans_obj.from_company else None
                _co_cif = company_purchase_cif.get(_seller_id, 0) if _seller_id else 0
                _co_amt = company_purchase_amount.get(_seller_id, 0) if _seller_id else 0
                if _co_cif > 0:
                    avg_rate = _co_amt / _co_cif
                    sale_profit_loss = round(total_amount - total_cif_usd * avg_rate, 2)
                elif total_purchase_cif > 0:
                    avg_rate = total_purchase_amount / total_purchase_cif
                    sale_profit_loss = round(total_amount - total_cif_usd * avg_rate, 2)
                else:
                    sale_profit_loss = round(total_amount, 2)

                transactions.append({
                    'date': trans_date,
                    'type': 'SALE',
                    'particular': f'DFIA Sale - {trans_obj.to_company.name if trans_obj.to_company else "N/A"}',
                    'invoice_number': trans_obj.invoice_number or '',
                    'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                    'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                    'qty': qty_kg_total,
                    'cif_usd': total_cif_usd,
                    'debit_cif': 0,
                    'credit_cif': total_cif_usd,
                    'rate': round(rate, 2),
                    'amount': total_amount,
                    'debit_amount': 0,
                    'credit_amount': total_amount,
                    'balance': round(running_balance, 2),
                    'profit_loss': sale_profit_loss,
                    'company_id': _co.id if _co else None,
                    'company_name': _co.name if _co else 'N/A',
                    'trade_id': trans_obj.id,
                })

    return {
        'license_id': license.id,
        'license_type': 'DFIA',
        'license_number': license.license_number,
        'license_date': license.license_date,
        'expiry_date': license.license_expiry_date,
        'exporter': license.exporter.name if license.exporter else '',
        'port': license.port.name if license.port else '',
        'total_value': total_purchase_cif,
        'available_balance': round(running_balance, 2),
        'db_balance': float(license.balance_cif or 0),
        'transactions': transactions,
    }


def build_incentive_ledger_detail(license, company_id=None):
    """
    Build the Incentive ledger-detail payload for *license* (IncentiveLicense).

    Returns a dict ready for ``Response(…)``.
    """
    from apps.trade.models import LicenseTrade
    from django.db.models import Q

    trades_query = LicenseTrade.objects.filter(
        license_type='INCENTIVE',
        incentive_lines__incentive_license=license,
    )

    if company_id:
        trades_query = trades_query.filter(
            Q(direction__in=['PURCHASE', 'COMMISSION_PURCHASE'], to_company_id=company_id)
            | Q(direction__in=['SALE', 'COMMISSION_SALE'], from_company_id=company_id)
        )

    trades = list(
        trades_query.prefetch_related(
            'incentive_lines__incentive_license',
            'from_company',
            'to_company',
        ).distinct()
    )
    trades.sort(key=lambda t: (
        t.direction not in ('PURCHASE', 'COMMISSION_PURCHASE'),
        t.invoice_date or timezone.now().date(),
        t.id,
    ))

    transactions = []
    running_balance = 0
    total_purchase_value = 0
    total_purchase_amount = 0
    total_sales_amount = 0
    is_first_transaction = True

    for trade in trades:
        license_line = next(
            (line for line in trade.incentive_lines.all() if line.incentive_license_id == license.id),
            None,
        )
        if not license_line:
            continue

        license_value = float(license_line.license_value or 0)
        rate_pct = float(license_line.rate_pct or 0)
        amount = float(license_line.amount_inr or 0)

        if trade.direction in ['PURCHASE', 'COMMISSION_PURCHASE']:
            running_balance += license_value
            total_purchase_value += license_value
            total_purchase_amount += amount

            is_commission = trade.direction == 'COMMISSION_PURCHASE'
            txn_type = 'COMMISSION' if is_commission else 'PURCHASE'
            particular_prefix = 'Commission Paid to' if is_commission else f'Purchase {license.license_type} -'
            _co = trade.to_company

            if is_first_transaction and not is_commission:
                transactions.append({
                    'date': trade.invoice_date or license.license_date,
                    'type': 'OPENING',
                    'particular': f'Opening Balance - Purchase from {trade.from_company.name if trade.from_company else "N/A"}',
                    'invoice_number': trade.invoice_number or '',
                    'license_value': license_value,
                    'debit_license_value': license_value,
                    'credit_license_value': 0,
                    'rate': round(rate_pct, 3),
                    'amount': amount,
                    'debit_amount': amount,
                    'credit_amount': 0,
                    'balance': round(running_balance, 2),
                    'profit_loss': 0,
                    'company_id': _co.id if _co else None,
                    'company_name': _co.name if _co else 'N/A',
                    'trade_id': trade.id,
                })
            else:
                transactions.append({
                    'date': trade.invoice_date or license.license_date,
                    'type': txn_type,
                    'particular': f'{particular_prefix} {trade.from_company.name if trade.from_company else "N/A"}',
                    'invoice_number': trade.invoice_number or '',
                    'license_value': license_value,
                    'debit_license_value': license_value,
                    'credit_license_value': 0,
                    'rate': round(rate_pct, 3),
                    'amount': amount,
                    'debit_amount': amount,
                    'credit_amount': 0,
                    'balance': round(running_balance, 2),
                    'profit_loss': 0,
                    'company_id': _co.id if _co else None,
                    'company_name': _co.name if _co else 'N/A',
                    'trade_id': trade.id,
                })
            is_first_transaction = False

        elif trade.direction in ['SALE', 'COMMISSION_SALE']:
            is_commission = trade.direction == 'COMMISSION_SALE'
            _co = trade.from_company

            if is_commission:
                running_balance += license_value
                total_purchase_amount += amount
                transactions.append({
                    'date': trade.invoice_date or timezone.now().date(),
                    'type': 'COMMISSION',
                    'particular': f'Commission Paid to {trade.to_company.name if trade.to_company else "N/A"}',
                    'invoice_number': trade.invoice_number or '',
                    'license_value': license_value,
                    'debit_license_value': license_value,
                    'credit_license_value': 0,
                    'rate': round(rate_pct, 3),
                    'amount': amount,
                    'debit_amount': amount,
                    'credit_amount': 0,
                    'balance': round(running_balance, 2),
                    'profit_loss': 0,
                    'company_id': _co.id if _co else None,
                    'company_name': _co.name if _co else 'N/A',
                    'trade_id': trade.id,
                })
            else:
                running_balance -= license_value
                total_sales_amount += amount

                if total_purchase_value > 0:
                    avg_rate = total_purchase_amount / total_purchase_value
                    sale_profit_loss = round(amount - license_value * avg_rate, 2)
                else:
                    sale_profit_loss = round(amount, 2)

                transactions.append({
                    'date': trade.invoice_date or timezone.now().date(),
                    'type': 'SALE',
                    'particular': f'{license.license_type} Sale - {trade.to_company.name if trade.to_company else "N/A"}',
                    'invoice_number': trade.invoice_number or '',
                    'license_value': license_value,
                    'debit_license_value': 0,
                    'credit_license_value': license_value,
                    'rate': round(rate_pct, 3),
                    'amount': amount,
                    'debit_amount': 0,
                    'credit_amount': amount,
                    'balance': round(running_balance, 2),
                    'profit_loss': sale_profit_loss,
                    'company_id': _co.id if _co else None,
                    'company_name': _co.name if _co else 'N/A',
                    'trade_id': trade.id,
                })
            is_first_transaction = False

    return {
        'license_id': license.id,
        'license_type': license.license_type,
        'license_number': license.license_number,
        'license_date': license.license_date,
        'expiry_date': license.license_expiry_date,
        'exporter': license.exporter.name if license.exporter else '',
        'port': license.port_code.name if license.port_code else '',
        'total_value': total_purchase_value,
        'available_balance': round(running_balance, 2),
        'db_balance': float(license.balance_value or 0),
        'transactions': transactions,
    }
