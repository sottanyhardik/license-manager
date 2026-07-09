# lmanagement/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.views.static import serve
from django.conf import settings

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from apps.core.views.health import HealthView
from apps.core.views.mds_status import MDSStatusView
from apps.core.views.media import ProtectedMediaView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="api-health"),
    path("api/mds/status/", MDSStatusView.as_view(), name="mds-status"),

    # OpenAPI schema + interactive docs (drf-spectacular)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Authenticated media/document downloads (replaces public /media/ — see
    # apps.core.views.media.ProtectedMediaView and docs/08-security.md).
    re_path(r"^api/media/(?P<path>.+)$", ProtectedMediaView.as_view(), name="protected-media"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.license.urls")),
    path("api/", include("apps.allotment.urls")),
    path("api/", include("apps.bill_of_entry.urls")),
    path("api/", include("apps.trade.urls")),
    path("api/", include("apps.tasks.urls")),
    path("api/masters/", include("apps.core.urls")),

    # Serve media files in development
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),

    # Serve React assets directly
    re_path(
        r"^assets/(?P<path>.*)$",
        serve,
        {"document_root": settings.BASE_DIR.parent / "frontend" / "dist" / "assets"},
    ),

    # Serve React frontend for all other routes (must be last)
    re_path(r"^.*$", TemplateView.as_view(template_name="index.html")),
]
