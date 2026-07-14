# tests/dashboard/conftest.py
"""
Dashboard-specific test configuration.

The managed=False → True patches for LicenseDetailsModel, LicenseBalance,
LicenseFlags, and AllotmentModel are already applied at import time in
config/settings/test.py (the _patch_license_managed and _patch_allotment_managed
functions).  No additional patching is needed here.

The fixtures api_client, auth_token, and authenticated_client come from
the root conftest at tests/conftest.py.
"""
