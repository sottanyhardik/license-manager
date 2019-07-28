from django.urls import path

from . import views

urlpatterns = [
    path('', views.BillOfEntryView.as_view(), name='bill-of-entry-list'),
    path('add', views.BillOfEntryCreateView.as_view(), name='bill-of-entry-create'),
    path('<int:pk>', views.BillOfEntryDetailView.as_view(), name='bill-of-entry-detail'),
    path('<int:pk>/update', views.BillOfEntryUpdateView.as_view(), name='bill-of-entry-update'),

]