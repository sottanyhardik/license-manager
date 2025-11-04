# from django.contrib.auth.decorators import login_required
# from django.urls import path
#
# from . import views
#
# urlpatterns = [
#     path('', login_required(views.BillOfEntryView.as_view()), name='bill-of-entry-list'),
#     path('ajax/', login_required(views.BillOfEntryAjaxListView.as_view()), name='bill-of-entry-ajax-list'),
#     path('add', login_required(views.BillOfEntryCreateView.as_view()), name='bill-of-entry-create'),
#     path('<slug:boe>', login_required(views.BillOfEntryDetailView.as_view()), name='bill-of-entry-detail'),
#     path('<slug:pk>/update', login_required(views.BillOfEntryUpdateDetailView.as_view()), name='bill-of-entry-update'),
#     path('<slug:pk>/item', login_required(views.BillOfEntryUpdateView.as_view()), name='bill-of-entry-items'),
#     path('fetch/', login_required(views.BillOfEntryFetchView.as_view()), name='bill_of_entry_fetch'),
#     path('download/', login_required(views.DownloadPendingBillView.as_view()), name='bill_of_entry_pending'),
#     path('<slug:pk>/tl', login_required(views.GenerateTransferLetterView.as_view()), name='bill-of-entry-tl'),
#     path('download/port/', login_required(views.DownloadPortView.as_view()), name='bill_of_entry_download_boe'),
# ]

from django.contrib.auth.decorators import login_required
from django.urls import path, include

from . import views

urlpatterns = [
]
