from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.bill_of_entry.views.boe import BillOfEntryViewSet
from apps.bill_of_entry.views.ledger import LedgerUploadView

app_name = "bill_of_entry"

router = DefaultRouter()
router.register(r"", BillOfEntryViewSet, basename="bill-of-entries")

urlpatterns = [
    path("upload-ledger/", LedgerUploadView.as_view(), name="upload-ledger"),
    path("", include(router.urls)),
]
