from django.urls import path, include
from rest_framework import routers

app_name = "license"

from apps.license.api.views.license import LicenseDetailsViewSet
from apps.license.api.views.expiring_licenses_report import ExpiringLicensesViewSet, ExpiringLicensesReportView
from apps.license.api.views.active_licenses_report import ActiveLicensesViewSet, ActiveLicensesReportView
from apps.license.api.views.item_pivot_report import ItemPivotViewSet, ItemPivotReportView
from apps.license.api.views.item_report import ItemReportViewSet, ItemReportView
from apps.license.api.views.planned_report import PlannedReportViewSet, PlannedReportView
from apps.license.api.views.license_purchase_profit_report import LicensePurchaseProfitReportView
from apps.license.api.views.inventory_balance_report import InventoryBalanceReportView
from apps.license.api.views.inventory_balance_viewset import InventoryBalanceViewSet
from apps.license.api.views.license_items import LicenseItemViewSet
from apps.license.api.views.item_plan import LicenseItemPlanViewSet
from apps.license.api.views.sion_planning_rule import SionPlanningRuleViewSet
from apps.license.api.views.dashboard import DashboardDataView
from apps.license.api.views.ledger_upload import LedgerUploadView, LedgerTaskStatusView
from apps.license.api.views.ledger import LicenseLedgerViewSet
from apps.license.api.views.parse_pdf import LicensePdfParseView
from apps.license.views_actions import LicenseActionViewSet
from apps.license.views_incentive import IncentiveLicenseViewSet
from apps.license.api.views.replan_status import LicenseReplanStatusView
from apps.license.api.views.import_item_suggestion import ImportItemSuggestionView
from apps.license.api.views.license_overview_transactions import LicenseOverviewTransactionsView

router = routers.DefaultRouter()
router.register(r"licenses", LicenseDetailsViewSet, basename="licenses")
router.register(r"license-actions", LicenseActionViewSet, basename="license-actions")
router.register(r"license-items", LicenseItemViewSet, basename="license-items")
router.register(r"license-item-plans", LicenseItemPlanViewSet, basename="license-item-plans")
router.register(r"sion-planning-rules", SionPlanningRuleViewSet, basename="sion-planning-rules")
router.register(r"license-ledger", LicenseLedgerViewSet, basename="license-ledger")
router.register(r"inventory-balance", InventoryBalanceViewSet, basename="inventory-balance")
router.register(r"expiring-licenses", ExpiringLicensesViewSet, basename="expiring-licenses")
router.register(r"active-licenses", ActiveLicensesViewSet, basename="active-licenses")
router.register(r"item-pivot", ItemPivotViewSet, basename="item-pivot")
router.register(r"item-report", ItemReportViewSet, basename="item-report")
router.register(r"planned-report", PlannedReportViewSet, basename="planned-report")
router.register(r"incentive-licenses", IncentiveLicenseViewSet, basename="incentive-licenses")

urlpatterns = [
    path("import-item-suggestion/", ImportItemSuggestionView.as_view(), name="import-item-suggestion"),
    # Specific paths must come BEFORE router.urls to avoid conflicts
    # Dashboard unified endpoint
    path("dashboard/", DashboardDataView.as_view(), name="dashboard"),
    # License PDF parse (DFIA licence copy → prefill License form)
    path("licenses/parse-pdf/", LicensePdfParseView.as_view(), name="licenses-parse-pdf"),
    path("licenses/<str:license_id>/replan-status/", LicenseReplanStatusView.as_view(), name="license-replan-status"),
    path(
        "licenses/<str:license_id>/overview-transactions/",
        LicenseOverviewTransactionsView.as_view(),
        name="license-overview-transactions",
    ),
    # Ledger Upload endpoint
    path("upload-ledger/", LedgerUploadView.as_view(), name="upload-ledger"),
    # Ledger Task Status endpoint
    path("ledger-task-status/<str:task_id>/", LedgerTaskStatusView.as_view(), name="ledger-task-status"),
    # Report endpoints
    path("reports/inventory-balance/", InventoryBalanceReportView.as_view(), name="inventory-balance-report"),
    path("reports/expiring-licenses/", ExpiringLicensesReportView.as_view(), name="expiring-licenses-report"),
    path("reports/active-licenses/", ActiveLicensesReportView.as_view(), name="active-licenses-report"),
    path("reports/item-pivot/", ItemPivotReportView.as_view(), name="item-pivot-report"),
    path("reports/item-report/", ItemReportView.as_view(), name="item-report"),
    path("reports/planned-report/", PlannedReportView.as_view(), name="planned-report"),
    path("reports/license-purchase-profit/", LicensePurchaseProfitReportView.as_view(), name="license-purchase-profit-report"),
    # Router URLs must come LAST
    path("", include(router.urls)),
]
