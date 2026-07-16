"""
PDF generation utilities and helpers.

This module provides utilities for generating PDFs including:
- Number to words conversion (Indian numbering system)
- PDF style builders for tables
- Base invoice PDF generator class
- Company logo loading utilities
- Common PDF formatting helpers
"""

import logging
import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Table, TableStyle
from PIL import Image as PILImage

logger = logging.getLogger(__name__)


# =============================================================================
# Number to Words Conversion
# =============================================================================

def num_to_words_indian(amount: int | float | str) -> str:
    """
    Convert number to Indian rupees words.

    Uses Indian numbering system: ones, tens, hundreds, thousands, lakhs, crores.

    Args:
        amount: Numeric amount to convert (decimals are truncated)

    Returns:
        String representation in words

    Examples:
        >>> num_to_words_indian(1234567)
        'Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven'
        >>> num_to_words_indian(0)
        'Zero'
        >>> num_to_words_indian(100.50)
        'One Hundred'
    """
    try:
        # Remove decimals for word conversion
        whole_amount = int(float(amount))

        # Conversion logic for Indian numbering system
        ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
        teens = [
            'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen',
            'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'
        ]
        tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

        if whole_amount == 0:
            return 'Zero'

        def convert_below_thousand(n: int) -> str:
            """Convert numbers below 1000 to words"""
            if n == 0:
                return ''
            elif n < 10:
                return ones[n]
            elif n < 20:
                return teens[n - 10]
            elif n < 100:
                return tens[n // 10] + (' ' + ones[n % 10] if n % 10 != 0 else '')
            else:
                return (
                    ones[n // 100] + ' Hundred' +
                    (' ' + convert_below_thousand(n % 100) if n % 100 != 0 else '')
                )

        def convert_indian(n: int) -> str:
            """Convert number using Indian numbering system"""
            if n < 1000:
                return convert_below_thousand(n)

            crore = n // 10000000
            n %= 10000000
            lakh = n // 100000
            n %= 100000
            thousand = n // 1000
            n %= 1000

            result = []
            if crore > 0:
                result.append(convert_below_thousand(crore) + ' Crore')
            if lakh > 0:
                result.append(convert_below_thousand(lakh) + ' Lakh')
            if thousand > 0:
                result.append(convert_below_thousand(thousand) + ' Thousand')
            if n > 0:
                result.append(convert_below_thousand(n))

            return ' '.join(result)

        return convert_indian(whole_amount)
    except Exception:
        logger.exception("Failed to convert number to words: %s", amount)
        return str(amount)


# =============================================================================
# PDF Style Builders
# =============================================================================

class PDFStyleBuilder:
    """
    Builder class for creating consistent PDF table styles.

    Provides methods for creating common table styles with consistent formatting.

    Usage:
        builder = PDFStyleBuilder()
        header_style = builder.header_style(colors.HexColor('#336699'))
        data_style = builder.data_rows_style()
        total_style = builder.total_row_style()
        combined = builder.combine_styles(header_style, data_style, total_style)
        table.setStyle(TableStyle(combined))
    """

    @staticmethod
    def header_style(
        bg_color: colors.Color = colors.lightgrey,
        font_size: int = 9,
        font_name: str = 'Helvetica-Bold',
        text_color: colors.Color = colors.black
    ) -> list[tuple]:
        """
        Create table header row style.

        Args:
            bg_color: Background color for header
            font_size: Font size for header text
            font_name: Font name for header text
            text_color: Text color for header

        Returns:
            List of style tuples for TableStyle
        """
        return [
            ('BACKGROUND', (0, 0), (-1, 0), bg_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), text_color),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), font_size),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ]

    @staticmethod
    def data_rows_style(
        font_size: int = 9,
        font_name: str = 'Helvetica',
        padding: int = 4,
        valign: str = 'MIDDLE'
    ) -> list[tuple]:
        """
        Create table data rows style.

        Args:
            font_size: Font size for data rows
            font_name: Font name for data rows
            padding: Padding for cells
            valign: Vertical alignment

        Returns:
            List of style tuples for TableStyle
        """
        return [
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), font_size),
            ('VALIGN', (0, 1), (-1, -1), valign),
            ('TOPPADDING', (0, 0), (-1, -1), padding),
            ('BOTTOMPADDING', (0, 0), (-1, -1), padding),
            ('LEFTPADDING', (0, 0), (-1, -1), padding),
            ('RIGHTPADDING', (0, 0), (-1, -1), padding),
        ]

    @staticmethod
    def total_row_style(
        font_size: int = 10,
        font_name: str = 'Helvetica-Bold',
        bg_color: colors.Color | None = None
    ) -> list[tuple]:
        """
        Create table total/summary row style.

        Args:
            font_size: Font size for total row
            font_name: Font name for total row
            bg_color: Optional background color for total row

        Returns:
            List of style tuples for TableStyle
        """
        styles = [
            ('FONTNAME', (0, -1), (-1, -1), font_name),
            ('FONTSIZE', (0, -1), (-1, -1), font_size),
        ]

        if bg_color:
            styles.append(('BACKGROUND', (0, -1), (-1, -1), bg_color))

        return styles

    @staticmethod
    def grid_style(
        line_width: float = 0.5,
        line_color: colors.Color = colors.black
    ) -> list[tuple]:
        """
        Create table grid/border style.

        Args:
            line_width: Width of grid lines
            line_color: Color of grid lines

        Returns:
            List of style tuples for TableStyle
        """
        return [
            ('GRID', (0, 0), (-1, -1), line_width, line_color),
            ('BOX', (0, 0), (-1, -1), line_width, line_color),
        ]

    @staticmethod
    def combine_styles(*style_groups: list[tuple]) -> list[tuple]:
        """
        Combine multiple style groups into one.

        Args:
            *style_groups: Variable number of style lists to combine

        Returns:
            Combined list of style tuples

        Example:
            combined = PDFStyleBuilder.combine_styles(
                header_style,
                data_style,
                total_style,
                grid_style
            )
        """
        combined = []
        for group in style_groups:
            combined.extend(group)
        return combined


