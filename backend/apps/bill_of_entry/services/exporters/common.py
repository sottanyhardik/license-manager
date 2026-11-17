"""Shared constants/helpers for the BOE exporters (moved verbatim from api/views_export.py)."""
from decimal import Decimal

from django.http import HttpResponse

try:
    import openpyxl  # noqa: F401
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import reportlab  # noqa: F401
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

EXPORT_FORMAT_PDF = 'pdf'
EXPORT_FORMAT_XLSX = 'xlsx'
EXPORT_FORMAT_PORT_XLSX = 'port_xlsx'
SUPPORTED_EXPORT_FORMATS = {EXPORT_FORMAT_PDF, EXPORT_FORMAT_XLSX, EXPORT_FORMAT_PORT_XLSX}


def _text_response(message, status_code):
    return HttpResponse(message, status=status_code, content_type='text/plain; charset=utf-8')


def _decimal_or_default(value, default=Decimal('0')):
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return default
