"""Generate a coordinate-grid PDF for positioning ReportLab output."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path("coordinate_grid.pdf")
DEFAULT_GRID_SPACING = 50


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def create_coordinate_grid(
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    *,
    grid_spacing: int = DEFAULT_GRID_SPACING,
    overwrite: bool = False,
) -> Path:
    """Create a PDF with an A4 coordinate grid overlay."""
    if grid_spacing <= 0:
        raise ValueError("grid_spacing must be a positive integer")

    destination = Path(output_path).expanduser()
    if destination.exists() and destination.is_dir():
        raise IsADirectoryError(f"{destination} is a directory")
    if destination.exists() and not overwrite:
        raise FileExistsError(f"{destination} already exists; pass --overwrite to replace it")
    if not destination.parent.exists():
        raise FileNotFoundError(f"Output directory does not exist: {destination.parent}")

    c = canvas.Canvas(str(destination), pagesize=A4)
    width, height = A4

    for x in range(0, int(width), grid_spacing):
        c.drawString(x, 10, str(x))
        c.line(x, 0, x, height)

    for y in range(0, int(height), grid_spacing):
        c.drawString(10, y, str(y))
        c.line(0, y, width, y)

    c.save()
    logger.info("Grid overlay created at: %s", destination)
    logger.info("Page size: %s x %s", width, height)
    logger.info(
        "To find coordinates: Open the grid PDF, find where you want to place text, "
        "read x from bottom axis, read y from left axis. Note: (0,0) is at bottom-left corner."
    )
    return destination


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an A4 PDF coordinate grid for ReportLab template positioning.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=DEFAULT_OUTPUT_PATH,
        type=Path,
        help=f"Output PDF path. Defaults to {DEFAULT_OUTPUT_PATH}.",
    )
    parser.add_argument(
        "--grid-spacing",
        default=DEFAULT_GRID_SPACING,
        type=_positive_int,
        help=f"Grid spacing in PDF points. Defaults to {DEFAULT_GRID_SPACING}.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output file if it already exists.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args(argv)
    create_coordinate_grid(
        args.output,
        grid_spacing=args.grid_spacing,
        overwrite=args.overwrite,
    )
    logger.info("Current field positions in aro.py:")
    logger.info(
        """
    fields = {
        'company': (150, 720),
        'company_address_1': (150, 705),
        'company_address_2': (150, 690),
        'license': (560, 565),
        'license_date': (180, 541),
        'v_allotment_usd': (415, 541),
        'exporter_name': (270, 518),
    }
    """
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
