"""
PDF Coordinate Finder Helper Script

This script helps you find the exact (x, y) coordinates for placing text on a PDF template.
Run this script and click on the PDF to find coordinates.

Usage:
    python pdf_coordinate_finder.py path/to/template.pdf
"""

import logging
import sys
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

logger = logging.getLogger(__name__)


def create_coordinate_grid(output_path):
    """Create a PDF with coordinate grid overlay"""
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # Draw vertical lines every 50 points
    for x in range(0, int(width), 50):
        c.drawString(x, 10, str(x))
        c.line(x, 0, x, height)

    # Draw horizontal lines every 50 points
    for y in range(0, int(height), 50):
        c.drawString(10, y, str(y))
        c.line(0, y, width, y)

    c.save()
    logger.info("Grid overlay created at: %s", output_path)
    logger.info("Page size: %s x %s", width, height)
    logger.info("To find coordinates: Open the grid PDF, find where you want to place text, "
                "read x from bottom axis, read y from left axis. Note: (0,0) is at bottom-left corner.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_coordinate_grid("coordinate_grid.pdf")
    logger.info("Current field positions in aro.py:")
    logger.info("""
    fields = {
        'company': (150, 720),
        'company_address_1': (150, 705),
        'company_address_2': (150, 690),
        'license': (560, 565),
        'license_date': (180, 541),
        'v_allotment_usd': (415, 541),
        'exporter_name': (270, 518),
    }
    """)
