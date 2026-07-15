# trade/services/trade_service.py
"""
Domain service layer for the Trade app.

All functions here accept plain Python arguments (model instances, dicts,
primitives) and return plain Python values or model instances.  No HTTP
Request objects, no DRF Response objects.  Domain errors are raised as
ValueError (or subclasses) so the view layer can map them to HTTP status codes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from apps.trade.models import LicenseTrade

# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date_strict(date_str: str | None) -> date | None:
    """
    Parse a date string in strict ISO format (YYYY-MM-DD) only.

    Args:
        date_str: Date string to parse, or None/empty.

    Returns:
        ``date`` object on success, ``None`` when *date_str* is falsy.

    Raises:
        ValueError: If the string is present but not in YYYY-MM-DD format.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"Invalid date format. Expected YYYY-MM-DD, got: {date_str}"
        ) from exc


# ---------------------------------------------------------------------------
# Invoice number pre-fill
# ---------------------------------------------------------------------------

_VALID_DIRECTIONS = frozenset(
    ["PURCHASE", "SALE", "COMMISSION_PURCHASE", "COMMISSION_SALE"]
)


def get_prefilled_invoice_number(
    direction: str,
    company_id: int,
    invoice_date: date | None = None,
) -> str:
    """
    Compute the next invoice number for a given direction / company / date.

    Args:
        direction:    Trade direction -- one of PURCHASE, SALE, COMMISSION_PURCHASE,
                      COMMISSION_SALE.
        company_id:   PK of the CompanyModel record.
        invoice_date: Optional date that determines the Indian financial year.
                      Defaults to today when omitted.

    Returns:
        Next invoice number string (e.g. ``"LM/2025-26/0024"``).

    Raises:
        ValueError:         When *direction* is not recognised.
        CompanyModel.DoesNotExist: When *company_id* does not match any company.
    """
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(
            f"direction must be one of {sorted(_VALID_DIRECTIONS)}, got: {direction!r}"
        )

    from apps.core.models import CompanyModel
    from apps.trade.models import get_next_invoice_number

    company = CompanyModel.objects.get(pk=company_id)
    return get_next_invoice_number(
        direction=direction,
        company_name=company.name,
        invoice_date=invoice_date,
    )


# ---------------------------------------------------------------------------
# Trade summary
# ---------------------------------------------------------------------------

def build_trade_summary(trade) -> dict:
    """
    Return a plain dict of computed summary fields for a LicenseTrade instance.

    Args:
        trade: A :class:`~apps.trade.models.LicenseTrade` instance.

    Returns:
        Dict with keys: id, direction, invoice_number, invoice_date,
        subtotal_amount, roundoff, total_amount, paid_or_received, due_amount,
        lines_count, payments_count.
    """
    return {
        "id": trade.id,
        "direction": trade.direction,
        "invoice_number": trade.invoice_number,
        "invoice_date": trade.invoice_date,
        "subtotal_amount": str(trade.subtotal_amount),
        "roundoff": str(trade.roundoff),
        "total_amount": str(trade.total_amount),
        "paid_or_received": str(trade.paid_or_received),
        "due_amount": str(trade.due_amount),
        "lines_count": trade.lines.count(),
        "payments_count": trade.payments.count(),
    }


# ---------------------------------------------------------------------------
# Bidirectional trade linking
# ---------------------------------------------------------------------------

class PartnerTradeNotFound(LookupError):
    """Raised when the partner trade PK cannot be resolved."""


@transaction.atomic
def link_trades(trade_pk: int, partner_pk: int | None) -> LicenseTrade:
    """
    Bidirectionally link or unlink two LicenseTrade records.

    Linking rules:
    - *partner_pk* == None  -> clear the link on *trade* and its current partner.
    - *partner_pk* == *trade_pk* -> raises ValueError (cannot link to itself).
    - Otherwise -> any stale links on either side are cleared, then both trades
      are linked to each other.

    Args:
        trade_pk:   PK of the primary trade.
        partner_pk: PK of the trade to link to, or ``None`` to unlink.

    Returns:
        The refreshed primary LicenseTrade instance.

    Raises:
        LicenseTrade.DoesNotExist: When *trade_pk* does not match any trade.
        ValueError: When *partner_pk* == *trade_pk*.
        PartnerTradeNotFound: When *partner_pk* is given but does not exist.
    """
    from apps.trade.models import LicenseTrade

    trade = LicenseTrade.objects.get(pk=trade_pk)

    # ---- Unlink ----
    if partner_pk is None:
        old_partner_id = trade.linked_trade_id
        LicenseTrade.objects.filter(pk=trade.pk).update(linked_trade=None)
        if old_partner_id:
            LicenseTrade.objects.filter(
                pk=old_partner_id, linked_trade=trade.pk
            ).update(linked_trade=None)
        trade.refresh_from_db()
        return trade

    # ---- Self-link guard ----
    if partner_pk == trade_pk:
        raise ValueError("Cannot link a trade to itself")

    # ---- Fetch partner ----
    try:
        partner = LicenseTrade.objects.get(pk=partner_pk)
    except LicenseTrade.DoesNotExist:
        raise PartnerTradeNotFound(f"Partner trade {partner_pk} not found")

    # ---- Clear stale links ----
    old_trade_partner = trade.linked_trade_id
    old_partner_partner = partner.linked_trade_id
    if old_trade_partner and old_trade_partner != partner.pk:
        LicenseTrade.objects.filter(pk=old_trade_partner).update(linked_trade=None)
    if old_partner_partner and old_partner_partner != trade.pk:
        LicenseTrade.objects.filter(pk=old_partner_partner).update(linked_trade=None)

    # ---- Set new link ----
    LicenseTrade.objects.filter(pk=trade.pk).update(linked_trade=partner)
    LicenseTrade.objects.filter(pk=partner.pk).update(linked_trade=trade)

    trade.refresh_from_db()
    return trade
