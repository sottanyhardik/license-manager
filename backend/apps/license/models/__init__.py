"""License models package (split from the former ~1.9k-LOC models.py).

Behaviour unchanged; every model/name remains importable from
apps.license.models.  Modules: header.py (licence header + 1:1 sub-tables),
items.py (export/import items), planning.py (utilization planning),
documents.py (documents, workflow lookups, transfers), incentive.py,
ledger_jobs.py (ledger package jobs), invoice.py (Invoice/InvoiceItem).
core.py is a re-export facade kept for backward compatibility.
"""
from .core import *  # noqa: F401,F403
from .invoice import Invoice, InvoiceItem  # noqa: F401
from .product_matching import ProductMatchDecision, ProductMatchingJob, ProductMatchSuggestion, ProductTextEmbedding  # noqa: F401,E402
from .product_intelligence import ProductAlias, ProductIntelAuditEvent, ProductIntelDataset, ProductIntelModel, ProductMatchSelection, MappingChange  # noqa: F401,E402
