from django.urls import path, include
from rest_framework import routers

from license.views.license import LicenseDetailsViewSet

router = routers.DefaultRouter()
router.register(r"license-details", LicenseDetailsViewSet, basename="license-details")

urlpatterns = [
    path("masters/", include(router.urls)),
]
