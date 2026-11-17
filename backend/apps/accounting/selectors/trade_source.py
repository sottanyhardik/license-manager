"""Read-only adapter over the existing Trade module (the operational source of truth).

The only place accounting reads trade data. Trade semantics (see trade_service._copy_to_counterpart):
``from_company`` is always the seller/supplier and ``to_company`` the buyer, on both legs of a pair.
So a SALE document belongs to the seller's books and a PURCHASE document to the buyer's books.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from apps.trade.models import LicenseTrade

OWN_SIDE = {  # direction -> (our side, invoice kind)
    "PURCHASE": ("to", "PURCHASE"),
    "SALE": ("from", "SALES"),
    "COMMISSION_PURCHASE": ("to", "COMMISSION_PAYABLE"),
    "COMMISSION_SALE": ("from", "COMMISSION_RECEIVABLE"),
}


@dataclass(frozen=True)
class TradeLineView:
    description: str
    amount: Decimal
    quantity: Decimal
    license_number: str


@dataclass(frozen=True)
class TradeView:
    id: int
    direction: str
    kind: str
    entity_company_id: int | None
    party_company_id: int | None
    invoice_number: str
    invoice_date: object
    subtotal: Decimal
    roundoff: Decimal
    total: Decimal
    lines: tuple[TradeLineView, ...]
    is_paired: bool

    @property
    def lines_total(self) -> Decimal:
        return sum((ln.amount for ln in self.lines), Decimal("0.00"))

    @property
    def version(self) -> str:
        """Hash of every field the accounting entry depends on; changes => re-post needed."""
        payload = {
            "d": self.direction, "e": self.entity_company_id, "p": self.party_company_id, "n": self.invoice_number,
            "dt": str(self.invoice_date), "s": str(self.subtotal), "r": str(self.roundoff), "t": str(self.total),
            "l": [[ln.description, str(ln.amount)] for ln in self.lines],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]


def trade_queryset():
    return LicenseTrade.objects.select_related("from_company", "to_company").prefetch_related(
        "lines__sr_number__license", "incentive_lines__incentive_license", "payments"
    )


def view_of(trade: LicenseTrade) -> TradeView:
    side, kind = OWN_SIDE[trade.direction]
    entity_id = trade.to_company_id if side == "to" else trade.from_company_id
    party_id = trade.from_company_id if side == "to" else trade.to_company_id
    if trade.license_type == LicenseTrade.LICENSE_TYPE_INCENTIVE:
        lines = tuple(
            TradeLineView(f"Incentive licence {getattr(il.incentive_license, 'license_number', il.incentive_license_id)}",
                          il.amount_inr, Decimal("0"), str(getattr(il.incentive_license, "license_number", "")))
            for il in trade.incentive_lines.all()
        )
    else:
        lines = tuple(
            TradeLineView(
                (ln.description or f"Licence item {ln.sr_number_id}")[:255], ln.amount_inr, ln.qty_kg or Decimal("0"),
                str(getattr(getattr(ln.sr_number, "license", None), "license_number", "") or ""),
            )
            for ln in trade.lines.all()
        )
    return TradeView(
        id=trade.pk, direction=trade.direction, kind=kind, entity_company_id=entity_id, party_company_id=party_id,
        invoice_number=trade.invoice_number or f"TRADE-{trade.pk}", invoice_date=trade.invoice_date,
        subtotal=trade.subtotal_amount, roundoff=trade.roundoff, total=trade.total_amount, lines=lines,
        is_paired=bool(trade.counterpart_id or trade.linked_trade_id),
    )


def get_trade(trade_id: int) -> LicenseTrade:
    return trade_queryset().get(pk=trade_id)


def trades_for_company(company_id: int):
    """Trades whose own side is ``company_id`` (i.e. documents of that entity's books)."""
    from django.db.models import Q
    return trade_queryset().filter(
        Q(direction__in=["PURCHASE", "COMMISSION_PURCHASE"], to_company_id=company_id)
        | Q(direction__in=["SALE", "COMMISSION_SALE"], from_company_id=company_id)
    )
