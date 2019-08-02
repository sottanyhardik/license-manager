from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

urlpatterns = [
    path('', login_required(views.BillOfEntryView.as_view()), name='bill-of-entry-list'),
    path('add', login_required(views.BillOfEntryCreateView.as_view()), name='bill-of-entry-create'),
    path('<int:pk>', login_required(views.BillOfEntryDetailView.as_view()), name='bill-of-entry-detail'),
    path('<int:pk>/update', login_required(views.BillOfEntryUpdateView.as_view()), name='bill-of-entry-update'),
    path('fetch', login_required(views.BillOfEntryFetchView.as_view()), name='bill_of_entry_fetch'),
]
