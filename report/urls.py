from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

urlpatterns = [
    path('biscuit', login_required(views.PDFBReportView.as_view()), name='biscuit_report_1'),
    path('confectionery', login_required(views.PDFCReportView.as_view()), name='confectionery_report_1'),
]
