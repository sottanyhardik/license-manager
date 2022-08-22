from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views
from .views import IECFetchView, CompanyLicenseListView

urlpatterns = [
    path('fetch/', IECFetchView.as_view(), name='fetch_iec_details'),
    path('list/', CompanyLicenseListView.as_view(), name='meis_list_details'),

]