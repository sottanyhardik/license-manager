# allotment/views_export.py -- compatibility shim; implementation lives in api/views_export.py.
# Aliased via sys.modules so mock.patch / private names on the old path hit the live module.
import sys

from apps.allotment.api import views_export as _impl

sys.modules[__name__] = _impl
