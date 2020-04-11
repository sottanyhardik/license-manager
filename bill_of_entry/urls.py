from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

urlpatterns = [
    path('', login_required(views.BillOfEntryView.as_view()), name='bill-of-entry-list'),
    path('ajax/', login_required(views.BillOfEntryAjaxListView.as_view()), name='bill-of-entry-ajax-list'),
    path('add', login_required(views.BillOfEntryCreateView.as_view()), name='bill-of-entry-create'),
    path('<slug:boe>', login_required(views.BillOfEntryDetailView.as_view()), name='bill-of-entry-detail'),
    path('<slug:boe>/update', login_required(views.BillOfEntryUpdateDetailView.as_view()), name='bill-of-entry-update'),
    path('<slug:boe>/item', login_required(views.BillOfEntryUpdateView.as_view()), name='bill-of-entry-items'),
    path('<slug:boe>/delete', login_required(views.BillOfEntryDeleteView.as_view()), name='bill-of-entry-delete'),
    path('fetch', login_required(views.BillOfEntryFetchView.as_view()), name='bill_of_entry_fetch'),
    path('download/', login_required(views.DownloadPendingBillView.as_view()), name='bill_of_entry_pending'),

]
