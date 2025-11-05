# core/urls.py
from rest_framework.routers import DefaultRouter
from .views import *
from .views.views import CompanyViewSet, PortViewSet, HSCodeViewSet, HeadSIONNormsViewSet, SionNormClassViewSet, \
    SIONExportViewSet, SIONImportViewSet, HSCodeDutyViewSet, ProductDescriptionViewSet, UnitPriceViewSet

router = DefaultRouter()
router.register("companies", CompanyViewSet)
router.register("ports", PortViewSet)
router.register("hs-codes", HSCodeViewSet)
router.register("head-sion-norms", HeadSIONNormsViewSet)
router.register("sion-classes", SionNormClassViewSet)
router.register("sion-exports", SIONExportViewSet)
router.register("sion-imports", SIONImportViewSet)
router.register("hs-code-duties", HSCodeDutyViewSet)
router.register("product-descriptions", ProductDescriptionViewSet)
router.register("unit-prices", UnitPriceViewSet)

urlpatterns = router.urls
