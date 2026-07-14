# license/permissions.py
"""
Permission re-exports for the License module.

All RBAC logic lives in apps.accounts.permissions.  This module re-exports the
relevant classes so that license views import from a single, stable location
without duplicating role codes.
"""
from apps.accounts.permissions import (
    IncentiveLicensePermission,
    LicensePermission,
    LicenseReadOnlyPermission,
)

__all__ = [
    "LicensePermission",
    "LicenseReadOnlyPermission",
    "IncentiveLicensePermission",
]
