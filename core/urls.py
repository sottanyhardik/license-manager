# core/urls.py
from rest_framework.routers import DefaultRouter
from .views import *
from .views.views import (CompanyViewSet, PortViewSet, HSCodeViewSet, HeadSIONNormsViewSet, SionNormClassViewSet,
                          HSCodeDutyViewSet, ProductDescriptionViewSet, UnitPriceViewSet)

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)
router.register(r'ports', PortViewSet)
router.register(r'hs-codes', HSCodeViewSet)
router.register(r'head-norms', HeadSIONNormsViewSet)
router.register(r'sion-classes', SionNormClassViewSet)
router.register("hs-code-duties", HSCodeDutyViewSet)
router.register("product-descriptions", ProductDescriptionViewSet)
router.register("unit-prices", UnitPriceViewSet)

urlpatterns = router.urls
