# trade/views.py -- compatibility shim; implementation lives in api/views.py.
# Aliased via sys.modules so mock.patch on the old path hits the live module.
import sys

from .api import views as _views

sys.modules[__name__] = _views
