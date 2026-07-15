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

from apps.license.views.license import (
    ImportItemViewSet,
    IncentiveLicenseViewSet,
    LicenseDocumentViewSet,
    LicenseItemPlanViewSet,
    LicenseViewSet,
)

app_name = "license"

router = DefaultRouter()
router.register(r"licenses", LicenseViewSet, basename="licenses")
router.register(r"incentive-licenses", IncentiveLicenseViewSet, basename="incentive-licenses")

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
]
