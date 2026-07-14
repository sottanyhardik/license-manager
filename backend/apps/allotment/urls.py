from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.allotment.views import AllotmentViewSet

app_name = "allotment"

router = DefaultRouter()
router.register(r"allotments", AllotmentViewSet, basename="allotment")

urlpatterns = [path("", include(router.urls))]
