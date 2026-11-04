"""Endpoint contract for paginated License Ledger collection responses.

Paging must slice only the licence rows and the page's company subtotals.
Totals, metrics and the full licence-id list always describe the complete
filtered collection, and exports must never be paginated.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.license.services.license_ledger_filters import LicenseLedgerFilters
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

LEDGER_EXPORT = "apps.license.services.license_ledger_export"


def _row(license_id):
    return {
        "license_id": license_id, "license_number": f"LIC-{license_id}", "license_type": "DFIA",
        "license_date": date(2026, 1, license_id), "expiry_date": None,
        "summary": {"current_balance": Decimal("10")}, "companies": [],
        "license_wise_companies": [], "display_transactions": [],
        "individual_ledger_projection": {}, "sion_norms": "",
    }


def _collection():
    rows = [_row(i) for i in (1, 2, 3)]
    return {
        "licenses": rows,
        "summary": {"dfia": {"total_licenses": 3}, "incentive": {}},
        "company_groups": [{"company_id": 9, "company_name": "FULL", "sion_groups": []}],
        "grand_total": {"license_count": 3, "total_purchase_bill_inr": "0.00",
                        "total_sale_bill_inr": "0.00", "total_balance": "30.00",
                        "total_profit_loss_inr": "0.00"},
        "metrics": {"total_licences": 3, "as_of": "2026-11-04"},
    }


@pytest.mark.django_db
def test_paged_response_slices_rows_but_keeps_totals_and_ids_complete(authenticated_client):
    seen_company_input = {}

    def fake_company_groups(datasets):
        seen_company_input["ids"] = [row["license_id"] for row in datasets]
        return [{"company_id": 1, "company_name": "PAGE", "sion_groups": []}]

    with patch(f"{LEDGER_EXPORT}.build_license_ledger_data", return_value=_collection()), \
         patch.object(CanonicalLedgerService, "build_collection_company_groups", side_effect=fake_company_groups):
        response = authenticated_client.get(
            reverse("license:license-ledger-license-wise"), {"page": "2", "page_size": "2"},
        )

    assert response.status_code == 200
    payload = response.json()
    # Only the page's licence rows, and only the page's subtotals.
    assert [row["license_id"] for row in payload["licenses"]] == [3]
    assert seen_company_input["ids"] == [3]
    assert payload["company_groups"][0]["company_name"] == "PAGE"
    # Totals, metrics and the full id list describe the whole filtered collection.
    assert payload["grand_total"]["license_count"] == 3
    assert payload["metrics"]["total_licences"] == 3
    assert payload["license_ids"] == ["DFIA:1", "DFIA:2", "DFIA:3"]
    assert payload["pagination"] == {"count": 3, "page": 2, "page_size": 2,
                                     "total_pages": 2, "has_next": False, "paginated": True}


@pytest.mark.django_db
def test_unpaged_response_keeps_the_full_collection_hierarchy(authenticated_client):
    with patch(f"{LEDGER_EXPORT}.build_license_ledger_data", return_value=_collection()):
        payload = authenticated_client.get(reverse("license:license-ledger-license-wise")).json()
    assert [row["license_id"] for row in payload["licenses"]] == [1, 2, 3]
    assert payload["company_groups"][0]["company_name"] == "FULL"
    assert payload["pagination"]["paginated"] is False


def test_export_filter_parsing_ignores_paging_parameters():
    """Exports never paginate: paging keys cannot change the filtered collection."""
    plain = LicenseLedgerFilters.from_query_params({"license_type": "DFIA"})
    paged = LicenseLedgerFilters.from_query_params({"license_type": "DFIA", "page": "3", "page_size": "1"})
    assert plain == paged
