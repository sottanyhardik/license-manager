"""
Liveness/readiness endpoint for deploy scripts and monitoring.

GET /api/health/

Returns 200 with {"status": "ok"} if Django can reach the DB and cache.
Returns 503 otherwise with the same shape (no internal details exposed).

Intentionally public — protected only by the global anon throttle (300/hour).
Do NOT add fields that leak backend identifiers, versions, or config.
"""
from django.core.cache import cache
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        if self._db_ok() and self._cache_ok():
            return Response({"status": "ok"})
        return Response({"status": "degraded"}, status=503)

    @staticmethod
    def _db_ok():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
        except Exception:
            return False

    @staticmethod
    def _cache_ok():
        try:
            cache.set("__health__", "1", 5)
            return cache.get("__health__") == "1"
        except Exception:
            return False
