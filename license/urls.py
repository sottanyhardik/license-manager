from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

urlpatterns = [
    # ex: /polls/
    path('add/', login_required(views.LicenseDetailCreateView.as_view()), name='add-license'),
    path('', login_required(views.LicenseDetailListView.as_view()), name='list-license'),
    path('<slug:license>/', login_required(views.LicenseDetailView.as_view()), name='license-detail'),
    path('<int:pk>/update', login_required(views.LicenseDetailUpdateView.as_view()), name='license-update'),
    path('<int:pk>/verify', login_required(views.LicenseVerifyView.as_view()), name='license-verify'),
    path('<slug:license>.pdf', login_required(views.PDFLicenseDetailView.as_view()), name='license-pdf'),
    path('amd/<slug:license>.pdf', login_required(views.PDFAmendmentLicenseDetailView.as_view()), name='amend-license-pdf'),
    path('<slug:license>.xlsx', login_required(views.ExcelLicenseDetailView.as_view()), name='license-excel'),
    path('<int:pk>/ledger', login_required(views.LicenseDetailLedgerView.as_view()), name='license_ledger'),
    path('ledger/<slug:license>.pdf', login_required(views.PDFLedgerLicenseDetailView.as_view()),
         name='license_ledger_pdf'),
    path('consolidated/<str:norm>_<str:notification>.pdf', login_required(views.PDFConsolidatedView.as_view()),
         name='consolidate_pdf'),
    path('report/biscuits', login_required(views.BiscuitsReportView.as_view()), name='biscuits_report'),
    path('report/confectinery', login_required(views.ConfectineryReportView.as_view()), name='confectinery_report'),
    path('report/biscuits/pdf', login_required(views.PDFReportView.as_view()), name='report'),

]