# =============================================================================
# Logo and Image Loading
# =============================================================================

def load_company_logo(
    company,
    max_width: float = 1.5 * inch,
    max_height: float = 0.75 * inch
) -> Image | None:
    """
    Load and resize company logo maintaining aspect ratio.

    Args:
        company: Company model instance with logo field
        max_width: Maximum width for logo (in reportlab units)
        max_height: Maximum height for logo (in reportlab units)

    Returns:
        reportlab.platypus.Image object or None if logo not available

    Example:
        logo_img = load_company_logo(company)
        if logo_img:
            elements.append(logo_img)
    """
    if not company:
        logger.info("No company provided")
        return None

    if not hasattr(company, 'logo') or not company.logo:
        logger.info("Company %s has no logo", company.name)
        return None

    try:
        logo_path = company.logo.path
        logger.info("Attempting to load logo from: %s", logo_path)

        if not os.path.exists(logo_path):
            logger.warning("Logo file does not exist at path: %s", logo_path)
            return None

        # Get image dimensions to maintain aspect ratio
        with PILImage.open(logo_path) as pil_img:
            img_width, img_height = pil_img.size
        aspect = img_height / float(img_width)

        # Calculate size maintaining aspect ratio
        if aspect > (max_height / max_width):
            # Height is limiting factor
            display_height = max_height
            display_width = max_height / aspect
        else:
            # Width is limiting factor
            display_width = max_width
            display_height = max_width * aspect

        logo_img = Image(logo_path, width=display_width, height=display_height)
        logger.info("Logo loaded successfully: %sx%s", display_width, display_height)
        return logo_img

    except Exception:
        logger.exception("Failed to load logo")
        return None


def load_company_signature(
    company,
    width: float = 1.3 * inch,
    height: float = 0.7 * inch
) -> Image | None:
    """
    Load company signature image.

    Args:
        company: Company model instance with signature field
        width: Width for signature image
        height: Height for signature image

    Returns:
        reportlab.platypus.Image object or None if signature not available
    """
    if not company or not hasattr(company, 'signature') or not company.signature:
        return None

    try:
        sig_path = company.signature.path
        if os.path.exists(sig_path):
            return Image(sig_path, width=width, height=height)
    except Exception:
        logger.exception("Failed to load signature")
    return None


