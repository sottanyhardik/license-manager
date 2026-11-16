# bill_of_entry/views_export.py -- compatibility shim; implementation lives in api/views_export.
# Aliased via sys.modules so mock.patch / private names on the old path hit the live module.
import sys

from apps.bill_of_entry.api import views_export as _impl

sys.modules[__name__] = _impl
