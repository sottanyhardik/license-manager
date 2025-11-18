from django.urls import path, include
from rest_framework import routers

from license.views import LicenseDetailsViewSet
from license.views_actions import LicenseActionViewSet

router = routers.DefaultRouter()
router.register(r"licenses", LicenseDetailsViewSet, basename="licenses")
router.register(r"license-actions", LicenseActionViewSet, basename="license-actions")

urlpatterns = [
    path("", include(router.urls)),
]
