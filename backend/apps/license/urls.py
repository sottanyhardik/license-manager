# license/urls.py
"""
URL routing for the License module.

drf-nested-routers is NOT available in this project's requirements.  We
therefore implement nested resources (items, documents) with explicit
path() patterns instead.

Top-level routes (registered on the standard DefaultRouter):
  /licenses/                           → LicenseViewSet
  /incentive-licenses/                 → IncentiveLicenseViewSet

Nested routes (manual):
  /licenses/{license_pk}/items/        → ImportItemViewSet
  /licenses/{license_pk}/items/{pk}/
  /licenses/{license_pk}/documents/    → LicenseDocumentViewSet
  /licenses/{license_pk}/documents/{pk}/
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.license.views.ledger_upload import LedgerTaskStatusView, LedgerUploadView
from apps.license.views.ledger import LicenseLedgerViewSet
from apps.license.views import (
    ActiveLicensesViewSet,
    ExpiringLicensesViewSet,
    LicenseViewSet,
    IncentiveLicenseViewSet,
    ItemReportViewSet,
    ItemPivotViewSet,
)
from apps.license.views.license import (
    ExportItemViewSet,
    ImportItemViewSet,
    LicenseDocumentViewSet,
    LicenseItemPlanViewSet,
)

app_name = "license"

router = DefaultRouter()
router.register(r"licenses", LicenseViewSet, basename="licenses")
router.register(r"incentive-licenses", IncentiveLicenseViewSet, basename="incentive-licenses")
router.register(r"expiring-licenses", ExpiringLicensesViewSet, basename="expiring-licenses")
router.register(r"active-licenses", ActiveLicensesViewSet, basename="active-licenses")
router.register(r"license-ledger", LicenseLedgerViewSet, basename="license-ledger")
router.register(r"item-report", ItemReportViewSet, basename="item-report")
router.register(r"item-pivot", ItemPivotViewSet, basename="item-pivot")

# Manually wired nested routes — mimics drf-nested-routers behaviour
_item_list = ImportItemViewSet.as_view(
    {
        "get": "list",
        "post": "create",
    }
)
_item_detail = ImportItemViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

_doc_list = LicenseDocumentViewSet.as_view(
    {
        "get": "list",
        "post": "create",
    }
)
_doc_detail = LicenseDocumentViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

_plan_list = LicenseItemPlanViewSet.as_view(
    {
        "get": "list",
        "post": "create",
    }
)
_plan_detail = LicenseItemPlanViewSet.as_view(
    {
        "get": "retrieve",
        "patch": "partial_update",
        "put": "update",
        "delete": "destroy",
    }
)

_export_item_list = ExportItemViewSet.as_view({"get": "list"})
_export_item_detail = ExportItemViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("", include(router.urls)),
    # Nested: import items
    path(
        "licenses/<int:license_pk>/items/",
        _item_list,
        name="license-items-list",
    ),
    path(
        "licenses/<int:license_pk>/items/<int:pk>/",
        _item_detail,
        name="license-items-detail",
    ),
    # Nested: documents
    path(
        "licenses/<int:license_pk>/documents/",
        _doc_list,
        name="license-documents-list",
    ),
    path(
        "licenses/<int:license_pk>/documents/<int:pk>/",
        _doc_detail,
        name="license-documents-detail",
    ),
    # Nested: item plans (LicenseItemPlan — planning allocations per import item)
    path(
        "licenses/<int:license_pk>/item-plans/",
        _plan_list,
        name="license-item-plans-list",
    ),
    path(
        "licenses/<int:license_pk>/item-plans/<int:pk>/",
        _plan_detail,
        name="license-item-plans-detail",
    ),
    # Nested: export items (credit side of a license)
    path(
        "licenses/<int:license_pk>/export-items/",
        _export_item_list,
        name="license-export-items-list",
    ),
    path(
        "licenses/<int:license_pk>/export-items/<int:pk>/",
        _export_item_detail,
        name="license-export-items-detail",
    ),
    # Ledger upload and task status
    path(
        "licenses/upload-ledger/",
        LedgerUploadView.as_view(),
        name="ledger-upload",
    ),
    path(
        "licenses/ledger-task-status/<str:task_id>/",
        LedgerTaskStatusView.as_view(),
        name="ledger-task-status",
    ),
]
