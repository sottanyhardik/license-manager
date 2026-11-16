# trade/serializers.py -- compatibility shim; implementation lives in api/serializers.py.
# Aliased via sys.modules so mock.patch on the old path hits the live module.
import sys

from .api import serializers as _serializers

sys.modules[__name__] = _serializers
