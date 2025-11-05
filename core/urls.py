# core/urls.py
from django.urls import path
from .views import (
    CompanyOptionsView,
    ItemOptionsView,
    HSCodeOptionsView,
    PortOptionsView,
    NormClassOptionsView,
)

urlpatterns = [
    path("companymodels/", CompanyOptionsView.as_view(), name="options-companies"),
    path("items/", ItemOptionsView.as_view(), name="options-items"),
    path("hscodes/", HSCodeOptionsView.as_view(), name="options-hscodes"),
    path("portmodels/", PortOptionsView.as_view(), name="options-ports"),
    path("norm-classes/", NormClassOptionsView.as_view(), name="options-norm-classes"),
]
