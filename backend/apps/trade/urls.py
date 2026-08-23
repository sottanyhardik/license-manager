# trade/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LicenseTradeViewSet, TradeLineViewSet, TradePaymentViewSet
from .views_invoice_documents import InvoiceDocumentView

app_name = "trade"

router = DefaultRouter()
router.register(r'trades', LicenseTradeViewSet, basename='trade')
router.register(r'lines', TradeLineViewSet, basename='trade-line')
router.register(r'payments', TradePaymentViewSet, basename='trade-payment')

urlpatterns = [
    path('invoice-documents/view/<str:token>/', InvoiceDocumentView.as_view(), name='invoice-document-view'),
    path('', include(router.urls)),
]
