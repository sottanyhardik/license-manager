from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

urlpatterns = [
    # ex: /polls/
    path('add/', login_required(views.LicenseDetailCreateView.as_view()), name='add-license'),
    path('', login_required(views.LicenseDetailListView.as_view()), name='list-license'),
    path('<int:pk>/', login_required(views.LicenseDetailView.as_view()), name='license-detail'),
    path('<int:pk>/update', login_required(views.LicenseDetailUpdateView.as_view()), name='license-update'),
    path('<int:pk>/verify', login_required(views.LicenseVerifyView.as_view()), name='license-verify'),
    path('<slug:license>.pdf', login_required(views.PDFLicenseDetailView.as_view()), name='license-pdf'),
    path('<slug:license>.xlsx', login_required(views.ExcelLicenseDetailView.as_view()), name='license-excel'),
    path('<int:pk>/ledger', login_required(views.LicenseDetailLedgerView.as_view()), name='license_ledger'),
    path('ledger/<slug:license>.pdf', login_required(views.PDFLedgerLicenseDetailView.as_view()),
         name='license_ledger_pdf'),
    path('consolidated/<str:norm>_<str:notification>.pdf', login_required(views.PDFConsolidatedView.as_view()),
         name='consolidate_pdf'),
    # # ex: /polls/5/
    # path('<int:question_id>/', views.detail, name='detail'),
    # # ex: /polls/5/results/
    # path('<int:question_id>/results/', views.results, name='results'),
    # # ex: /polls/5/vote/
    # path('<int:question_id>/vote/', views.vote, name='vote'),
]
