# allotment/views.py -- compatibility shim; implementation lives in api/views.py.
# Aliased via sys.modules so mock.patch / private names on the old path hit the live module.
import sys

from apps.allotment.api import views as _impl

sys.modules[__name__] = _impl
