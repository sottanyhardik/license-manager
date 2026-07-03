from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("companies", views.CompanyViewSet, basename="company")
router.register("ports", views.PortViewSet, basename="port")
router.register("exchange-rates", views.ExchangeRateViewSet, basename="exchangerate")
router.register("changes", views.MasterChangeViewSet, basename="masterchange")

urlpatterns = router.urls
