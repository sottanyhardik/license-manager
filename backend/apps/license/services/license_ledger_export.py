"""Shared License Ledger dataset builder and export dispatcher.

This module contains no accounting formula. It selects licenses, asks
``CanonicalLedgerService`` for each authoritative dataset, then passes those
same dictionaries to a presentation-only renderer.
"""
from __future__ import annotations

from apps.license.services.license_ledger_filters import build_filtered_license_ledger_data


def enrich_invoice_documents(canonical_data: dict, *, user, base_url="") -> dict:
    """Attach request-scoped secure invoice metadata to canonical rows.

    Accounting remains request-agnostic. This orchestration runs only after
    filtering/canonical calculation and reuses one resolved document/link per
    trade+bill version across all representations of that transaction.
    """
    from apps.trade.models import LicenseTrade
    from apps.trade.services.invoice_document_service import InvoiceDocumentService

    rows = []
    for dataset in canonical_data.get("licenses") or []:
        rows.extend(dataset.get("transactions") or [])
        rows.extend(dataset.get("display_transactions") or [])
    invoice_rows = [
        row for row in rows
        if row.get("type") in {"PURCHASE", "SALE"} and row.get("id") is not None
    ]
    trade_ids = {row.get("id") for row in invoice_rows}
    trades = {
        trade.pk: trade
        for trade in LicenseTrade.objects.filter(pk__in=trade_ids).select_related(
            "from_company", "to_company"
        ).prefetch_related("lines", "incentive_lines")
    }
    cache = {}
    for row in invoice_rows:
        trade = trades.get(row.get("id"))
        if not trade:
            continue
        sale_bill = row.get("sale_bill_amount")
        cache_key = (trade.pk, str(sale_bill) if sale_bill is not None else "purchase")
        result = cache.get(cache_key)
        if result is None:
            result = InvoiceDocumentService.resolve(
                trade,
                canonical_sale_bill_inr=sale_bill if trade.direction == LicenseTrade.DIR_SALE else None,
            )
            result = InvoiceDocumentService.issue_secure_link(
                result, trade=trade, user=user, base_url=base_url,
            )
            cache[cache_key] = result
        # A document resolver describes an optional uploaded copy; it is not
        # the source of the system transaction invoice number.  Never let an
        # absent copy overwrite the canonical Trade.invoice_number selected by
        # CanonicalLedgerService.
        canonical_number = row.get("invoice_number") or result.invoice_number
        row["invoice_number"] = canonical_number
        row["invoice_document"] = {
            "invoice_number": canonical_number,
            "document_exists": result.document_exists,
            "signed": result.signed,
            "status": result.status,
            "secure_url": result.secure_url,
        }
    return canonical_data


def build_license_ledger_data(query_params=None, *, company_id=None, license_ref=None) -> dict:
    """Return the shared filtered canonical collection for UI and exporters."""
    data = build_filtered_license_ledger_data(
        query_params or {}, authorization_company_id=company_id, license_ref=license_ref,
    )
    # Presentation context only.  A filtered list can legitimately contain a
    # single licence, so renderers must not guess the requested design from the
    # collection length.
    data["scope"] = "detail" if license_ref is not None else "list"
    return data


def generate_license_ledger_statement_pdf(
    *,
    query_params=None,
    user=None,
    base_url="",
    company_id=None,
    license_ref=None,
    canonical_data=None,
):
    """Generate the one canonical Financial License Ledger Statement PDF.

    All statement callers use this orchestration point.  Callers which have
    already materialised an authorized canonical dataset (for example a
    package builder) may pass it through ``canonical_data``; doing so avoids a
    second query without creating another calculation or rendering path.
    ``canonical_data`` must be the output shape of
    :func:`build_license_ledger_data` (at minimum its ``licenses`` collection).
    """
    if canonical_data is None:
        canonical_data = build_license_ledger_data(
            query_params, company_id=company_id, license_ref=license_ref,
        )
    if user is not None:
        enrich_invoice_documents(canonical_data, user=user, base_url=base_url)
    return render_license_ledger(canonical_data, "pdf")


def render_license_ledger(canonical_data: dict, file_format: str):
    """Render the same canonical dataset collection as PDF or Excel."""
    if file_format == "pdf":
        from apps.license.services.exporters.financial_ledger_pdf_renderer import render_financial_ledger_pdf
        return render_financial_ledger_pdf(canonical_data)
    if file_format == "xlsx":
        from apps.license.services.exporters.financial_ledger_excel_renderer import render_financial_ledger_excel
        return render_financial_ledger_excel(canonical_data)
    raise ValueError("format must be 'pdf' or 'xlsx'")
