from types import SimpleNamespace

from django.core.cache import cache
from django.test import RequestFactory
from rest_framework.response import Response

from apps.core.cache_utils import cache_query, cache_view, generate_cache_key


def test_generate_cache_key_is_stable_for_sorted_kwargs():
    assert generate_cache_key("master", company=1, active=True) == generate_cache_key(
        "master",
        active=True,
        company=1,
    )


def test_cache_query_reuses_cached_non_none_result():
    cache.clear()
    calls = {"count": 0}

    @cache_query("master-test", timeout=30)
    def load_value(value):
        calls["count"] += 1
        return {"value": value}

    assert load_value("iec") == {"value": "iec"}
    assert load_value("iec") == {"value": "iec"}
    assert calls["count"] == 1


def test_cache_view_caches_successful_get_response_by_user_and_query_params():
    cache.clear()
    factory = RequestFactory()
    calls = {"count": 0}

    @cache_view(timeout=30, key_prefix="master-list")
    def view(request):
        calls["count"] += 1
        return Response({"count": calls["count"]})

    request = factory.get("/masters/", {"page": "1"})
    request.user = SimpleNamespace(id=7)

    first_response = view(request)
    second_response = view(request)

    assert first_response.data == {"count": 1}
    assert second_response.data == {"count": 1}
    assert calls["count"] == 1


def test_cache_view_skips_non_get_requests():
    cache.clear()
    factory = RequestFactory()
    calls = {"count": 0}

    @cache_view(timeout=30, key_prefix="master-list")
    def view(request):
        calls["count"] += 1
        return Response({"count": calls["count"]})

    request = factory.post("/masters/")
    request.user = SimpleNamespace(id=7)

    assert view(request).data == {"count": 1}
    assert view(request).data == {"count": 2}
    assert calls["count"] == 2
