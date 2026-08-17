"""License models package (split from the former ~1.9k-LOC models.py).

Behaviour unchanged; every model/name remains importable from
apps.license.models. core.py holds the licence models + signals; invoice.py
holds the standalone Invoice/InvoiceItem pair.
"""
from .core import *  # noqa: F401,F403
from .invoice import Invoice, InvoiceItem  # noqa: F401
