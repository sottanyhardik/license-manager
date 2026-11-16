# trade/views_invoice_documents.py -- compatibility shim; implementation lives in api/views_invoice_documents.py.
# Aliased via sys.modules so mock.patch on the old path hits the live module.
import sys

from .api import views_invoice_documents as _views_invoice_documents

sys.modules[__name__] = _views_invoice_documents
