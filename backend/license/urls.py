from django.urls import path, include
from rest_framework import routers

from license.views import LicenseDetailsViewSet
from license.views_actions import LicenseActionViewSet
from license.views.license_items import LicenseItemViewSet

router = routers.DefaultRouter()
router.register(r"licenses", LicenseDetailsViewSet, basename="licenses")
router.register(r"license-actions", LicenseActionViewSet, basename="license-actions")
router.register(r"license-items", LicenseItemViewSet, basename="license-items")

urlpatterns = [
    path("", include(router.urls)),
]
