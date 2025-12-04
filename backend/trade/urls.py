# trade/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LicenseTradeViewSet, TradeLineViewSet, TradePaymentViewSet

router = DefaultRouter()
router.register(r'trades', LicenseTradeViewSet, basename='trade')
router.register(r'lines', TradeLineViewSet, basename='trade-line')
router.register(r'payments', TradePaymentViewSet, basename='trade-payment')

urlpatterns = [
    path('', include(router.urls)),
]
