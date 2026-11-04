"""Internal transfers between our own group companies, and the evidence that a sale and its purchase are one transfer.

Two rules live here and nowhere else:

1. Group membership is by registered company ID, taken from the company master. A company is never treated as
   internal because its name resembles a group company, and a customer is never internal by name.
2. A sale is matched to its counterpart purchase only from persisted records: the same invoice number, the same
   seller and buyer, the same invoice date and identical lines, or a persisted COPIED pair (TradePairAudit).
   Equal amounts or names alone never match.

Matching is evidence only. The classification that changes licence utilisation is the explicit
`TradeUtilisationClassification` record, which an authorised user writes. Nothing here writes a record.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Registered group companies, by company master ID (CompanyModel.id). Confirmed by name in the master:
#   881  LABDHI GLOBAL LLP            (AAMFL9142N)
#   766  LABDHI MERCANTILE LLP        (AAMFL0999F)
#   866  NEELKANTH IMPEX              (AAWFN4258P)
#   1037 Sambhav Corporation          (AADHA3706J)
#   885  VISION GURUKRUPA BUILDCON LLP (AAZFV9505C)
# Not included: SAMBHAV PAPERS (223), SAMBHAV PAPERS LLP (564), VISION (273), VISION VANIJYA PRIVATE LIMITED (198).
GROUP_COMPANY_IDS = frozenset({881, 766, 866, 1037, 885})

# Classification labels shown to users. Derived from the persisted record, the trade direction and the matching
# evidence. They never change arithmetic by themselves.
EXTERNAL_SALE = "EXTERNAL_SALE"
EXTERNAL_PURCHASE = "EXTERNAL_PURCHASE"
INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
INTERNAL_TRANSFER_PURCHASE = "INTERNAL_TRANSFER_PURCHASE"
UNMATCHED_INTERNAL_TRANSACTION = "UNMATCHED_INTERNAL_TRANSACTION"
REVIEW_REQUIRED = "REVIEW_REQUIRED"


def is_group_company(company_id) -> bool:
    return company_id is not None and int(company_id) in GROUP_COMPANY_IDS


def is_group_transfer(trade) -> bool:
    """A transaction whose seller and buyer are both registered group companies."""
    return is_group_company(trade.from_company_id) and is_group_company(trade.to_company_id)


@dataclass(frozen=True)
class CounterpartMatch:
    """The other side of the same transfer (a purchase for a sale, a sale for a purchase), and the evidence used."""

    counterpart_trade_id: int
    counterpart_invoice_number: str
    basis: str  # "COPIED_PAIR" or "SAME_INVOICE_AND_LINES"


def _line_signature(trade) -> tuple:
    return tuple(sorted(
        (line.sr_number_id, Decimal(line.cif_fc or 0), Decimal(line.qty_kg or 0))
        for line in trade.lines.all()
    ))


def match_counterpart_purchase(sale) -> CounterpartMatch | None:
    """The purchase that records this group sale as the buyer's purchase, from persisted records only.

    Returns None when no purchase can be established. Does not write anything.
    """
    from apps.trade.models import LicenseTrade, TradePairAudit

    copied = (
        TradePairAudit.objects.filter(source_id=sale.pk, action="COPIED", counterpart__direction="PURCHASE")
        .select_related("counterpart")
        .first()
    )
    if copied is not None:
        return CounterpartMatch(copied.counterpart_id, copied.counterpart.invoice_number, "COPIED_PAIR")

    candidates = LicenseTrade.objects.filter(
        direction="PURCHASE",
        invoice_number=sale.invoice_number,
        from_company_id=sale.from_company_id,
        to_company_id=sale.to_company_id,
        invoice_date=sale.invoice_date,
    ).exclude(pk=sale.pk)
    sale_lines = _line_signature(sale)
    for purchase in candidates:
        if _line_signature(purchase) == sale_lines:
            return CounterpartMatch(purchase.pk, purchase.invoice_number, "SAME_INVOICE_AND_LINES")
    return None


def match_counterpart_sale(purchase) -> CounterpartMatch | None:
    """The sale that records this purchase as the seller's sale. The reverse of match_counterpart_purchase.

    Same evidence rules: a persisted COPIED pair, or the same invoice, parties, date and identical lines.
    """
    from apps.trade.models import LicenseTrade, TradePairAudit

    copied = (
        TradePairAudit.objects.filter(counterpart_id=purchase.pk, action="COPIED", source__direction="SALE")
        .select_related("source")
        .first()
    )
    if copied is not None:
        return CounterpartMatch(copied.source_id, copied.source.invoice_number, "COPIED_PAIR")

    candidates = LicenseTrade.objects.filter(
        direction="SALE",
        invoice_number=purchase.invoice_number,
        from_company_id=purchase.from_company_id,
        to_company_id=purchase.to_company_id,
        invoice_date=purchase.invoice_date,
    ).exclude(pk=purchase.pk)
    purchase_lines = _line_signature(purchase)
    for sale in candidates:
        if _line_signature(sale) == purchase_lines:
            return CounterpartMatch(sale.pk, sale.invoice_number, "SAME_INVOICE_AND_LINES")
    return None


def transaction_class(trade, classification: str | None) -> tuple[str, CounterpartMatch | None]:
    """The one classification label for a trade, with its counterpart when it is an internal transfer.

    `classification` is the persisted TradeUtilisationClassification value, or None when there is no record.
    """
    from apps.trade.models import TradeUtilisationClassification

    if classification == TradeUtilisationClassification.CLASS_REVIEW:
        return REVIEW_REQUIRED, None
    if classification == TradeUtilisationClassification.CLASS_INTERNAL:
        if trade.direction == "SALE":
            return INTERNAL_TRANSFER, match_counterpart_purchase(trade)
        return INTERNAL_TRANSFER_PURCHASE, match_counterpart_sale(trade)
    if trade.direction == "PURCHASE":
        return EXTERNAL_PURCHASE, None
    if is_group_transfer(trade) and match_counterpart_purchase(trade) is None:
        return UNMATCHED_INTERNAL_TRANSACTION, None
    return EXTERNAL_SALE, None
