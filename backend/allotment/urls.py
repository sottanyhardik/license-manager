# allotment/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from allotment.views import AllotmentViewSet

router = DefaultRouter()
router.register(r'allotments', AllotmentViewSet, basename='allotment')

urlpatterns = [
    path('', include(router.urls)),
]
