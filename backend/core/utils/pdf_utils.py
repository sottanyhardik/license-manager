"""
Shared PDF export utilities for creating professional business-level reports.
"""
from datetime import datetime
from io import BytesIO

from django.http import HttpResponse

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class BusinessPDFExporter:
    """
    Professional PDF exporter with consistent styling and layout.
    """

    # Color scheme - Professional black theme
    PRIMARY_COLOR = colors.black
    SECONDARY_COLOR = colors.black
    ACCENT_COLOR = colors.HexColor('#4b5563')  # Gray
    HEADER_BG = colors.HexColor('#f1f5f9')  # Light gray
    STRIPE_COLOR = colors.HexColor('#f8fafc')  # Very light gray
    BORDER_COLOR = colors.HexColor('#cbd5e1')  # Gray border

    def __init__(self, title, filename_prefix, orientation='landscape'):
        """
        Initialize PDF exporter.

        Args:
            title: Document title
            filename_prefix: Prefix for the filename
            orientation: 'landscape' or 'portrait'
        """
        self.title = title
        self.filename_prefix = filename_prefix
        self.orientation = orientation
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles for consistent formatting."""
        # Title style
        self.title_style = ParagraphStyle(
            'BusinessTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=self.PRIMARY_COLOR,
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        # Subtitle style
        self.subtitle_style = ParagraphStyle(
            'BusinessSubtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=self.SECONDARY_COLOR,
            spaceAfter=8,
            spaceBefore=12,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )

        # Company header style
        self.company_style = ParagraphStyle(
            'CompanyHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=6,
            spaceBefore=6,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            backColor=self.HEADER_BG,
            leftIndent=6,
            rightIndent=6
        )

        # Section header style
        self.section_style = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=self.SECONDARY_COLOR,
            spaceAfter=4,
            spaceBefore=8,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )

        # Footer style
        self.footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )

    def create_pdf_response(self):
        """Create HTTP response for PDF download."""
        response = HttpResponse(content_type='application/pdf')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{self.filename_prefix}_{timestamp}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    def create_document(self, buffer):
        """
        Create SimpleDocTemplate with professional margins.

        Args:
            buffer: BytesIO buffer

        Returns:
            SimpleDocTemplate instance
        """
        pagesize = landscape(A4) if self.orientation == 'landscape' else A4

        return SimpleDocTemplate(
            buffer,
            pagesize=pagesize,
            topMargin=0.25 * inch,
            bottomMargin=0.25 * inch,
            leftMargin=0.2 * inch,
            rightMargin=0.2 * inch
        )

    def add_title(self, elements, subtitle=None):
        """
        Add professional title section to the document.

        Args:
            elements: List of elements to add to
            subtitle: Optional subtitle text
        """
        elements.append(Paragraph(self.title, self.title_style))

        if subtitle:
            elements.append(Paragraph(subtitle, self.subtitle_style))

        # Add timestamp
        timestamp_text = f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
        timestamp_style = ParagraphStyle(
            'Timestamp',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=16
        )
        elements.append(Paragraph(timestamp_text, timestamp_style))

    def add_company_header(self, elements, company_name):
        """
        Add company section header.

        Args:
            elements: List of elements to add to
            company_name: Name of the company
        """
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Paragraph(f"  {company_name}", self.company_style))
        elements.append(Spacer(1, 0.05 * inch))

    def add_section_header(self, elements, section_title):
        """
        Add section header.

        Args:
            elements: List of elements to add to
            section_title: Title of the section
        """
        elements.append(Paragraph(section_title, self.section_style))

    def create_table(self, data, col_widths=None, repeating_rows=1, wrap_text=True):
        """
        Create a professionally styled table.

        Args:
            data: 2D list of table data
            col_widths: List of column widths (optional)
            repeating_rows: Number of header rows to repeat on each page
            wrap_text: Whether to wrap text in cells

        Returns:
            Table object with professional styling
        """
        # Convert long text to Paragraphs for wrapping if needed
        if wrap_text:
            wrapped_data = []
            cell_style = ParagraphStyle(
                'CellText',
                parent=self.styles['Normal'],
                fontSize=8,
                leading=10,
                textColor=colors.black,
                wordWrap='CJK'
            )
            for i, row in enumerate(data):
                wrapped_row = []
                for j, cell in enumerate(row):
                    if i == 0:  # Header row - keep as is
                        wrapped_row.append(cell)
                    else:
                        # Wrap long text in Paragraph
                        if isinstance(cell, str) and len(cell) > 15:
                            wrapped_row.append(Paragraph(cell, cell_style))
                        else:
                            wrapped_row.append(cell)
                wrapped_data.append(wrapped_row)
            data = wrapped_data

        table = Table(data, colWidths=col_widths, repeatRows=repeating_rows, splitByRow=True)

        # Base table style with improved styling for directors - clean and light
        table_style = [
            # Header row styling - light professional background
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eaf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('TOPPADDING', (0, 0), (-1, 0), 7),
            ('LEFTPADDING', (0, 0), (-1, 0), 4),
            ('RIGHTPADDING', (0, 0), (-1, 0), 4),

            # Data rows styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING', (0, 1), (-1, -1), 4),
            ('RIGHTPADDING', (0, 1), (-1, -1), 4),

            # Grid and borders - light clean lines
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#9e9e9e')),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#7986cb')),

            # Alternating row colors - subtle
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
        ]

        table.setStyle(TableStyle(table_style))
        return table

    def apply_number_column_alignment(self, table_style_commands, data, number_columns):
        """
        Apply right alignment to number columns.

        Args:
            table_style_commands: List of style commands to append to
            data: Table data (to determine row count)
            number_columns: List of column indices that contain numbers
        """
        for col_idx in number_columns:
            table_style_commands.append(
                ('ALIGN', (col_idx, 1), (col_idx, len(data) - 1), 'RIGHT')
            )

    def create_summary_table(self, summary_data):
        """
        Create a summary/totals table with professional styling.

        Args:
            summary_data: 2D list of summary data

        Returns:
            Table object for summary
        """
        table = Table(summary_data)

        table_style = [
            ('BACKGROUND', (0, 0), (-1, -1), self.HEADER_BG),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), self.PRIMARY_COLOR),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 1.5, self.PRIMARY_COLOR),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]

        table.setStyle(TableStyle(table_style))
        return table

    def add_page_break(self, elements):
        """Add a page break."""
        elements.append(PageBreak())

    def add_spacer(self, elements, height_inches=0.1):
        """
        Add vertical spacing.

        Args:
            elements: List of elements
            height_inches: Height in inches
        """
        elements.append(Spacer(1, height_inches * inch))

    @staticmethod
    def format_number(value, decimals=2, use_comma=True):
        """
        Format number for display in PDF using Indian number format (12,34,567.89).

        Args:
            value: Number to format
            decimals: Number of decimal places
            use_comma: Whether to use comma separators

        Returns:
            Formatted string in Indian number format
        """
        try:
            num = float(value)

            if not use_comma:
                if decimals == 0:
                    return f"{int(num)}"
                else:
                    return f"{num:.{decimals}f}"

            # Split into integer and decimal parts
            if decimals == 0:
                integer_part = str(int(num))
                decimal_part = ""
            else:
                formatted = f"{num:.{decimals}f}"
                parts = formatted.split('.')
                integer_part = parts[0]
                decimal_part = f".{parts[1]}"

            # Handle negative numbers
            is_negative = integer_part.startswith('-')
            if is_negative:
                integer_part = integer_part[1:]

            # Apply Indian number format: last 3 digits, then groups of 2
            if len(integer_part) <= 3:
                formatted_int = integer_part
            else:
                # Get last 3 digits
                last_three = integer_part[-3:]
                remaining = integer_part[:-3]

                # Group remaining digits in pairs from right to left
                groups = []
                while remaining:
                    if len(remaining) <= 2:
                        groups.append(remaining)
                        break
                    groups.append(remaining[-2:])
                    remaining = remaining[:-2]

                # Reverse groups and join with commas
                groups.reverse()
                formatted_int = ','.join(groups) + ',' + last_three

            # Add negative sign back if needed
            if is_negative:
                formatted_int = '-' + formatted_int

            return formatted_int + decimal_part

        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_date(date_value, format_string='%d-%m-%Y'):
        """
        Format date for display in PDF.

        Args:
            date_value: Date object or string
            format_string: Desired format string

        Returns:
            Formatted date string
        """
        if not date_value:
            return '--'

        try:
            if isinstance(date_value, str):
                return date_value
            return date_value.strftime(format_string)
        except (AttributeError, ValueError):
            return str(date_value)


def create_pdf_exporter(title, filename_prefix, orientation='landscape'):
    """
    Factory function to create a BusinessPDFExporter instance.

    Args:
        title: Document title
        filename_prefix: Prefix for the filename
        orientation: 'landscape' or 'portrait'

    Returns:
        BusinessPDFExporter instance or None if reportlab not available
    """
    if not REPORTLAB_AVAILABLE:
        return None

    return BusinessPDFExporter(title, filename_prefix, orientation)
