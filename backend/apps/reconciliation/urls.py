# reconciliation/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReconciliationViewSet

app_name = "reconciliation"

router = DefaultRouter()
router.register(r"reconciliation", ReconciliationViewSet, basename="reconciliation")

urlpatterns = [
    path("", include(router.urls)),
]
