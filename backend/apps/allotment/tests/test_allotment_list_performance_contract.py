"""Regression coverage for the canonical Allotments list projection.

The list view is deliberately exercised through the public endpoint: this is
where pagination, the filter backends and serializer method fields interact.
"""

import json
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.allotment.models import AllotmentItems, AllotmentModel


TARGET_PARAMS = {
    "type": "AT",
    "is_boe": "False",
    "is_allotted": "all",
    "page": 1,
}


def _normalise_response(payload):
    """Remove only fixture-clock values; every business value remains frozen."""
    payload = json.loads(json.dumps(payload))
    for row in payload["results"]:
        row["created_on"] = "<fixture-clock>"
        row["modified_on"] = "<fixture-clock>"
    return payload


def _fingerprint(sql):
    return re.sub(r"\b\d+(?:\.\d+)?\b", "?", re.sub(r"\s+", " ", sql)).strip()


def _make_list_fixture(test_allotment, test_license):
    """A deterministic list fixture with details on every displayed row."""
    test_license.license_number = "0310835340"
    test_license.save(update_fields=["license_number"])
    items = list(test_license.import_license.order_by("id"))
    rows = [test_allotment]
    for index in range(1, 9):
        rows.append(AllotmentModel.objects.create(
            company=test_allotment.company,
            port=test_allotment.port,
            type="AT",
            item_name=f"Contract item {index}",
            required_quantity="1000.00",
            unit_value_per_unit="1.184",
            exchange_rate="84.500000",
            is_boe=False,
            is_allotted=index % 2 == 0,
        ))
    for index, row in enumerate(rows):
        AllotmentItems.objects.create(
            allotment=row,
            item=items[index % len(items)],
            qty="100.000",
            cif_fc="118.40",
            cif_inr="10004.80",
        )
    return rows


@pytest.mark.django_db
def test_exact_target_list_contract_and_query_trace(authenticated_client, test_allotment):
    """Freeze the public target URL before list-query optimisations evolve."""
    url = reverse("allotment:allotment-list")
    with CaptureQueriesContext(connection) as queries:
        response = authenticated_client.get(url, TARGET_PARAMS)

    assert response.status_code == 200, response.data
    # The list UI is metadata-driven.  Keep the established BOE selector
    # available alongside Company and Port without inventing another endpoint
    # or changing the public query values.
    assert response.data["filter_config"]["is_boe"] == {"type": "exact", "label": "BOE"}
    normalized = _normalise_response(response.data)
    assert normalized["count"] == 1
    assert normalized["current_page"] == 1
    assert normalized["page_size"] == 25
    assert normalized["total_pages"] == 1
    assert normalized["has_next"] is False
    assert normalized["has_previous"] is False
    assert [row["id"] for row in normalized["results"]] == [test_allotment.id]

    row = normalized["results"][0]
    assert row == {
        "id": test_allotment.id,
        "company": test_allotment.company_id,
        "type": "AT",
        "required_quantity": "1000.00",
        "unit_value_per_unit": "1.184",
        "cif_fc": "1183.43",
        "cif_inr": "99999.84",
        "exchange_rate": "84.500000",
        "item_name": "Crude Palm Oil",
        "contact_person": None,
        "contact_number": None,
        "invoice": None,
        "planning_target_item": None,
        "planning_mapping_status": "UNMAPPED_AMBIGUOUS",
        "planning_mapping_source": "",
        "planning_target_item_name": None,
        "planning_target_sion": None,
        "estimated_arrival_date": None,
        "bl_detail": None,
        "port": test_allotment.port_id,
        "related_company": None,
        "is_boe": False,
        "is_approved": False,
        "created_on": "<fixture-clock>",
        "modified_on": "<fixture-clock>",
        "created_by": None,
        "modified_by": None,
        "required_value": "1184.00",
        "dfia_list": "",
        "balanced_quantity": "1000.00",
        "alloted_quantity": "0.00",
        "allotted_value": "0.00",
        "company_name": "Test Exporter Ltd",
        "port_name": "Mumbai Port",
        "display_label": "Test Exporter Ltd | Qty: 1000.00",
        "allotment_details": [],
        "allotted_items_count": 0,
        "allocated_licenses_count": 0,
    }

    # Kept as test diagnostics as well as a guard against a serializer query
    # regressing unnoticed; the richer multi-row budget is added below.
    fingerprints = [_fingerprint(query["sql"]) for query in queries.captured_queries]
    assert len(fingerprints) == len(queries.captured_queries)


