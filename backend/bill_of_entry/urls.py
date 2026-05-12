from django.urls import path, include
from rest_framework import routers

from bill_of_entry.views.boe import BillOfEntryViewSet
from bill_of_entry.views.parse_pdf import BOEPdfParseView

router = routers.DefaultRouter()
router.register(r"bill-of-entries", BillOfEntryViewSet, basename="bill-of-entries")

urlpatterns = [
    path("bill-of-entries/parse-pdf/", BOEPdfParseView.as_view(), name="boe-parse-pdf"),
    path("", include(router.urls)),
]
