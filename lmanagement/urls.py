# lmanagement/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),  # auth endpoints
    path("api/", include("license.urls")),    # license CRUD + schema
    path("api/core/", include("core.urls")),          # options/select endpoints
]
