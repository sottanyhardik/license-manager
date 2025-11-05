# license/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LicenseViewSet, LicenseImportItemViewSet, LicenseExportItemViewSet

router = DefaultRouter()
router.register(r"licenses", LicenseViewSet, basename="license")
router.register(r"license-import-items", LicenseImportItemViewSet, basename="license-import-item")
router.register(r"license-export-items", LicenseExportItemViewSet, basename="license-export-item")

urlpatterns = [
    path("", include(router.urls)),
]