def load_company_stamp(
    company,
    max_size: float = 1.0 * inch
) -> Image | None:
    """
    Load company stamp image with aspect ratio preservation.

    Args:
        company: Company model instance with stamp field
        max_size: Maximum width/height for stamp

    Returns:
        reportlab.platypus.Image object or None if stamp not available
    """
    if not company or not hasattr(company, 'stamp') or not company.stamp:
        return None

    try:
        stamp_path = company.stamp.path
        if not os.path.exists(stamp_path):
            return None

        # Get original stamp dimensions
        with PILImage.open(stamp_path) as pil_stamp:
            stamp_width, stamp_height = pil_stamp.size

        # Use original aspect ratio
        aspect = stamp_height / float(stamp_width)

        if aspect > 1:
            # Taller than wide
            display_height = min(max_size, stamp_height)
            display_width = display_height / aspect
        else:
            # Wider than tall or square
            display_width = min(max_size, stamp_width)
            display_height = display_width * aspect

        return Image(stamp_path, width=display_width, height=display_height)
    except Exception:
        logger.exception("Failed to load stamp")
    return None


# =============================================================================
# Common Paragraph Styles
# =============================================================================

def create_paragraph_styles():
    """
    Create common paragraph styles for PDFs.

    Returns:
        Dictionary of ParagraphStyle objects

    Example:
        styles = create_paragraph_styles()
        title = Paragraph('<b>Invoice</b>', styles['title'])
        header = Paragraph('Company Name', styles['header'])
    """
    base_styles = getSampleStyleSheet()

    return {
        'title': ParagraphStyle(
            'CustomTitle',
            parent=base_styles['Normal'],
            fontSize=16,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=10
        ),
        'header': ParagraphStyle(
            'CustomHeader',
            parent=base_styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            spaceAfter=6
        ),
        'subheader': ParagraphStyle(
            'CustomSubHeader',
            parent=base_styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            spaceAfter=4
        ),
        'normal': ParagraphStyle(
            'CustomNormal',
            parent=base_styles['Normal'],
            fontSize=14,
            alignment=TA_LEFT
        ),
        'right_align': ParagraphStyle(
            'CustomRightAlign',
            parent=base_styles['Normal'],
            fontSize=14,
            alignment=TA_RIGHT
        ),
        'center': ParagraphStyle(
            'CustomCenter',
            parent=base_styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER
        ),
        'bold_right': ParagraphStyle(
            'CustomBoldRight',
            parent=base_styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT,
            wordWrap='LTR',
            splitLongWords=False
        ),
        'italic': ParagraphStyle(
            'CustomItalic',
            parent=base_styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Oblique',
            alignment=TA_LEFT
        ),
        'footer': ParagraphStyle(
            'CustomFooter',
            parent=base_styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER
        )
    }


# =============================================================================
# Color Utilities
# =============================================================================

def parse_company_color(color_value: str | None, default: colors.Color = colors.black) -> colors.Color:
    """
    Parse company color from hex string.

    Args:
        color_value: Hex color string (with or without #)
        default: Default color if parsing fails

    Returns:
        reportlab.lib.colors.Color object

    Example:
        color = parse_company_color(company.bill_colour, colors.blue)
    """
    if not color_value:
        return default

    try:
        color_str = color_value.strip()
        if not color_str.startswith('#'):
            color_str = '#' + color_str
        return colors.HexColor(color_str)
    except Exception:
        logger.warning("Failed to parse color %r", color_value, exc_info=True)
        return default


# =============================================================================
# Base Invoice PDF Generator
# =============================================================================

