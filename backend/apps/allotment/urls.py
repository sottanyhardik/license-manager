from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.allotment.views import AllotmentActionViewSet, AllotmentViewSet

app_name = "allotment"

router = DefaultRouter()
router.register(r"allotments", AllotmentViewSet, basename="allotment")
router.register(r"allotment-actions", AllotmentActionViewSet, basename="allotment-action")

urlpatterns = [path("", include(router.urls))]
