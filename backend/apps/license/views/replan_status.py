# license/views/replan_status.py -- compatibility shim; implementation lives in api/views/replan_status.
# Aliased via sys.modules so mock.patch / private names on the old path hit the live module.
import importlib
import sys

sys.modules[__name__] = importlib.import_module("apps.license.api.views.replan_status")
