from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView as SpectacularSwaggerUIView
from shared.views import health_check_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check_view, name="health-check"),
    path("api/v1/", include("config.api_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerUIView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
