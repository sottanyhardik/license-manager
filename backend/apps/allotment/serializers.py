# allotment/serializers.py -- compatibility shim; implementation lives in api/serializers.py.
# Aliased via sys.modules so mock.patch / private names on the old path hit the live module.
import sys

from apps.allotment.api import serializers as _impl

sys.modules[__name__] = _impl
