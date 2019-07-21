from django.urls import path

from . import views

urlpatterns = [
    # ex: /polls/
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('company/add/', views.CreateCompanyView.as_view(), name='company-add'),
    path('company/', views.ListCompanyView.as_view(), name='company-list'),
    path('company/<int:pk>/update/', views.UpdateCompanyView.as_view(), name='company-update'),
    path('sion/', views.ListSionView.as_view(), name='sion-list'),
    path('sion/<int:pk>/update/', views.UpdateSionView.as_view(), name='sion-update'),
    path('hs_code/add/', views.CreateHSNCodeView.as_view(), name='hs-code-add'),
    path('hs_code/', views.ListHSNView.as_view(), name='hs-code-list'),
    path('hs_code/<int:pk>/update/', views.UpdateHSNCodeView.as_view(), name='hs-code-update'),
    path('item/add/', views.CreateItemView.as_view(), name='item-add'),
    path('item/', views.ListItemView.as_view(), name='item-list'),
    path('item/<int:pk>/update/', views.UpdateItemView.as_view(), name='item-update'),
    path('ledger/', views.UploadLedger.as_view(), name='ledger-upload'),
]