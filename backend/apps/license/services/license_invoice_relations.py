"""Canonical trade/invoice candidates for a licence download package.

The invoice header is :class:`trade.LicenseTrade`; its ``invoice_number`` is
the sole invoice-number authority for both purchase and system-generated sale
documents.  Physical documents are deliberately represented separately:
purchase files live in ``purchase_invoice_copy`` and sale render versions in
``TradeInvoiceDocument``.  Neither may replace the header number.

This module makes the relationship decisions auditable without doing filename,
party-name, or date matching.  It is read-only and can be reused by the ZIP
builder and manifest.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from django.db.models import Exists, OuterRef, Prefetch

from apps.trade.models import LicenseTrade, LicenseTradeLine


def _json_date(value):
    """Return a JSON-safe, stable audit value for a date/datetime field."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def _trade_queryset(licence):
    """Return direct trade rows for *licence* with only linked line records.

    The relationship is ``LicenseTradeLine.sr_number -> LicenseImportItemsModel
    -> LicenseDetailsModel``.  It is the only eligible relation here; do not
    broaden it to a similarly named party, invoice, or uploaded file.
    """
    licence_lines = LicenseTradeLine.objects.filter(sr_number__license=licence).select_related("sr_number")
    # Historic links are not guaranteed to have been saved reciprocally.  A
    # reverse edge is nevertheless an explicit graph fact and must prevent
    # either side from being presented as a standalone terminal sale.
    reverse_links = LicenseTrade.objects.filter(linked_trade_id=OuterRef("pk"))
    reverse_counterparts = LicenseTrade.objects.filter(counterpart_id=OuterRef("pk"))
    reverse_copies = LicenseTrade.objects.filter(copied_from_id=OuterRef("pk"))
    return (
        LicenseTrade.objects.filter(lines__sr_number__license=licence)
        .distinct()
        .annotate(
            package_has_reverse_link=Exists(reverse_links),
            package_has_reverse_counterpart=Exists(reverse_counterparts),
            package_has_reverse_copy=Exists(reverse_copies),
        )
        .select_related("from_company", "to_company", "final_party", "linked_trade", "counterpart", "copied_from")
        .prefetch_related(
            Prefetch("lines", queryset=licence_lines, to_attr="package_licence_lines"),
            "generated_invoice_documents",
        )
        .order_by("invoice_date", "invoice_number", "pk")
    )


def _is_interlinked(trade: LicenseTrade, *, include_reverse: bool = False) -> bool:
    """True only for an explicit paired/copied trade relation.

    The schema has no independent ``interlinked`` Boolean.  Existing explicit
    relation fields are the authoritative representation; an unpaired SALE is
    not labelled final by this helper.
    """
    return bool(
        trade.linked_trade_id
        or trade.counterpart_id
        or trade.copied_from_id
        or getattr(trade, "copied_from_type", "")
        or getattr(trade, "transaction_pair_uuid", None)
        or (include_reverse and (
            getattr(trade, "package_has_reverse_link", False)
            or getattr(trade, "package_has_reverse_counterpart", False)
            or getattr(trade, "package_has_reverse_copy", False)
        ))
    )


