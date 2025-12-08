from django.urls import path, include
from rest_framework import routers

from license.views import LicenseDetailsViewSet
from license.views.expiring_licenses_report import ExpiringLicensesViewSet, ExpiringLicensesReportView
from license.views.active_licenses_report import ActiveLicensesViewSet, ActiveLicensesReportView
from license.views.item_pivot_report import ItemPivotViewSet, ItemPivotReportView
from license.views.item_report import ItemReportViewSet, ItemReportView
from license.views.inventory_balance_report import InventoryBalanceReportView
from license.views.inventory_balance_viewset import InventoryBalanceViewSet
from license.views.license_items import LicenseItemViewSet
from license.views.dashboard import DashboardDataView
from license.views.ledger_upload import LedgerUploadView
from license.views_actions import LicenseActionViewSet

router = routers.DefaultRouter()
router.register(r"licenses", LicenseDetailsViewSet, basename="licenses")
router.register(r"license-actions", LicenseActionViewSet, basename="license-actions")
router.register(r"license-items", LicenseItemViewSet, basename="license-items")
router.register(r"inventory-balance", InventoryBalanceViewSet, basename="inventory-balance")
router.register(r"expiring-licenses", ExpiringLicensesViewSet, basename="expiring-licenses")
router.register(r"active-licenses", ActiveLicensesViewSet, basename="active-licenses")
router.register(r"item-pivot", ItemPivotViewSet, basename="item-pivot")
router.register(r"item-report", ItemReportViewSet, basename="item-report")

urlpatterns = [
    # Specific paths must come BEFORE router.urls to avoid conflicts
    # Dashboard unified endpoint
    path("dashboard/", DashboardDataView.as_view(), name="dashboard"),
    # Ledger Upload endpoint
    path("upload-ledger/", LedgerUploadView.as_view(), name="upload-ledger"),
    # Report endpoints
    path("reports/inventory-balance/", InventoryBalanceReportView.as_view(), name="inventory-balance-report"),
    path("reports/expiring-licenses/", ExpiringLicensesReportView.as_view(), name="expiring-licenses-report"),
    path("reports/active-licenses/", ActiveLicensesReportView.as_view(), name="active-licenses-report"),
    path("reports/item-pivot/", ItemPivotReportView.as_view(), name="item-pivot-report"),
    path("reports/item-report/", ItemReportView.as_view(), name="item-report"),
    # Router URLs must come LAST
    path("", include(router.urls)),
]
