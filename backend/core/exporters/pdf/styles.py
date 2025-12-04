"""
PDF styling utilities and predefined styles.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import TableStyle


class PDFStyles:
    """Collection of commonly used PDF styles."""

    def __init__(self):
        """Initialize with ReportLab sample styles."""
        self.base_styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        """Create custom paragraph styles."""
        # Title style
        self.title = ParagraphStyle(
            'CustomTitle',
            parent=self.base_styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        # Subtitle style
        self.subtitle = ParagraphStyle(
            'CustomSubtitle',
            parent=self.base_styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        # Section heading style
        self.section_heading = ParagraphStyle(
            'SectionHeading',
            parent=self.base_styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=8,
            spaceBefore=12,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )

        # Header info style (for key-value pairs)
        self.header_label = ParagraphStyle(
            'HeaderLabel',
            parent=self.base_styles['Normal'],
            fontSize=9,
            leading=11,
            fontName='Helvetica-Bold',
            textColor=colors.black
        )

        self.header_value = ParagraphStyle(
            'HeaderValue',
            parent=self.base_styles['Normal'],
            fontSize=9,
            leading=11,
            fontName='Helvetica',
            textColor=colors.black
        )

        # Table text styles
        self.table_header = ParagraphStyle(
            'TableHeader',
            parent=self.base_styles['Normal'],
            fontSize=8,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.white
        )

        self.table_cell = ParagraphStyle(
            'TableCell',
            parent=self.base_styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_LEFT
        )

        self.table_cell_number = ParagraphStyle(
            'TableCellNumber',
            parent=self.base_styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_RIGHT
        )

        # Normal body text
        self.body = ParagraphStyle(
            'CustomBody',
            parent=self.base_styles['Normal'],
            fontSize=10,
            leading=12,
            alignment=TA_JUSTIFY
        )

        # Small text
        self.small = ParagraphStyle(
            'SmallText',
            parent=self.base_styles['Normal'],
            fontSize=8,
            leading=10
        )


def get_default_styles() -> PDFStyles:
    """
    Get default PDF styles.
    
    Returns:
        PDFStyles instance
    """
    return PDFStyles()


def create_table_style_basic() -> TableStyle:
    """
    Create a basic table style with grid and headers.
    
    Returns:
        TableStyle instance
    """
    return TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])


def create_table_style_striped() -> TableStyle:
    """
    Create a table style with alternating row colors.
    
    Returns:
        TableStyle instance
    """
    return TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        # Data rows
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])


def create_table_style_header_info() -> TableStyle:
    """
    Create a table style for header information (key-value pairs).
    
    Returns:
        TableStyle instance
    """
    return TableStyle([
        # Label columns (0, 2)
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#ecf0f1')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),

        # All cells
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ])


def apply_alternating_row_colors(
        style: TableStyle,
        start_row: int = 1,
        color1: colors.Color = colors.white,
        color2: colors.Color = colors.HexColor('#f8f9fa')
) -> TableStyle:
    """
    Apply alternating row colors to existing table style.
    
    Args:
        style: Existing TableStyle
        start_row: Row to start alternating (usually 1 to skip header)
        color1: First color (odd rows)
        color2: Second color (even rows)
        
    Returns:
        Modified TableStyle
    """
    # Add alternating colors (will be applied to specific rows when table is created)
    commands = list(style._cmds)

    # Add instruction for alternating rows
    # Note: This needs to be applied dynamically based on actual row count
    commands.append(('ROWBACKGROUNDS', (0, start_row), (-1, -1), [color1, color2]))

    return TableStyle(commands)


def highlight_total_row(style: TableStyle, row_index: int = -1) -> TableStyle:
    """
    Highlight a total/summary row.
    
    Args:
        style: Existing TableStyle
        row_index: Row index to highlight (-1 for last row)
        
    Returns:
        Modified TableStyle
    """
    commands = list(style._cmds)

    commands.extend([
        ('BACKGROUND', (0, row_index), (-1, row_index), colors.HexColor('#d4edda')),
        ('FONTNAME', (0, row_index), (-1, row_index), 'Helvetica-Bold'),
        ('LINEABOVE', (0, row_index), (-1, row_index), 1.5, colors.black),
    ])

    return TableStyle(commands)


def create_minimal_table_style() -> TableStyle:
    """
    Create a minimal table style (no grid, only borders).
    
    Returns:
        TableStyle instance
    """
    return TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),

        # Data rows
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),

        # Only horizontal lines
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
