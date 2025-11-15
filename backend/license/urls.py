from django.urls import path, include
from rest_framework import routers

from license.views import LicenseDetailsViewSet

router = routers.DefaultRouter()
router.register(r"licenses", LicenseDetailsViewSet, basename="licenses")

urlpatterns = [
    path("", include(router.urls)),
]
