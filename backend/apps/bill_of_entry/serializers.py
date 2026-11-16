# bill_of_entry/serializers.py -- compatibility shim; implementation lives in api/serializers.
# Aliased via sys.modules so mock.patch / private names on the old path hit the live module.
import sys

from apps.bill_of_entry.api import serializers as _impl

sys.modules[__name__] = _impl
