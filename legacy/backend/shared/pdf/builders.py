"""
Shared PDF building utilities for the License Manager.

This module provides generic, reusable helpers for building ReportLab PDFs.
It intentionally imports ONLY from the standard library, reportlab, and other
third-party packages — never from any apps.* path — to avoid circular imports.

Public API
----------
format_indian_number(num, decimals=2)
make_landscape_doc(buffer, **kwargs)
make_title_style(styles, **kwargs)
make_subtitle_style(styles, **kwargs)
make_wrap_style(styles, **kwargs)
make_profit_loss_style(styles, *, color)
make_section_title_style(styles, **kwargs)
make_header_table_style_commands()
make_data_grid_commands()
append_generated_footer(elements, styles)
pl_color_name(value)
pl_paragraph(value, style, decimals=2, prefix="")
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


# ---------------------------------------------------------------------------
# Numeric formatting
# ---------------------------------------------------------------------------

def format_indian_number(num, decimals: int = 2) -> str:
    """
    Format *num* using the Indian numbering system (lakhs / crores).

    Examples::

        format_indian_number(1_00_00_000)    -> '1,00,00,000.00'
        format_indian_number(1234.5, 0)      -> '1,234'
        format_indian_number(-500.25)        -> '-500.25'
        format_indian_number(None)           -> '0'
    """
    if num is None:
        return "0"

    is_negative = num < 0
    num = abs(num)

    if decimals > 0:
        formatted = f"{{:,.{decimals}f}}".format(num)
        parts = formatted.split(".")
        integer_part = parts[0].replace(",", "")
        decimal_part = parts[1] if len(parts) > 1 else "0" * decimals
    else:
        integer_part = str(int(num))
        decimal_part = None

    if len(integer_part) <= 3:
        result = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups: list[str] = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        groups.reverse()
        result = ",".join(groups) + "," + last_three

    if decimal_part is not None:
        result = f"{result}.{decimal_part}"

    return f"-{result}" if is_negative else result


# ---------------------------------------------------------------------------
# Document creation
# ---------------------------------------------------------------------------

def make_landscape_doc(
    buffer: BytesIO,
    *,
    right_margin: float = 30,
    left_margin: float = 30,
    top_margin: float = 40,
    bottom_margin: float = 40,
) -> SimpleDocTemplate:
    """
    Return a landscape-A4 :class:`SimpleDocTemplate` with standard margins.

    Parameters mirror the ``rightMargin`` / ``leftMargin`` / … kwargs of
    ``SimpleDocTemplate`` but use underscored names and sensible defaults.
    """
    return SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )


# ---------------------------------------------------------------------------
# Paragraph style factories
# ---------------------------------------------------------------------------

def make_title_style(styles, **overrides) -> ParagraphStyle:
    """
    Large, centred, dark title (Helvetica-Bold 18 pt).

    Pass keyword overrides to adjust individual attributes, e.g.::

        make_title_style(styles, fontSize=20)
    """
    kwargs = dict(
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    kwargs.update(overrides)
    return ParagraphStyle("_SharedTitle", **kwargs)


def make_subtitle_style(styles, **overrides) -> ParagraphStyle:
    """
    Centred subtitle (Helvetica 10 pt, grey).
    """
    kwargs = dict(
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    kwargs.update(overrides)
    return ParagraphStyle("_SharedSubtitle", **kwargs)


def make_wrap_style(styles, **overrides) -> ParagraphStyle:
    """
    Small (7 pt) word-wrapping style for table cells.
    """
    kwargs = dict(
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        wordWrap="CJK",
        splitLongWords=True,
    )
    kwargs.update(overrides)
    return ParagraphStyle("_SharedWrap", **kwargs)


def make_section_title_style(styles, color_hex: str = "#2c3e50", **overrides) -> ParagraphStyle:
    """
    Heading-2-sized section title (Helvetica-Bold 14 pt).
    """
    kwargs = dict(
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor(color_hex),
        spaceAfter=10,
        fontName="Helvetica-Bold",
    )
    kwargs.update(overrides)
    return ParagraphStyle("_SharedSectionTitle", **kwargs)


def make_profit_loss_style(styles, *, positive: bool, **overrides) -> ParagraphStyle:
    """
    Coloured paragraph style for profit (green) or loss (red) cells.
    """
    base = make_wrap_style(styles)
    kwargs = dict(
        parent=base,
        textColor=colors.green if positive else colors.red,
    )
    kwargs.update(overrides)
    return ParagraphStyle("_PLStyle", **kwargs)


# ---------------------------------------------------------------------------
# TableStyle command sequences
# ---------------------------------------------------------------------------

def make_header_table_style_commands(
    header_bg: str = "#2c3e50",
    header_fg: str = "#FFFFFF",
    header_fontsize: int = 8,
) -> list:
    """
    Return a list of TableStyle commands for a standard dark-header row.

    Combine with additional commands before passing to ``TableStyle()``.

    Example::

        style = TableStyle(
            make_header_table_style_commands() + make_data_grid_commands()
        )
    """
    return [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.HexColor(header_fg)),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), header_fontsize),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",     (0, 0), (-1, 0), "MIDDLE"),
    ]


def make_data_grid_commands(
    *,
    font_size: int = 7,
    padding: int = 4,
    grid_color: str = "#808080",
) -> list:
    """
    Return TableStyle commands for data rows: Helvetica, grey grid, padding.
    """
    grey = colors.HexColor(grid_color)
    return [
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), font_size),
        ("GRID",          (0, 0), (-1, -1), 0.5, grey),
        ("TOPPADDING",    (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("LEFTPADDING",   (0, 0), (-1, -1), padding),
        ("RIGHTPADDING",  (0, 0), (-1, -1), padding),
    ]


def make_alternating_row_commands(n_data_rows: int, even_color: str = "#f8f9fa") -> list:
    """
    Return ``BACKGROUND`` commands that produce alternating row colours for
    *n_data_rows* data rows (row indices 1 … n_data_rows).
    """
    bg = colors.HexColor(even_color)
    commands = []
    for i in range(1, n_data_rows + 1):
        if i % 2 == 0:
            commands.append(("BACKGROUND", (0, i), (-1, i), bg))
    return commands


# ---------------------------------------------------------------------------
# Footer helper
# ---------------------------------------------------------------------------

def append_generated_footer(elements: list, styles) -> None:
    """
    Append a centred italic "Generated on: …" footer paragraph to *elements*.
    """
    footer_style = ParagraphStyle(
        "_Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(
        Paragraph(
            f"<i>Generated on: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}</i>",
            footer_style,
        )
    )


# ---------------------------------------------------------------------------
# Profit/loss cell helpers
# ---------------------------------------------------------------------------

def pl_color_name(value: float) -> str:
    """Return ``'green'`` or ``'red'`` depending on sign of *value*."""
    return "green" if value >= 0 else "red"


def pl_paragraph(
    value: float,
    wrap_style: ParagraphStyle,
    *,
    decimals: int = 2,
    prefix: str = "",
    bold: bool = False,
) -> Paragraph:
    """
    Return a colour-coded profit/loss ``Paragraph`` suitable for a table cell.

    ``prefix`` is prepended inside the colour tag (e.g. ``"+"`` for positives).
    """
    color = pl_color_name(value)
    sign = "+" if value >= 0 else ""
    text = f"{prefix}{sign}{format_indian_number(value, decimals)}"
    tag = f"<font color='{color}'>"
    if bold:
        tag_inner = f"<b>{text}</b>"
    else:
        tag_inner = text
    return Paragraph(f"<font color='{color}'>{tag_inner}</font>", wrap_style)
