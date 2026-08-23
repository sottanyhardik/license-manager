import json
from unittest.mock import Mock

from django.core.cache import cache
from django.test import RequestFactory

from apps.license.views.item_pivot_report import ItemPivotReportView


def test_item_pivot_json_response_cache_reuses_identical_complete_query():
    """The cache is keyed by every supplied query value, not just a subset.

    This keeps expensive report projection work out of repeated navigation
    requests while retaining the response body exactly as generated.
    """
    cache.clear()
    try:
        view = ItemPivotReportView()
        view.generate_report = Mock(return_value={"groups": [], "summary": {"license_count": 0}})
        factory = RequestFactory()

        first = view.get(factory.get("/item-pivot/?days=30&sion_norm=E132&purchase_status=GE,MI"))
        second = view.get(factory.get("/item-pivot/?purchase_status=GE,MI&sion_norm=E132&days=30"))

        assert first.status_code == second.status_code == 200
        assert json.loads(first.content) == json.loads(second.content) == {
            "groups": [], "summary": {"license_count": 0}
        }
        assert view.generate_report.call_count == 1
    finally:
        cache.clear()


def test_item_pivot_json_response_cache_misses_when_a_query_value_changes():
    cache.clear()
    try:
        view = ItemPivotReportView()
        view.generate_report = Mock(side_effect=[{"marker": "E132"}, {"marker": "E1"}])
        factory = RequestFactory()

        first = view.get(factory.get("/item-pivot/?days=30&sion_norm=E132"))
        second = view.get(factory.get("/item-pivot/?days=30&sion_norm=E1"))

        assert json.loads(first.content) == {"marker": "E132"}
        assert json.loads(second.content) == {"marker": "E1"}
        assert view.generate_report.call_count == 2
    finally:
        cache.clear()
