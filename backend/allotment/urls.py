# allotment/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from allotment.views import AllotmentViewSet
from allotment.views_actions import AllotmentActionViewSet

router = DefaultRouter()
router.register(r'allotments', AllotmentViewSet, basename='allotment')
router.register(r'allotment-actions', AllotmentActionViewSet, basename='allotment-actions')

urlpatterns = [
    path('', include(router.urls)),
]
