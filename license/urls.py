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
    path('ledger/item/<slug:license>.pdf', login_required(views.PDFLedgerItemLicenseDetailView.as_view()),
         name='license_item_ledger_pdf'),
    path('consolidated/<str:norm>_<str:notification>.pdf', login_required(views.PDFConsolidatedView.as_view()),
         name='consolidate_pdf'),
    path('report/biscuits', login_required(views.BiscuitsReportView.as_view()), name='biscuits_report'),
    path('report/confectinery', login_required(views.ConfectineryReportView.as_view()), name='confectinery_report'),
    path('report/con/', login_required(views.PDFCReportView.as_view()), name='report_conversion'),
    path('report/oth/con/ss', login_required(views.PDFOCReportView.as_view()), name='report_other_conversion'),

    path('report/biscuits/new', login_required(views.PDFNewBiscuitsReportView.as_view()), name='report_new_biscuits'),
    path('report/confectinery/new', login_required(views.PDFNewConfectioneryReportView.as_view()),
         name='report_new_confectionery'),
    path('report/biscuits/new/other/', login_required(views.PDFNewBiscuitsOtherReportView.as_view()), name='report_new_biscuits_other'),
    path('report/confectinery/new/other/', login_required(views.PDFNewConfectioneryOtherReportView.as_view()),
         name='report_new_confectionery_other'),
    path('report/all/old', login_required(views.PDFOldAllReportView.as_view()), name='report_all_old'),
    path('biscuits/amend', login_required(views.BiscuitsAmmendmentView.as_view()), name='biscuit_amend'),
    path('biscuits/new/expiried', login_required(views.PDFBiscuitsNewExpiryReportView.as_view()), name='biscuits_expiried_new'),
    path('confectinery/new/expiried', login_required(views.PDFConfectioneryNewExpiredReportView.as_view()), name='confectinery_expiried_new'),
    path('biscuits/old/expiried', login_required(views.PDFBiscuitsOldExpiryReportView.as_view()), name='biscuits_expiried_old'),
    path('confectinery/old/expiried', login_required(views.PDFConfectioneryOldExpiredReportView.as_view()), name='confectinery_expiried_old'),
]
