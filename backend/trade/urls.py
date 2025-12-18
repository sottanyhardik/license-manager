# trade/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LicenseTradeViewSet, TradeLineViewSet, TradePaymentViewSet
from .ledger_views import (
    ChartOfAccountsViewSet,
    BankAccountViewSet,
    JournalEntryViewSet,
    PartyLedgerView,
    AccountLedgerView,
    OutstandingInvoicesView,
    AgingAnalysisView,
)

router = DefaultRouter()
router.register(r'trades', LicenseTradeViewSet, basename='trade')
router.register(r'lines', TradeLineViewSet, basename='trade-line')
router.register(r'payments', TradePaymentViewSet, basename='trade-payment')

# Ledger module routes
router.register(r'chart-of-accounts', ChartOfAccountsViewSet, basename='chart-of-accounts')
router.register(r'bank-accounts', BankAccountViewSet, basename='bank-accounts')
router.register(r'journal-entries', JournalEntryViewSet, basename='journal-entries')

urlpatterns = [
    path('', include(router.urls)),

    # Ledger reports
    path('ledger/party/<int:company_id>/', PartyLedgerView.as_view(), name='party-ledger'),
    path('ledger/account/<int:account_id>/', AccountLedgerView.as_view(), name='account-ledger'),
    path('ledger/reports/outstanding-invoices/', OutstandingInvoicesView.as_view(), name='outstanding-invoices'),
    path('ledger/reports/aging-analysis/', AgingAnalysisView.as_view(), name='aging-analysis'),
]
