from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views
from .views import IECFetchView

urlpatterns = [
    path('fetch/', IECFetchView.as_view(), name='fetch_iec_details'),
]