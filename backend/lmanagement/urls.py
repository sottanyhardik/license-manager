# lmanagement/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),  # auth endpoints
    path("api/", include("license.urls")),  # license CRUD + schema
    path("api/masters/", include("core.urls")),  # options/select endpoints
]
