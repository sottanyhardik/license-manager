"""
License Purchase & Profit Report — view layer.

Per-license Purchase Cost (consolidated `LicensePurchase` invoices) vs
Debited CIF (period `RowDetails` DEBIT rows) vs Remaining CIF (live
balance), grouped Item -> License -> Norm -> Grand Total. See
`apps.license.services.purchase_profit_report.build_purchase_profit_report`
for the full business-rule rationale.

GET parameters:
    - from_date, to_date: required, 'YYYY-MM-DD'
    - norm: 'All' (default) / 'E1' / 'E5' / 'E126' / 'E132' / 'Others'
    - license_number: optional, case-insensitive contains search
    - exporter_id: optional
    - format / _format: 'json' (default) / 'excel' / 'pdf'
"""
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict

from django.http import HttpResponse, JsonResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

from apps.accounts.permissions import ReportPermission
from apps.license.services.purchase_profit_report import build_purchase_profit_report
from apps.license.views.item_report import _ExcelPassthroughRenderer

logger = logging.getLogger(__name__)


class LicensePurchaseProfitReportView(APIView):
    permission_classes = [ReportPermission]
    # Without this, DRF content negotiation raises NotAcceptable/404 for
    # ?format=excel / ?format=pdf before get() ever runs — same fix as
    # ItemPivotReportView / ItemReportView.
    renderer_classes = [JSONRenderer, _ExcelPassthroughRenderer]

    def get(self, request, *args, **kwargs):
        output_format = (
            request.GET.get('_format') or request.GET.get('format', 'json')
        ).lower()

        from_date_str = request.GET.get('from_date')
        to_date_str = request.GET.get('to_date')
        if not from_date_str or not to_date_str:
            return JsonResponse(
                {'error': 'from_date and to_date parameters are required',
                 'example': '?from_date=2026-01-01&to_date=2026-01-31'},
                status=400,
            )
        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse(
                {'error': 'from_date and to_date must be in YYYY-MM-DD format'},
                status=400,
            )

        norm = request.GET.get('norm', 'All')
        license_number = request.GET.get('license_number') or None
        exporter_id_raw = request.GET.get('exporter_id')
        exporter_id = None
        if exporter_id_raw:
            try:
                exporter_id = int(exporter_id_raw)
            except ValueError:
                return JsonResponse({'error': 'exporter_id must be an integer'}, status=400)

        try:
            report_data = build_purchase_profit_report(
                from_date, to_date, norm=norm, license_number=license_number, exporter_id=exporter_id,
            )
        except Exception as e:
            logger.exception("Error generating License Purchase & Profit Report")
            return JsonResponse({'error': str(e)}, status=500)

        if output_format == 'excel':
            try:
                return self.export_to_excel(report_data)
            except Exception as e:
                logger.exception("Error exporting License Purchase & Profit Report to Excel")
                return JsonResponse({'error': str(e)}, status=500)

        if output_format == 'pdf':
            try:
                return self.export_to_pdf(report_data, from_date, to_date)
            except Exception as e:
                logger.exception("Error exporting License Purchase & Profit Report to PDF")
                return JsonResponse({'error': str(e)}, status=500)

        return JsonResponse(report_data, safe=False)

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------
    def export_to_excel(self, report_data: Dict[str, Any]) -> HttpResponse:
        import openpyxl
        from openpyxl.cell.cell import MergedCell
        from openpyxl.styles import Alignment, Font, PatternFill

        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "Purchase & Profit Report"

        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
        section_font = Font(bold=True, size=12, color='1A1A1A')
        section_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
        center = Alignment(horizontal='center')

        max_cols = 8
        current_row = 1

        title_cell = worksheet.cell(row=current_row, column=1, value="License Purchase & Profit Report")
        worksheet.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=max_cols)
        title_cell.font = Font(bold=True, size=14)
        title_cell.alignment = center
        current_row += 2

        def write_section_header(text):
            nonlocal current_row
            cell = worksheet.cell(row=current_row, column=1, value=text)
            worksheet.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=max_cols)
            cell.font = section_font
            cell.fill = section_fill
            current_row += 1

        def write_table(headers, rows):
            nonlocal current_row
            for col_num, header in enumerate(headers, 1):
                cell = worksheet.cell(row=current_row, column=col_num, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center
            current_row += 1
            for row_data in rows:
                for col_num, value in enumerate(row_data, 1):
                    worksheet.cell(row=current_row, column=col_num, value=value)
                current_row += 1

        for norm_block in report_data['norms']:
            write_section_header(f"Norm: {norm_block['norm']}")
            current_row += 1

            write_section_header("License Summary")
            write_table(
                ['License Number', 'Exporter', 'Purchase Cost', 'Debited CIF', 'Remaining CIF',
                 'Allocated Purchase', 'Realized Profit', 'Profit %'],
                [
                    [lic['license_number'], lic['exporter'], lic['purchase_cost'], lic['debited_cif'],
                     lic['remaining_cif'], lic['allocated_purchase'], lic['realized_profit'], lic['profit_pct']]
                    for lic in norm_block['licenses']
                ],
            )
            current_row += 1

            write_section_header("Item-wise Profit")
            write_table(
                ['License Number', 'Item', 'Qty Debited', 'Debited CIF', 'Pct Share (%)',
                 'Allocated Purchase', 'Profit'],
                [
                    [it['license_number'], it['item'], it['qty_debited'], it['debited_cif'],
                     it['pct_share'], it['allocated_purchase'], it['profit']]
                    for it in norm_block['items']
                ],
            )
            current_row += 1

            write_section_header("Norm Summary")
            summary = norm_block['summary']
            write_table(
                ['Total Purchase', 'Total Debited CIF', 'Total Profit', 'Margin %'],
                [[summary['total_purchase'], summary['total_debited_cif'],
                  summary['total_profit'], summary['margin_pct']]],
            )
            current_row += 2

        write_section_header("Grand Summary")
        grand = report_data['grand_summary']
        write_table(
            ['Norm', 'Purchase', 'Debited CIF', 'Profit', 'Margin %'],
            [[row['norm'], row['purchase'], row['debited_cif'], row['profit'], row['margin_pct']]
             for row in grand['rows']]
            + [['TOTAL', grand['total']['purchase'], grand['total']['debited_cif'],
                grand['total']['profit'], grand['total']['margin_pct']]],
        )

        # Auto-size columns.
        for col_idx in range(1, max_cols + 1):
            max_length = 0
            column_letter = openpyxl.utils.get_column_letter(col_idx)
            for row in worksheet.iter_rows(min_col=col_idx, max_col=col_idx):
                for cell in row:
                    if isinstance(cell, MergedCell):
                        continue
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except (TypeError, AttributeError):
                        pass
            worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 10), 50)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="license_purchase_profit_report.xlsx"'
        workbook.save(response)
        return response

    # ------------------------------------------------------------------
    # PDF export
    # ------------------------------------------------------------------
    def export_to_pdf(self, report_data: Dict[str, Any], from_date, to_date) -> HttpResponse:
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        from shared.pdf.builders import (
            append_generated_footer,
            format_indian_number,
            make_data_grid_commands,
            make_header_table_style_commands,
            make_landscape_doc,
            make_section_title_style,
            make_subtitle_style,
            make_title_style,
            pl_paragraph,
        )

        buffer = BytesIO()
        doc = make_landscape_doc(buffer)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("License Purchase & Profit Report", make_title_style(styles)))
        elements.append(
            Paragraph(f"Period: {from_date.isoformat()} to {to_date.isoformat()}", make_subtitle_style(styles))
        )
        elements.append(Spacer(1, 0.2 * inch))

        wrap_style = styles["Normal"]

        for norm_block in report_data['norms']:
            elements.append(
                Paragraph(f"Norm: {norm_block['norm']}", make_section_title_style(styles))
            )

            elements.append(Paragraph("License Summary", styles["Heading3"]))
            lic_header = ['License Number', 'Exporter', 'Purchase Cost', 'Debited CIF',
                          'Remaining CIF', 'Allocated Purchase', 'Realized Profit', 'Profit %']
            lic_data = [lic_header]
            for lic in norm_block['licenses']:
                lic_data.append([
                    lic['license_number'], lic['exporter'],
                    format_indian_number(lic['purchase_cost']),
                    format_indian_number(lic['debited_cif']),
                    format_indian_number(lic['remaining_cif']),
                    format_indian_number(lic['allocated_purchase']),
                    pl_paragraph(lic['realized_profit'], wrap_style),
                    f"{lic['profit_pct']:.2f}",
                ])
            lic_table = Table(lic_data, repeatRows=1)
            lic_table.setStyle(TableStyle(
                make_header_table_style_commands() + make_data_grid_commands()
            ))
            elements.append(lic_table)
            elements.append(Spacer(1, 0.15 * inch))

            elements.append(Paragraph("Item-wise Profit", styles["Heading3"]))
            item_header = ['License Number', 'Item', 'Qty Debited', 'Debited CIF',
                          'Pct Share (%)', 'Allocated Purchase', 'Profit']
            item_data = [item_header]
            for it in norm_block['items']:
                item_data.append([
                    it['license_number'], it['item'],
                    format_indian_number(it['qty_debited'], 3),
                    format_indian_number(it['debited_cif']),
                    f"{it['pct_share']:.2f}",
                    format_indian_number(it['allocated_purchase']),
                    pl_paragraph(it['profit'], wrap_style),
                ])
            item_table = Table(item_data, repeatRows=1)
            item_table.setStyle(TableStyle(
                make_header_table_style_commands() + make_data_grid_commands()
            ))
            elements.append(item_table)
            elements.append(Spacer(1, 0.15 * inch))

            elements.append(Paragraph("Norm Summary", styles["Heading3"]))
            summary = norm_block['summary']
            summary_data = [
                ['Total Purchase', 'Total Debited CIF', 'Total Profit', 'Margin %'],
                [
                    format_indian_number(summary['total_purchase']),
                    format_indian_number(summary['total_debited_cif']),
                    pl_paragraph(summary['total_profit'], wrap_style),
                    f"{summary['margin_pct']:.2f}",
                ],
            ]
            summary_table = Table(summary_data)
            summary_table.setStyle(TableStyle(
                make_header_table_style_commands() + make_data_grid_commands()
            ))
            elements.append(summary_table)
            elements.append(Spacer(1, 0.3 * inch))

        elements.append(Paragraph("Grand Summary", make_section_title_style(styles)))
        grand = report_data['grand_summary']
        grand_data = [['Norm', 'Purchase', 'Debited CIF', 'Profit', 'Margin %']]
        for row in grand['rows']:
            grand_data.append([
                row['norm'],
                format_indian_number(row['purchase']),
                format_indian_number(row['debited_cif']),
                pl_paragraph(row['profit'], wrap_style),
                f"{row['margin_pct']:.2f}",
            ])
        grand_data.append([
            'TOTAL',
            format_indian_number(grand['total']['purchase']),
            format_indian_number(grand['total']['debited_cif']),
            pl_paragraph(grand['total']['profit'], wrap_style, bold=True),
            f"{grand['total']['margin_pct']:.2f}",
        ])
        grand_table = Table(grand_data, repeatRows=1)
        grand_table.setStyle(TableStyle(
            make_header_table_style_commands() + make_data_grid_commands()
            + [('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')]
        ))
        elements.append(grand_table)

        append_generated_footer(elements, styles)

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="license_purchase_profit_report.pdf"'
        return response
