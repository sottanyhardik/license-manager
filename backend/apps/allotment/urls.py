# allotment/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.allotment.api.views import AllotmentViewSet
from apps.allotment.api.views_actions import AllotmentActionViewSet

app_name = "allotment"

router = DefaultRouter()
router.register(r'allotments', AllotmentViewSet, basename='allotment')
router.register(r'allotment-actions', AllotmentActionViewSet, basename='allotment-actions')

urlpatterns = [
    path('', include(router.urls)),
]
