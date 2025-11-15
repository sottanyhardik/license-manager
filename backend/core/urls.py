# core/urls.py
from rest_framework.routers import DefaultRouter

from .views.views import (CompanyViewSet, PortViewSet, HSCodeViewSet, HeadSIONNormsViewSet, SionNormClassViewSet,
                          HSCodeDutyViewSet, ProductDescriptionViewSet, UnitPriceViewSet, ItemNameViewSet, ItemHeadViewSet)

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)
router.register(r'ports', PortViewSet)
router.register(r'hs-codes', HSCodeViewSet)
router.register(r'head-norms', HeadSIONNormsViewSet)
router.register(r'sion-classes', SionNormClassViewSet)
router.register("hs-code-duties", HSCodeDutyViewSet)
router.register("product-descriptions", ProductDescriptionViewSet)
router.register("unit-prices", UnitPriceViewSet)
router.register("item-heads", ItemHeadViewSet)
router.register("item-names", ItemNameViewSet)
urlpatterns = router.urls
