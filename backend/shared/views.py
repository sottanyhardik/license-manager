from django.http import JsonResponse


def health_check_view(request):
    """
    Simple health check endpoint. No authentication required.
    Returns {"status": "ok", "version": "1.0.0"}
    """
    return JsonResponse({"status": "ok", "version": "1.0.0"})
