# lmanagement/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.views.static import serve
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),  # auth endpoints
    path("api/", include("license.urls")),  # license CRUD + schema
    path("api/", include("allotment.urls")),  # allotment CRUD
    path("api/", include("bill_of_entry.urls")),  # bill of entry CRUD
    path("api/", include("trade.urls")),  # trade in/out CRUD
    path("api/masters/", include("core.urls")),  # options/select endpoints

    # Serve React assets directly
    re_path(
        r"^assets/(?P<path>.*)$",
        serve,
        {"document_root": settings.BASE_DIR.parent / "frontend" / "dist" / "assets"},
    ),

    # Serve React frontend for all other routes (must be last)
    re_path(r"^.*$", TemplateView.as_view(template_name="index.html")),
]
