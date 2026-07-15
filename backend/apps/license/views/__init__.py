# license/views/__init__.py
from apps.license.views.license import (
    ExportItemViewSet,
    ImportItemViewSet,
    IncentiveLicenseViewSet,
    LicenseDocumentViewSet,
    LicenseItemPlanViewSet,
    LicenseViewSet,
)
from apps.license.views.active_dfia_report import add_active_dfia_report_action
from apps.license.views.expiring_licenses_report import ExpiringLicensesViewSet
from apps.license.views.active_licenses_report import ActiveLicensesViewSet
from apps.license.views.ledger import LicenseLedgerViewSet
from apps.license.views.item_report import ItemReportViewSet
from apps.license.views.item_pivot_report import ItemPivotViewSet

# Attach the active DFIA report action to LicenseViewSet
LicenseViewSet = add_active_dfia_report_action(LicenseViewSet)

__all__ = [
    "LicenseViewSet",
    "ImportItemViewSet",
    "IncentiveLicenseViewSet",
    "LicenseDocumentViewSet",
    "LicenseItemPlanViewSet",
    "ExportItemViewSet",
    "ExpiringLicensesViewSet",
    "ActiveLicensesViewSet",
    "LicenseLedgerViewSet",
    "ItemReportViewSet",
    "ItemPivotViewSet",
]
