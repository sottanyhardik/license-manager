"""Regression contracts for the paginated ``/api/trade/trades/`` collection.

These tests deliberately exercise the public API rather than private queryset
implementation details.  They freeze the response shape and the request
semantics while allowing the view to improve its query plan.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.trade.models import LicenseTrade, LicenseTradePayment


pytestmark = pytest.mark.django_db


LIST_METADATA = {
    "count",
    "next",
    "previous",
    "page_size",
    "total_pages",
    "current_page",
    "results",
}

TRADE_FIELDS = {
    "id",
    "direction",
    "license_type",
    "invoice_number",
    "invoice_date",
    "remarks",
    "subtotal_amount",
    "roundoff",
    "total_amount",
    "from_company",
    "to_company",
    "from_company_label",
    "to_company_label",
    "direction_label",
    "license_type_label",
    "incentive_license",
    "boes",
    "lines",
    "incentive_lines",
    "payments",
    "paid_or_received",
    "due_amount",
    "linked_trade_info",
    "counterpart_info",
}


def _results(response):
    assert response.status_code == status.HTTP_200_OK, response.data
    assert LIST_METADATA <= set(response.data)
    return response.data["results"]


def _make_trade_like(source, *, invoice_number, invoice_date):
    """Create a header-only row for collection-query scaling assertions.

    Header-only records are valid historical rows and keep this query test
    focused on collection serialization; the representative source record
    still supplies nested line/payment coverage.
    """
    return LicenseTrade.objects.create(
        direction=source.direction,
        license_type=source.license_type,
        from_company=source.from_company,
        to_company=source.to_company,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        remarks="contract scale fixture",
    )


def test_list_contract_keeps_pagination_nested_values_nulls_and_precision(
    authenticated_client, test_trade
):
    """The optimized collection must retain every public serialized value."""
    LicenseTradePayment.objects.create(
        trade=test_trade,
        date=test_trade.invoice_date,
        amount=Decimal("12.34"),
        note="Part payment",
    )

    response = authenticated_client.get(reverse("trade:trade-list"), {"page_size": 25})
    rows = _results(response)
    row = next(item for item in rows if item["id"] == test_trade.id)

    assert TRADE_FIELDS <= set(row)
    assert row["invoice_number"] == test_trade.invoice_number
    # Despite the field name, this display value includes DFIA licences found
    # through line items.  That legacy response meaning is contractual.
    assert row["incentive_license"] == test_trade.lines.first().sr_number.license.license_number
    assert row["linked_trade_info"] is None
    assert row["counterpart_info"] is None
    assert row["purchase_invoice_copy"] is None
    assert len(row["lines"]) == 3
    assert row["payments"] == [
        {"id": str(LicenseTradePayment.objects.get(trade=test_trade).id),
         "date": test_trade.invoice_date.strftime("%d-%m-%Y"), "amount": "12.34", "note": "Part payment"}
    ]
    # Decimal fields remain JSON decimal strings; zeros and four decimal
    # quantity precision are not coerced to floats by the list endpoint.
    first_line = row["lines"][0]
    assert isinstance(first_line["qty_kg"], str)
    assert first_line["qty_kg"].endswith(".0000")
    assert isinstance(row["paid_or_received"], str)
    assert row["paid_or_received"] == "12.34"
    assert row["due_amount"] == str(test_trade.total_amount - Decimal("12.34"))


def test_list_contract_preserves_filter_search_date_ordering_and_pagination(
    authenticated_client, test_trade
):
    second = _make_trade_like(
        test_trade,
        invoice_number="ZZ-CONTRACT-SECOND",
        invoice_date=test_trade.invoice_date + timedelta(days=1),
    )
    sale = LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_SALE,
        license_type=test_trade.license_type,
        from_company=test_trade.from_company,
        to_company=test_trade.to_company,
        invoice_number="AA-CONTRACT-SALE",
        invoice_date=test_trade.invoice_date + timedelta(days=2),
    )
    url = reverse("trade:trade-list")

    # Exact direction, search and date-range inputs are all public query keys.
    response = authenticated_client.get(
        url,
        {
            "direction": "PURCHASE",
            "search": "CONTRACT",
            "invoice_date_from": test_trade.invoice_date.isoformat(),
            "invoice_date_to": second.invoice_date.isoformat(),
            "ordering": "invoice_number",
            "page_size": 1,
            "page": 1,
        },
    )
    rows = _results(response)
    assert response.data["count"] == 1
    assert response.data["page_size"] == 1
    assert response.data["current_page"] == 1
    assert [item["id"] for item in rows] == [second.id]

    # A discrete filter never changes the default ordered list's response
    # metadata, and unrelated direction rows remain excluded.
    response = authenticated_client.get(url, {"direction": "SALE", "page_size": 25})
    rows = _results(response)
    assert [item["id"] for item in rows] == [sale.id]


def test_list_contract_keeps_permission_gate(test_trade):
    url = reverse("trade:trade-list")
    anonymous = APIClient()
    assert anonymous.get(url).status_code == status.HTTP_401_UNAUTHORIZED
    assert test_trade.id


def test_list_contract_bad_page_error_shape(authenticated_client, test_trade):
    response = authenticated_client.get(reverse("trade:trade-list"), {"page": "not-a-page"})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert set(response.data) == {"detail"}
    assert isinstance(response.data["detail"], str)


def test_list_contract_preserves_manual_link_metadata(authenticated_client, test_trade):
    """Direct and reverse legacy links retain the same metadata contract.

    The query optimization replaces ``paired_trades.first()`` only when the
    reverse relation is prefetched.  This test protects the legacy fallback
    used by manually linked, pre-counterpart transactions.
    """
    linked = LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_SALE,
        license_type=test_trade.license_type,
        from_company=test_trade.from_company,
        to_company=test_trade.to_company,
        invoice_number="LINKED-CONTRACT-001",
        invoice_date=test_trade.invoice_date + timedelta(days=1),
        linked_trade=test_trade,
    )
    LicenseTradePayment.objects.create(
        trade=linked,
        date=linked.invoice_date,
        amount=Decimal("7.89"),
        note="linked settlement",
    )

    rows = _results(authenticated_client.get(reverse("trade:trade-list"), {"page_size": 25}))
    by_id = {row["id"]: row for row in rows}

    source_metadata = by_id[test_trade.id]["linked_trade_info"]
    linked_metadata = by_id[linked.id]["linked_trade_info"]
    assert source_metadata["id"] == linked.id
    assert source_metadata["invoice_number"] == linked.invoice_number
    assert source_metadata["paid_or_received"] == "7.89"
    assert linked_metadata["id"] == test_trade.id
    assert linked_metadata["invoice_number"] == test_trade.invoice_number


def test_list_query_count_does_not_grow_per_trade(authenticated_client, test_trade):
    """Regression guard: page serialization stays bounded as result rows grow.

    The limit allows the count, main select and intentional relation prefetches,
    but fails the historical per-trade payment/paired-trade queries.
    """
    for number in range(8):
        _make_trade_like(
            test_trade,
            invoice_number=f"QUERY-SCALE-{number:02d}",
            invoice_date=date(2026, 1, 1) + timedelta(days=number),
        )

    with CaptureQueriesContext(connection) as context:
        response = authenticated_client.get(reverse("trade:trade-list"), {"page_size": 25})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 9
    # Intentional bounded queries: count, page, nested relation prefetches,
    # and database-level totals.  Keep this threshold small enough to catch a
    # one-query-per-row regression while remaining database-backend agnostic.
    assert len(context) <= 14, "\n".join(query["sql"] for query in context.captured_queries)
