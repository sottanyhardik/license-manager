from django.contrib.auth.decorators import login_required
from django.urls import path, include

from . import views

urlpatterns = [
    # ex: /polls/
    path('', login_required(views.DashboardView.as_view()), name='dashboard'),
    path('company/add', login_required(views.CreateCompanyView.as_view()), name='company-add'),
    path('company/', login_required(views.ListCompanyView.as_view()), name='company-list'),
    path('company/<int:pk>/update/', login_required(views.UpdateCompanyView.as_view()), name='company-update'),
    path('sion/', login_required(views.ListSionView.as_view()), name='sion-list'),
    path('sion/<int:pk>/update/', login_required(views.UpdateSionView.as_view()), name='sion-update'),
    path('sion/<int:pk>/', login_required(views.SionDetailView.as_view()), name='sion-detail'),
    path('hs_code/add/', login_required(views.CreateHSNCodeView.as_view()), name='hs-code-add'),
    path('hs_code/', login_required(views.ListHSNView.as_view()), name='hs-code-list'),
    path('hs_code/<int:pk>/update/', login_required(views.UpdateHSNCodeView.as_view()), name='hs-code-update'),
    path('item/add/', login_required(views.CreateItemView.as_view()), name='item-add'),
    path('item/', login_required(views.ListItemView.as_view()), name='item-list'),
    path('item/<int:pk>/update/', login_required(views.UpdateItemView.as_view()), name='item-update'),
    path('ledger/', login_required(views.UploadLedger.as_view()), name='ledger-upload'),
    path('ledger_complete/', login_required(views.LedgerSuccess.as_view()), name='ledger-complete'),
    path('meis/upload/', login_required(views.UploadMEISView.as_view()), name='meis-upload'),
    path('meis/generate/', login_required(views.GenerateTransferLetterMEISView.as_view()), name='generate_tl'),
    # this url is to update transfer dfia status on server
    path('api/update-license-transfer/', views.save_license_transfer, name='save_license_transfer'),
]
