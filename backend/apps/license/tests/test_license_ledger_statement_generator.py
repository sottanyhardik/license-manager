"""Contracts for the one public Financial Ledger PDF orchestration point."""
from io import BytesIO
from unittest.mock import patch

from apps.license.services.license_ledger_export import (
    generate_license_ledger_statement_pdf,
)


def test_statement_generator_builds_once_enriches_once_and_renders_pdf():
    dataset = {"licenses": [{"license_id": 17}]}
    user = object()
    with patch(
        "apps.license.services.license_ledger_export.build_license_ledger_data",
        return_value=dataset,
    ) as build, patch(
        "apps.license.services.license_ledger_export.enrich_invoice_documents",
    ) as enrich, patch(
        "apps.license.services.license_ledger_export.render_license_ledger",
        return_value=BytesIO(b"%PDF"),
    ) as render:
        result = generate_license_ledger_statement_pdf(
            query_params={"license_id": "17"}, user=user,
            base_url="http://testserver/", company_id=4, license_ref=(17, "DFIA"),
        )

    assert result.getvalue() == b"%PDF"
    build.assert_called_once_with(
        {"license_id": "17"}, company_id=4, license_ref=(17, "DFIA"),
    )
    enrich.assert_called_once_with(dataset, user=user, base_url="http://testserver/")
    render.assert_called_once_with(dataset, "pdf")


def test_statement_generator_reuses_a_materialized_dataset_without_requerying():
    dataset = {"licenses": [{"license_id": 17}]}
    with patch(
        "apps.license.services.license_ledger_export.build_license_ledger_data",
    ) as build, patch(
        "apps.license.services.license_ledger_export.enrich_invoice_documents",
    ) as enrich, patch(
        "apps.license.services.license_ledger_export.render_license_ledger",
        return_value=BytesIO(b"%PDF"),
    ) as render:
        generate_license_ledger_statement_pdf(canonical_data=dataset)

    build.assert_not_called()
    enrich.assert_not_called()
    render.assert_called_once_with(dataset, "pdf")
