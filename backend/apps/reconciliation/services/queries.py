# reconciliation/services/queries.py -- compatibility shim; implementation lives in reconciliation/selectors.py
import sys

from .. import selectors as _selectors

sys.modules[__name__] = _selectors
