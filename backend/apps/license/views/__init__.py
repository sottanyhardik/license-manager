# license/views/__init__.py
from .license import LicenseDetailsViewSet
# Submodules that were eagerly imported (as package attributes) via .license before the
# api/ move; keep them importable as attributes of this package.
from . import active_dfia_report, license_balance_ledger, license_overview, license_report  # noqa: F401

__all__ = ['LicenseDetailsViewSet']
