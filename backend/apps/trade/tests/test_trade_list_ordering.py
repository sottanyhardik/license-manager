"""Regression coverage for ``GET /api/trades/?page=1&page_size=25&ordering=-invoice_date``.

Incident 2026-11-17: the list returned HTTP 500 because the DB lacked the
``trade.0012`` columns that the ``lines`` prefetch selects.  These tests run on
a fully migrated test DB, so they pin the list contract (ordering, null dates,
pagination, search/filter, shape, query budget) end to end.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.trade.models import LicenseTrade, LicenseTradeLine

URL = reverse("trade:trade-list")
BASE_DATE = date(2026, 1, 1)


def _trade(from_company, to_company, number, invoice_date, direction="PURCHASE"):
    trade = LicenseTrade.objects.create(
        direction=direction,
        from_company=from_company,
        to_company=to_company,
        invoice_number=number,
        invoice_date=invoice_date,
        total_amount=Decimal("100.00"),
    )
    if invoice_date is None:
        # ``save()`` back-fills a missing date with today; legacy/imported rows
        # can still hold NULL, so write it the way bulk paths do.
        LicenseTrade.objects.filter(pk=trade.pk).update(invoice_date=None)
        trade.invoice_date = None
    return trade


def _ids(response):
    return [row["id"] for row in response.data["results"]]


@pytest.fixture
def make_trade(test_company, test_company_2):
    def factory(number, invoice_date, direction="PURCHASE"):
        return _trade(test_company, test_company_2, number, invoice_date, direction)

    return factory


@pytest.mark.django_db
class TestTradeListOrdering:
    def test_empty_list(self, authenticated_client):
        response = authenticated_client.get(URL, {"page": 1, "page_size": 25, "ordering": "-invoice_date"})
        assert response.status_code == 200
        assert response.data["count"] == 0
        assert response.data["results"] == []

    def test_exact_incident_request_returns_newest_first(self, authenticated_client, make_trade):
        old = make_trade("ORD-OLD", BASE_DATE)
        new = make_trade("ORD-NEW", BASE_DATE + timedelta(days=5))
        mid = make_trade("ORD-MID", BASE_DATE + timedelta(days=2))

        response = authenticated_client.get(URL, {"page": 1, "page_size": 25, "ordering": "-invoice_date"})

        assert response.status_code == 200
        assert _ids(response) == [new.id, mid.id, old.id]

    @pytest.mark.parametrize("params", [{}, {"ordering": "invoice_date"}, {"ordering": "-invoice_date"}])
    def test_register_order_is_enforced_for_any_client_ordering(self, authenticated_client, make_trade, params):
        """Existing contract: the list is a newest-invoice register regardless of ``ordering``."""
        old = make_trade("ENF-OLD", BASE_DATE)
        new = make_trade("ENF-NEW", BASE_DATE + timedelta(days=1))

        response = authenticated_client.get(URL, {"page_size": 25, **params})

        assert response.status_code == 200
        assert _ids(response) == [new.id, old.id]

    def test_null_invoice_dates_sort_last_without_error(self, authenticated_client, make_trade):
        undated = make_trade("NULL-DATE", None)
        dated = make_trade("HAS-DATE", BASE_DATE)

        response = authenticated_client.get(URL, {"page": 1, "page_size": 25, "ordering": "-invoice_date"})

        assert response.status_code == 200
        assert _ids(response) == [dated.id, undated.id]
        assert response.data["results"][1]["invoice_date"] is None

    def test_same_date_ties_break_by_newest_id(self, authenticated_client, make_trade):
        first = make_trade("TIE-1", BASE_DATE)
        second = make_trade("TIE-2", BASE_DATE)

        response = authenticated_client.get(URL, {"page_size": 25, "ordering": "-invoice_date"})

        assert _ids(response) == [second.id, first.id]

    def test_pagination_is_complete_and_disjoint_across_pages(self, authenticated_client, make_trade):
        """Same-date trades must not repeat or vanish between LIMIT/OFFSET pages."""
        created = [make_trade(f"PG-{i:02d}", BASE_DATE + timedelta(days=i % 3)) for i in range(7)]
        created.append(make_trade("PG-NULL", None))

        seen = []
        for page in (1, 2, 3):
            response = authenticated_client.get(URL, {"page": page, "page_size": 3, "ordering": "-invoice_date"})
            assert response.status_code == 200
            assert response.data["count"] == 8
            seen.extend(_ids(response))

        assert len(seen) == len(set(seen)) == 8
        assert set(seen) == {t.id for t in created}
        assert seen[-1] == created[-1].id  # undated trade is last

        beyond = authenticated_client.get(URL, {"page": 4, "page_size": 3})
        assert beyond.status_code == 404

    def test_trades_without_lines_or_boes_serialize(self, authenticated_client, make_trade):
        bare = make_trade("BARE-1", BASE_DATE)

        response = authenticated_client.get(URL, {"page_size": 25})

        row = response.data["results"][0]
        assert row["id"] == bare.id
        assert row["lines"] == []
        assert row["boes"] == []

    def test_search_and_filter_compose_with_ordering(self, authenticated_client, make_trade):
        sale_old = make_trade("FLT-SALE-A", BASE_DATE, direction="SALE")
        sale_new = make_trade("FLT-SALE-B", BASE_DATE + timedelta(days=1), direction="SALE")
        make_trade("FLT-PURCHASE", BASE_DATE + timedelta(days=2))

        filtered = authenticated_client.get(URL, {"direction": "SALE", "ordering": "-invoice_date"})
        assert filtered.status_code == 200
        assert _ids(filtered) == [sale_new.id, sale_old.id]

        searched = authenticated_client.get(URL, {"search": "FLT-SALE-B", "ordering": "-invoice_date"})
        assert searched.status_code == 200
        assert _ids(searched) == [sale_new.id]

    def test_line_search_join_does_not_duplicate_trades(self, authenticated_client, test_trade):
        """Searching across ``lines__...`` joins must still return each trade once."""
        licence_number = test_trade.lines.first().sr_number.license.license_number
        assert test_trade.lines.count() >= 1

        response = authenticated_client.get(URL, {"search": licence_number, "page_size": 25})

        assert response.status_code == 200
        assert _ids(response).count(test_trade.id) == 1
        assert response.data["count"] == len(set(_ids(response)))

    def test_serializer_shape_with_lines(self, authenticated_client, test_trade):
        response = authenticated_client.get(URL, {"page": 1, "page_size": 25, "ordering": "-invoice_date"})

        assert response.status_code == 200
        row = next(r for r in response.data["results"] if r["id"] == test_trade.id)
        for key in ("id", "direction", "invoice_number", "invoice_date", "lines", "boes", "payments",
                    "paid_or_received", "due_amount"):
            assert key in row, key
        # Existing contract: nested line ids serialize as strings.
        assert {line["id"] for line in row["lines"]} == {
            str(pk) for pk in LicenseTradeLine.objects.filter(trade=test_trade).values_list("id", flat=True)
        }

    def test_query_count_does_not_grow_with_trade_count(self, authenticated_client, test_trade, make_trade):
        def measure():
            with CaptureQueriesContext(connection) as ctx:
                response = authenticated_client.get(
                    URL, {"page": 1, "page_size": 25, "ordering": "-invoice_date"}
                )
            assert response.status_code == 200
            return len(ctx.captured_queries)

        baseline = measure()
        for i in range(6):
            make_trade(f"QC-{i}", BASE_DATE + timedelta(days=i))
        assert measure() <= baseline
