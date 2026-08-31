"""Deterministic, auditable final-party classification from the canonical graph."""
from __future__ import annotations

from django.db import transaction

from apps.trade.models import LicenseTrade


INTERLINK_PROVENANCE = "CANONICAL_TRANSACTION_GRAPH_INTERLINK"
TERMINAL_PROVENANCE = "CANONICAL_TRANSACTION_GRAPH_TERMINAL"


def is_interlinked(trade: LicenseTrade) -> bool:
    return bool(trade.linked_trade_id or trade.counterpart_id or trade.copied_from_id
                or trade.copied_from_type or trade.transaction_pair_uuid)


@transaction.atomic
def backfill_final_party_classifications(queryset=None) -> dict[str, int]:
    """Classify only graph facts; never use date, value, party name, or type.

    A missing graph edge is not positive proof of a terminal sale.  This
    backfill therefore classifies only explicit interlink edges; all other
    historical sales remain UNKNOWN for an authorised workflow resolution.
    """
    sales = (queryset if queryset is not None else LicenseTrade.objects.all()).filter(direction=LicenseTrade.DIR_SALE)
    changed = {"FINAL_PARTY": 0, "INTERLINKED": 0, "UNKNOWN": 0}
    for trade in sales.select_related("to_company").prefetch_related("lines", "copies_created"):
        # A human-authorised resolution is durable business evidence.  The
        # graph backfill must never erase it merely because historical graph
        # data has no edge proving the relationship.
        if trade.final_party_status == LicenseTrade.FINAL_PARTY_FINAL and trade.final_party_classification_provenance.startswith(("AUTHORISED_", "EXPLICIT_MANUAL_")):
            continue
        if is_interlinked(trade):
            status, party, provenance = LicenseTrade.FINAL_PARTY_INTERMEDIATE, None, INTERLINK_PROVENANCE
        else:
            status, party, provenance = LicenseTrade.FINAL_PARTY_UNKNOWN, None, ""
        if (trade.final_party_status, trade.final_party_id, trade.final_party_classification_provenance) != (status, getattr(party, "pk", None), provenance):
            trade.final_party_status = status
            trade.final_party = party
            trade.final_party_classification_provenance = provenance
            trade.final_party_resolution_note = (
                "Deterministic canonical transaction-graph backfill. " + provenance if provenance else ""
            )
            trade.save(update_fields=["final_party_status", "final_party", "final_party_classification_provenance", "final_party_resolution_note"])
            changed[status] += 1
    return changed
