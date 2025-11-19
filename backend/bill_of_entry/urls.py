from django.urls import path, include
from rest_framework import routers

from bill_of_entry.views.boe import BillOfEntryViewSet

router = routers.DefaultRouter()
router.register(r"bill-of-entries", BillOfEntryViewSet, basename="bill-of-entries")

urlpatterns = [
    path("", include(router.urls)),
]
