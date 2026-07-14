# lmanagement/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.views.static import serve
from django.conf import settings
from django.http import JsonResponse

from rest_framework.permissions import IsAuthenticated

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from apps.core.views.health import HealthView
from apps.core.views.mds_status import MDSStatusView
from apps.core.views.media import ProtectedMediaView

_schema_permission = [] if settings.DEBUG else [IsAuthenticated]


def _api_404(request, *args, **kwargs):
    return JsonResponse(
        {"detail": "Not found."},
        status=404,
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="api-health"),
    path("api/mds/status/", MDSStatusView.as_view(), name="mds-status"),

    # OpenAPI schema + interactive docs (gated in production)
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=_schema_permission), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=_schema_permission), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema", permission_classes=_schema_permission), name="redoc"),

    # Authenticated media/document downloads (replaces public /media/ — see
    # apps.core.views.media.ProtectedMediaView and docs/08-security.md).
    re_path(r"^api/media/(?P<path>.+)$", ProtectedMediaView.as_view(), name="protected-media"),
    path("api/auth/", include("apps.accounts.urls", namespace="accounts")),
    path("api/", include("apps.license.urls", namespace="license")),
    path("api/", include("apps.allotment.urls", namespace="allotment")),
    path("api/", include("apps.bill_of_entry.urls", namespace="bill_of_entry")),
    path("api/", include("apps.trade.urls", namespace="trade")),
    path("api/", include("apps.tasks.urls", namespace="tasks")),
    path("api/masters/", include("apps.core.urls", namespace="masters")),

    # JSON 404 for any unmatched /api/ path (must come after all real api/ patterns,
    # before the SPA catch-all)
    re_path(r"^api/", _api_404),
]

# Development-only static file serving — must be inserted BEFORE the SPA catch-all
# so Django resolves ^media/ and ^assets/ ahead of ^.*$.
if settings.DEBUG:
    urlpatterns += [
        # Serve media files in development only
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
        # Serve React assets directly in development only
        re_path(
            r"^assets/(?P<path>.*)$",
            serve,
            {"document_root": settings.BASE_DIR.parent / "frontend" / "dist" / "assets"},
        ),
    ]

# SPA catch-all — must be absolutely last so every explicit pattern above takes priority.
urlpatterns += [
    re_path(r"^.*$", TemplateView.as_view(template_name="index.html")),
]
