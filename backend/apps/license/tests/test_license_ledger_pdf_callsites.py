"""Statement PDF routes remain thin delegates to the canonical generator."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from rest_framework.test import APIRequestFactory

from apps.license.views.ledger import LicenseLedgerViewSet


def _request(path):
    view = LicenseLedgerViewSet()
    view.action_map = {}
    request = view.initialize_request(APIRequestFactory().get(path))
    request._user = SimpleNamespace(is_authenticated=True)
    return view, request


def test_direct_financial_statement_route_delegates_to_canonical_generator():
    view, request = _request("/api/license-ledger/17/financial-ledger-pdf/?license_type=DFIA")
    licence = SimpleNamespace(id=17, license_number="LIC-17")
    with patch.object(view, "_authorized_license", return_value=("DFIA", licence)), patch(
        "apps.license.services.license_ledger_export.generate_license_ledger_statement_pdf",
        return_value=BytesIO(b"%PDF"),
    ) as generate:
        response = view.financial_ledger_pdf(request, pk="17")

    generate.assert_called_once_with(
        query_params=request.query_params,
        user=request.user,
        base_url="http://testserver/",
        license_ref=(17, "DFIA"),
    )
    assert response["Content-Type"] == "application/pdf"


def test_collection_pdf_export_delegates_its_materialized_dataset_once():
    view, request = _request("/api/license-ledger/export/?file_format=pdf&license_id=17")
    dataset = {"licenses": [{"license_id": 17}]}
    licence = SimpleNamespace(id=17, license_number="LIC-17")
    with patch.object(view, "_authorized_license", return_value=("DFIA", licence)), patch(
        "apps.license.services.license_ledger_export.build_license_ledger_data",
        return_value=dataset,
    ), patch(
        "apps.license.services.license_ledger_export.generate_license_ledger_statement_pdf",
        return_value=BytesIO(b"%PDF"),
    ) as generate:
        response = view.export(request)

    generate.assert_called_once_with(
        user=request.user,
        base_url="http://testserver/",
        canonical_data=dataset,
    )
    assert response["Content-Type"] == "application/pdf"