class InvoicePDFGenerator:
    """
    Base class for generating invoice PDFs.

    Provides common functionality for creating invoice-style PDFs with headers,
    line items, totals, and footers.

    Usage:
        class BillOfSupplyPDF(InvoicePDFGenerator):
            def generate(self, trade):
                buffer = BytesIO()
                doc = self.create_document(buffer)
                elements = []

                # Add logo and title
                elements.extend(self.create_header(trade.from_company, 'Bill of Supply'))

                # Add invoice details
                elements.append(self.create_invoice_header(trade))

                # Add line items
                elements.append(self.create_items_table(trade))

                # Build PDF
                doc.build(elements)
                buffer.seek(0)
                return buffer
    """

    def __init__(self, pagesize=A4, margins=None):
        """
        Initialize PDF generator.

        Args:
            pagesize: Page size (default A4)
            margins: Dict with 'top', 'bottom', 'left', 'right' keys (in points)
        """
        self.pagesize = pagesize
        self.margins = margins or {
            'top': 20,
            'bottom': 15,
            'left': 20,
            'right': 20
        }
        self.styles = create_paragraph_styles()
        self.style_builder = PDFStyleBuilder()

    def create_document(self, buffer: BytesIO):
        """Create SimpleDocTemplate with configured margins"""
        from reportlab.platypus import SimpleDocTemplate

        return SimpleDocTemplate(
            buffer,
            pagesize=self.pagesize,
            rightMargin=self.margins['right'],
            leftMargin=self.margins['left'],
            topMargin=self.margins['top'],
            bottomMargin=self.margins['bottom']
        )

    def get_page_width(self) -> float:
        """Get usable page width (pagesize - margins)"""
        return self.pagesize[0] - self.margins['left'] - self.margins['right']

    def create_header(self, company, title: str) -> list:
        """
        Create header with logo and title.

        Args:
            company: Company model instance
            title: Title text (e.g., 'Bill of Supply')

        Returns:
            List of flowable elements
        """
        elements = []
        page_width = self.get_page_width()

        logo_img = load_company_logo(company)

        if logo_img:
            # Create table with logo on left, title in center
            logo_title_table = Table([
                [logo_img, Paragraph(f'<b>{title}</b>', self.styles['title']), '']
            ], colWidths=[page_width * 0.25, page_width * 0.5, page_width * 0.25])

            logo_title_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(logo_title_table)
        else:
            # Just title without logo
            elements.append(Paragraph(f'<b>{title}</b>', self.styles['title']))

        return elements

    def create_signature_section(self, company, include_signature: bool = True) -> Table:
        """
        Create signature section with signature and stamp.

        Args:
            company: Company model instance
            include_signature: Whether to include signature/stamp images

        Returns:
            Table with signature section
        """
        page_width = self.get_page_width()
        sig_rows = []

        if include_signature and company:
            sig_img = load_company_signature(company)
            stamp_img = load_company_stamp(company)

            # Place signature and stamp side by side
            if sig_img and stamp_img:
                sig_stamp_table = Table(
                    [[sig_img, stamp_img]],
                    colWidths=[1.4 * inch, 1.1 * inch]
                )
                sig_stamp_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ]))
                sig_rows.append([sig_stamp_table])
            elif sig_img:
                sig_rows.append([sig_img])
            elif stamp_img:
                sig_rows.append([stamp_img])
            else:
                # No images, add spacing
                sig_rows.append([Paragraph('<br/><br/>', self.styles['normal'])])
        else:
            sig_rows.append([Paragraph('<br/><br/>', self.styles['normal'])])

        # Add "Authorised Signatory"
        sig_rows.append([
            Paragraph('<b>Authorised Signatory</b>', self.styles['center'])
        ])

        # Create signature table
        sig_table = Table(sig_rows, colWidths=[page_width * 0.35])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (0, 0), 'TOP'),
            ('VALIGN', (0, 1), (0, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0, colors.white),
        ]))

        return sig_table

    def format_currency(self, amount: int | float, decimals: int = 2) -> str:
        """Format currency with Indian numbering system"""
        return f"{float(amount):,.{decimals}f}"

    def format_date(self, date_obj, format_str: str = '%d-%b-%y') -> str:
        """Format date object to string"""
        if date_obj:
            return date_obj.strftime(format_str)
        return ''
