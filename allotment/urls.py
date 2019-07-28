from django.urls import path

from . import views

urlpatterns = [
    # ex: /polls/
    path('add/', views.AllotmentCreateView.as_view(), name='allotment-add'),
    path('<int:pk>', views.StartAllotmentView.as_view(), name='allotment-details'),
    path('', views.AllotmentView.as_view(), name='allotment-list'),
    path('<int:pk>/update', views.AllotmentUpdateView.as_view(), name='allotment-update'),
    path('<int:pk>/delete', views.AllotmentDeleteView.as_view(), name='allotment-delete'),
    path('<int:pk>/item/delete', views.AllotmentDeleteItemsView.as_view(), name='allotment-item-delete'),
    path('<int:pk>/verify', views.AllotmentVerifyView.as_view(), name='allotment-verify'),
    path('<int:pk>/data/', views.allotment_data, name='allotment-data'),
    path('<int:pk>/send/', views.SendAllotmentView.as_view(), name='allotment-send'),
    # path('<int:pk>/pdf', views.PDFLicenseDetailView.as_view(), name='license-pdf')
]