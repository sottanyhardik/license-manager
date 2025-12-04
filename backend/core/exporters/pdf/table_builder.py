"""
PDF table building utilities.
"""

from dataclasses import dataclass
from typing import List, Optional, Any, Dict

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph

from core.utils.decimal_utils import to_decimal, format_decimal
from .styles import create_table_style_basic, PDFStyles


@dataclass
class TableConfig:
    """Configuration for table generation."""
    col_widths: Optional[List[float]] = None
    repeat_rows: int = 1  # Number of header rows to repeat on each page
    style: Optional[TableStyle] = None
    wrap_text: bool = True  # Whether to wrap text in Paragraphs


class PDFTableBuilder:
    """
    Helper class for building PDF tables with common patterns.
    """

    def __init__(self, config: Optional[TableConfig] = None, styles: Optional[PDFStyles] = None):
        """
        Initialize table builder.
        
        Args:
            config: Table configuration
            styles: PDF styles to use
        """
        self.config = config or TableConfig()
        self.styles = styles or PDFStyles()
        self.data = []

    def add_header_row(self, headers: List[str]) -> 'PDFTableBuilder':
        """
        Add header row to table.
        
        Args:
            headers: List of header strings
            
        Returns:
            Self for chaining
        """
        if self.config.wrap_text:
            header_cells = [Paragraph(str(h), self.styles.table_header) for h in headers]
        else:
            header_cells = list(headers)

        self.data.append(header_cells)
        return self

    def add_data_row(self, row: List[Any], number_columns: Optional[List[int]] = None) -> 'PDFTableBuilder':
        """
        Add data row to table.
        
        Args:
            row: List of cell values
            number_columns: Indices of columns that should be right-aligned (for numbers)
            
        Returns:
            Self for chaining
        """
        if self.config.wrap_text:
            cells = []
            for idx, cell in enumerate(row):
                if number_columns and idx in number_columns:
                    cells.append(Paragraph(str(cell), self.styles.table_cell_number))
                else:
                    cells.append(Paragraph(str(cell), self.styles.table_cell))
            self.data.append(cells)
        else:
            self.data.append(list(row))

        return self

    def add_rows(self, rows: List[List[Any]], number_columns: Optional[List[int]] = None) -> 'PDFTableBuilder':
        """
        Add multiple data rows.
        
        Args:
            rows: List of rows
            number_columns: Indices of columns that should be right-aligned
            
        Returns:
            Self for chaining
        """
        for row in rows:
            self.add_data_row(row, number_columns)
        return self

    def add_total_row(self, row: List[Any], label: str = "Total") -> 'PDFTableBuilder':
        """
        Add a total/summary row.
        
        Args:
            row: Row data
            label: Label for first column (default: "Total")
            
        Returns:
            Self for chaining
        """
        total_row = [label] + list(row[1:])

        if self.config.wrap_text:
            cells = []
            for cell in total_row:
                cells.append(Paragraph(f"<b>{cell}</b>", self.styles.table_cell))
            self.data.append(cells)
        else:
            self.data.append(total_row)

        return self

    def build(self) -> Table:
        """
        Build the table.
        
        Returns:
            ReportLab Table instance
        """
        if not self.data:
            raise ValueError("No data added to table")

        # Create table
        table = Table(
            self.data,
            colWidths=self.config.col_widths,
            repeatRows=self.config.repeat_rows
        )

        # Apply style
        if self.config.style:
            table.setStyle(self.config.style)
        else:
            table.setStyle(create_table_style_basic())

        return table

    def reset(self) -> 'PDFTableBuilder':
        """
        Reset builder to create a new table.
        
        Returns:
            Self for chaining
        """
        self.data = []
        return self


def create_simple_table(
        headers: List[str],
        rows: List[List[Any]],
        col_widths: Optional[List[float]] = None,
        style: Optional[TableStyle] = None
) -> Table:
    """
    Create a simple table with headers and data rows.
    
    Args:
        headers: Header row
        rows: Data rows
        col_widths: Column widths in inches
        style: Table style (uses default if None)
        
    Returns:
        ReportLab Table instance
    """
    builder = PDFTableBuilder(config=TableConfig(col_widths=col_widths, style=style))
    builder.add_header_row(headers)
    builder.add_rows(rows)
    return builder.build()


def create_key_value_table(
        data: Dict[str, Any],
        col_widths: Optional[List[float]] = None,
        style: Optional[TableStyle] = None
) -> Table:
    """
    Create a key-value table (2 columns).
    
    Args:
        data: Dictionary of key-value pairs
        col_widths: Column widths (defaults to [2, 4] inches)
        style: Table style
        
    Returns:
        ReportLab Table instance
    """
    if col_widths is None:
        col_widths = [2 * inch, 4 * inch]

    rows = [[key, value] for key, value in data.items()]

    table = Table(rows, colWidths=col_widths)

    if style:
        table.setStyle(style)
    else:
        # Default style for key-value tables
        default_style = TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ])
        table.setStyle(default_style)

    return table


def create_info_header_table(
        info_data: List[List[str]],
        col_widths: Optional[List[float]] = None
) -> Table:
    """
    Create an information header table (typically 4 columns: label, value, label, value).
    
    Args:
        info_data: List of rows, each with 4 elements
        col_widths: Column widths (defaults to [1.5, 3, 1.5, 3] inches)
        
    Returns:
        ReportLab Table instance
    """
    if col_widths is None:
        col_widths = [1.5 * inch, 3 * inch, 1.5 * inch, 3 * inch]

    table = Table(info_data, colWidths=col_widths)

    style = TableStyle([
        # Label columns
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

    table.setStyle(style)
    return table


def format_currency_cell(value: Any, decimals: int = 2) -> str:
    """
    Format a value as currency for table cells.
    
    Args:
        value: Numeric value
        decimals: Number of decimal places
        
    Returns:
        Formatted string
    """
    dec_value = to_decimal(value)
    return format_decimal(dec_value, decimals)


def format_quantity_cell(value: Any, decimals: int = 3) -> str:
    """
    Format a value as quantity for table cells.
    
    Args:
        value: Numeric value
        decimals: Number of decimal places
        
    Returns:
        Formatted string
    """
    dec_value = to_decimal(value)
    return format_decimal(dec_value, decimals)


def calculate_column_widths(
        total_width: float,
        proportions: List[float]
) -> List[float]:
    """
    Calculate column widths based on proportions.
    
    Args:
        total_width: Total available width
        proportions: List of proportions (e.g., [1, 2, 1] for 25%, 50%, 25%)
        
    Returns:
        List of column widths
    """
    total_proportion = sum(proportions)
    return [total_width * (p / total_proportion) for p in proportions]