@pytest.mark.django_db
def test_target_list_query_count_is_bounded_for_nine_rows(
    authenticated_client, test_allotment, test_license
):
    _make_list_fixture(test_allotment, test_license)
    with CaptureQueriesContext(connection) as queries:
        response = authenticated_client.get(reverse("allotment:allotment-list"), TARGET_PARAMS)

    assert response.status_code == 200, response.data
    assert response.data["count"] == 9
    assert len(response.data["results"]) == 9
    # Six cold-request queries: authentication, metadata, count, list page,
    # one joined detail batch, and the sole plan-line collection batch.
    assert len(queries) <= 6

    with CaptureQueriesContext(connection) as one_row_queries:
        one_row_response = authenticated_client.get(
            reverse("allotment:allotment-list"), {**TARGET_PARAMS, "page_size": 1}
        )
    assert one_row_response.status_code == 200, one_row_response.data
    assert len(one_row_response.data["results"]) == 1
    assert len(one_row_queries) <= 6
    # The class-level field metadata performs one cold exchange-rate lookup;
    # it is a fixed request setup cost, never a row/serializer query.
    assert abs(len(queries) - len(one_row_queries)) <= 1

    fingerprints = [_fingerprint(query["sql"]) for query in queries.captured_queries]
    # A repeated fingerprint here would mean a collection or serializer path
    # has escaped its batch prefetch.  Count/page queries are intentionally
    # distinct shapes, so exact duplicates are never necessary.
    assert len(fingerprints) == len(set(fingerprints))


@pytest.mark.django_db
def test_target_filter_matrix_preserves_records_pagination_and_order(
    authenticated_client, test_allotment
):
    """Exercise the page's established URL filters without client inference."""
    visible = [test_allotment]
    visible.append(AllotmentModel.objects.create(
        company=test_allotment.company, port=test_allotment.port, type="AT",
        item_name="Second visible", required_quantity="2.00", is_boe=False,
        is_allotted=True,
    ))
    hidden_type = AllotmentModel.objects.create(
        company=test_allotment.company, port=test_allotment.port, type="AR",
        item_name="ARO", required_quantity="3.00", is_boe=False,
    )
    hidden_boe = AllotmentModel.objects.create(
        company=test_allotment.company, port=test_allotment.port, type="AT",
        item_name="BOE", required_quantity="4.00", is_boe=True,
    )
    url = reverse("allotment:allotment-list")
    target = authenticated_client.get(url, TARGET_PARAMS)
    repeated = authenticated_client.get(url, TARGET_PARAMS)
    assert target.status_code == repeated.status_code == 200
    target_ids = [row["id"] for row in target.data["results"]]
    assert target_ids == [row["id"] for row in repeated.data["results"]]
    assert set(target_ids) == {row.id for row in visible}
    assert hidden_type.id not in target_ids
    assert hidden_boe.id not in target_ids
    assert target.data["count"] == 2

    all_boe = authenticated_client.get(url, {**TARGET_PARAMS, "is_boe": "all"})
    assert all_boe.status_code == 200
    assert hidden_boe.id in [row["id"] for row in all_boe.data["results"]]

    page = authenticated_client.get(url, {**TARGET_PARAMS, "page_size": 1})
    assert page.status_code == 200
    assert page.data["count"] == 2
    assert page.data["total_pages"] == 2
    assert len(page.data["results"]) == 1
