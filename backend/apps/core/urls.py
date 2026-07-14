# core/urls.py
"""
URL routing for the core masters module.

All routes are under /api/v1/masters/ (wired in config/api_urls.py).
The app_name "core" provides URL namespace isolation.

Priority order reflects which masters are used as FKs by other modules:
  companies, ports, hs-codes, item-groups, item-names, sion-norm-classes,
  exchange-rates — then the rest.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.core.views.masters import (
    ActivityLogViewSet,
    CeleryTaskTrackerViewSet,
    CompanyViewSet,
    ExchangeRateViewSet,
    HSCodeViewSet,
    HeadSIONNormsViewSet,
    InvoiceEntityViewSet,
    ItemGroupViewSet,
    ItemHeadViewSet,
    ItemNameViewSet,
    MasterChangeViewSet,
    NotificationNumberViewSet,
    PortViewSet,
    ProductDescriptionViewSet,
    PurchaseStatusViewSet,
    SIONExportViewSet,
    SIONImportViewSet,
    SchemeCodeViewSet,
    SionNormClassViewSet,
    SionNormConditionViewSet,
    SionNormNoteViewSet,
    TransferLetterViewSet,
    UnitPriceViewSet,
)

app_name = "core"

router = DefaultRouter()

# --- Priority masters (FK targets for other modules) ---
router.register("companies", CompanyViewSet, basename="company")
router.register("ports", PortViewSet, basename="port")
router.register("hs-codes", HSCodeViewSet, basename="hscode")
router.register("item-groups", ItemGroupViewSet, basename="item-group")
router.register("item-names", ItemNameViewSet, basename="item-name")
router.register("sion-norm-classes", SionNormClassViewSet, basename="sion-norm-class")
router.register("exchange-rates", ExchangeRateViewSet, basename="exchange-rate")

# --- SION sub-masters ---
router.register("head-norms", HeadSIONNormsViewSet, basename="head-norm")
router.register("sion-exports", SIONExportViewSet, basename="sion-export")
router.register("sion-imports", SIONImportViewSet, basename="sion-import")
router.register("sion-norm-notes", SionNormNoteViewSet, basename="sion-norm-note")
router.register("sion-norm-conditions", SionNormConditionViewSet, basename="sion-norm-condition")

# --- Secondary masters ---
router.register("invoice-entities", InvoiceEntityViewSet, basename="invoice-entity")
router.register("scheme-codes", SchemeCodeViewSet, basename="scheme-code")
router.register("notification-numbers", NotificationNumberViewSet, basename="notification-number")
router.register("purchase-statuses", PurchaseStatusViewSet, basename="purchase-status")
router.register("transfer-letters", TransferLetterViewSet, basename="transfer-letter")
router.register("unit-prices", UnitPriceViewSet, basename="unit-price")
router.register("product-descriptions", ProductDescriptionViewSet, basename="product-description")

# --- Deprecated (read-only, for backward compat) ---
router.register("item-heads", ItemHeadViewSet, basename="item-head")

# --- System / ops (staff-only, read-only) ---
router.register("master-changes", MasterChangeViewSet, basename="master-change")
router.register("celery-tasks", CeleryTaskTrackerViewSet, basename="celery-task")
router.register("activity-logs", ActivityLogViewSet, basename="activity-log")

urlpatterns = [
    path("", include(router.urls)),
]
