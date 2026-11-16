# license/views/active_licenses_report.py -- compatibility shim; implementation lives in api/views/active_licenses_report.
# Aliased via sys.modules so mock.patch / private names on the old path hit the live module.
import importlib
import sys

sys.modules[__name__] = importlib.import_module("apps.license.api.views.active_licenses_report")
