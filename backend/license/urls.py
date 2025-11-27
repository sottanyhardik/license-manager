from django.urls import path, include
from rest_framework import routers

from license.views import LicenseDetailsViewSet
from license.views.expiring_licenses_report import ExpiringLicensesViewSet, ExpiringLicensesReportView
from license.views.inventory_balance_report import InventoryBalanceReportView
from license.views.inventory_balance_viewset import InventoryBalanceViewSet
from license.views.license_items import LicenseItemViewSet
from license.views_actions import LicenseActionViewSet

router = routers.DefaultRouter()
router.register(r"licenses", LicenseDetailsViewSet, basename="licenses")
router.register(r"license-actions", LicenseActionViewSet, basename="license-actions")
router.register(r"license-items", LicenseItemViewSet, basename="license-items")
router.register(r"inventory-balance", InventoryBalanceViewSet, basename="inventory-balance")
router.register(r"expiring-licenses", ExpiringLicensesViewSet, basename="expiring-licenses")

urlpatterns = [
    path("", include(router.urls)),
    # Legacy endpoints for backward compatibility
    path("reports/inventory-balance/", InventoryBalanceReportView.as_view(), name="inventory-balance-report"),
    path("license/reports/expiring-licenses/", ExpiringLicensesReportView.as_view(), name="expiring-licenses-report"),
]
