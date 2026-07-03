from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthz(_request):
    """Liveness probe for devops-sre / load balancers."""
    return JsonResponse({"status": "ok", "service": "master-data-service"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("api/v1/", include("masters.urls")),
]
