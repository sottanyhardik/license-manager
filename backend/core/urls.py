# core/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views.views import (CompanyViewSet, PortViewSet, HSCodeViewSet, HeadSIONNormsViewSet, SionNormClassViewSet,
                          ProductDescriptionViewSet, UnitPriceViewSet, ItemNameViewSet, ItemHeadViewSet, GroupViewSet,
                          TransferLetterViewSet, ExchangeRateViewSet, PurchaseStatusViewSet)
from .views.throttle_status import (
    ThrottleStatusView,
    ThrottleScopeStatusView,
    ThrottleResetView,
    ThrottleStatsView,
    ThrottleHealthView,
)

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)
router.register(r'ports', PortViewSet)
router.register(r'hs-codes', HSCodeViewSet)
router.register(r'head-norms', HeadSIONNormsViewSet)
router.register(r'sion-classes', SionNormClassViewSet)
router.register("product-descriptions", ProductDescriptionViewSet)
router.register("unit-prices", UnitPriceViewSet)
router.register("groups", GroupViewSet)
router.register("item-heads", ItemHeadViewSet)  # Deprecated
router.register("item-names", ItemNameViewSet)
router.register("exchange-rates", ExchangeRateViewSet)
router.register("transfer-letters", TransferLetterViewSet)
router.register("purchase-statuses", PurchaseStatusViewSet)

urlpatterns = [
    # Throttle monitoring endpoints
    path('throttle-status/', ThrottleStatusView.as_view(), name='throttle-status'),
    path('throttle-status/<str:scope>/', ThrottleScopeStatusView.as_view(), name='throttle-scope-status'),
    path('throttle-reset/', ThrottleResetView.as_view(), name='throttle-reset'),
    path('throttle-stats/', ThrottleStatsView.as_view(), name='throttle-stats'),
    path('throttle-health/', ThrottleHealthView.as_view(), name='throttle-health'),
] + router.urls
