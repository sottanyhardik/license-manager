# license/serializers/_license_write.py -- compatibility shim; implementation lives in api/serializers/_license_write.
# Aliased via sys.modules so mock.patch / private names on the old path hit the live module.
import importlib
import sys

sys.modules[__name__] = importlib.import_module("apps.license.api.serializers._license_write")
