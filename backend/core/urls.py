# core/urls.py
from rest_framework.routers import DefaultRouter

from .views.views import (CompanyViewSet, PortViewSet, HSCodeViewSet, HeadSIONNormsViewSet, SionNormClassViewSet,
                          ProductDescriptionViewSet, UnitPriceViewSet, ItemNameViewSet, ItemHeadViewSet, GroupViewSet,
                          TransferLetterViewSet, ExchangeRateViewSet)

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
urlpatterns = router.urls