def _candidate(trade: LicenseTrade, *, selection_result: str, selection_reason: str, is_final_party: bool = False) -> dict[str, Any]:
    # ``prefetch_related`` leaves a RelatedManager on the model (rather than a
    # directly iterable list); `.all()` reads its prefetched cache here.
    interlinked = _is_interlinked(trade, include_reverse=trade.direction == LicenseTrade.DIR_SALE)
    sale_document = next(iter(trade.generated_invoice_documents.all()), None)
    return {
        "source_type": "trade.LicenseTrade",
        "source_id": trade.pk,
        "purchase_transaction_id": trade.pk if trade.direction == LicenseTrade.DIR_PURCHASE else None,
        "sales_invoice_id": trade.pk if trade.direction == LicenseTrade.DIR_SALE else None,
        # LicenseTrade is the canonical invoice model/header.  The generated
        # document is a versioned physical representation, not a replacement
        # invoice record.
        "invoice_model": "trade.LicenseTrade",
        "invoice_id": trade.pk,
        "invoice_number": trade.invoice_number or "",
        # Candidate decisions are persisted in the durable job manifest.  Do
        # not leave Django date objects for JSONField/JSON encoders to reject.
        "invoice_date": _json_date(trade.invoice_date),
        "direction": trade.direction,
        "document_id": getattr(sale_document, "pk", None),
        "is_main": trade.direction == LicenseTrade.DIR_PURCHASE and not interlinked,
        "is_interlinked": interlinked,
        "trade_id": trade.pk,
        "allotment_id": None,  # There is no FK from LicenseTrade to AllotmentModel.
        "buyer_party_id": trade.to_company_id,
        "buyer_party_name": getattr(trade.to_company, "name", "") if trade.to_company else "",
        "explicit_final_party_reference": (
            "trade.LicenseTrade.final_party"
            if getattr(trade, "final_party_status", None) == LicenseTrade.FINAL_PARTY_FINAL
            else None
        ),
        "classification_status": trade.final_party_status,
        "classification_provenance": getattr(trade, "final_party_classification_provenance", ""),
        "final_party_id": trade.final_party_id,
        "final_party_name": getattr(trade.final_party, "name", "") if trade.final_party else "",
        "is_final_party": is_final_party,
        "selection_result": selection_result,
        "selection_reason": selection_reason,
    }


def get_main_purchase_invoices(licence) -> list[dict[str, Any]]:
    """Return the first auditable main purchase for a licence.

    The package must contain the original acquisition document, not every
    later standalone purchase which happens to share a licence line. Paired
    and copied trades remain excluded. Of the remaining direct purchases,
    exactly the earliest (date, invoice number, primary key) is included;
    subsequent purchases are retained as explicit audit exclusions.
    """
    candidates, main_selected = [], False
    for trade in _trade_queryset(licence):
        if trade.direction != LicenseTrade.DIR_PURCHASE:
            continue
        interlinked = _is_interlinked(trade)
        included = not interlinked and not main_selected
        if included:
            main_selected = True
        candidates.append(_candidate(
            trade,
            selection_result="INCLUDED" if included else "EXCLUDED",
            selection_reason=("direct licence first acquisition" if included else
                              "explicit paired/copy relation" if interlinked else
                              "later direct purchase; original acquisition already selected"),
        ))
    return candidates


def get_final_party_sales_invoices(licence) -> list[dict[str, Any]]:
    """Return only explicitly classified terminal-party sale invoices.

    A direct line is evidence that a sale belongs to the licence, not evidence
    that its buyer is the terminal party.  Historical ``UNKNOWN`` rows must be
    resolved through the authorised classification workflow before a package
    can include their system-generated invoice.
    """
    candidates = []
    for trade in _trade_queryset(licence):
        if trade.direction != LicenseTrade.DIR_SALE:
            continue
        interlinked = _is_interlinked(trade, include_reverse=True)
        status = trade.final_party_status
        if interlinked:
            result, reason, is_final = "EXCLUDED", "explicit paired/copy relation", False
        elif (status == LicenseTrade.FINAL_PARTY_FINAL and trade.final_party_id
              and trade.final_party_id == trade.to_company_id):
            result, reason, is_final = "INCLUDED", "explicit final-party classification", True
        elif status == LicenseTrade.FINAL_PARTY_FINAL:
            # The system invoice belongs to ``to_company``.  A classification
            # pointing at another party cannot turn that invoice into a final
            # party invoice; retain it as an auditable invalid decision.
            result, reason, is_final = "EXCLUDED", "final-party classification does not match invoice buyer", False
        elif status == LicenseTrade.FINAL_PARTY_INTERMEDIATE:
            result, reason, is_final = "EXCLUDED", "explicit interlinked-party classification", False
        elif status == LicenseTrade.FINAL_PARTY_NOT_APPLICABLE:
            result, reason, is_final = "EXCLUDED", "audited no qualifying final-party sale", False
        else:
            result, reason, is_final = "EXCLUDED", "final-party classification required", False
        candidates.append(_candidate(
            trade, selection_result=result, selection_reason=reason, is_final_party=is_final,
        ))
    return candidates
