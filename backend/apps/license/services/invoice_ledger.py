"""Licence purchase/sale invoice ledger (Invoices & Sales tab).

Built from the same licence-item trade lines the canonical balance uses. Every amount is a
line-level value from the stored record: CIF in the licence currency (`cif_fc`) and the bill
value in INR (`amount_inr`). Nothing is converted with a guessed rate.

Classification of each line:
- PURCHASE / SALE from the trade direction.
- CREDIT NOTE / DEBIT NOTE from the invoice text prefix.
  A note is netted only when it matches exactly one original trade line: same referenced invoice
  number, same licence item, same quantity and same CIF. Anything else is shown as
  UNMATCHED and contributes nothing until a person confirms the link.

Each row contributes exactly once to one bucket:
- PURCHASE rows → gross purchase.
- SALE rows → gross sale.
- Matched notes → an adjustment to the bucket of their original (CREDIT reduces, DEBIT increases).
- Unmatched notes → no contribution (flagged).

Net purchase − net sale is the holder's current CIF balance, reconciled against the canonical
sale figure (which does not yet net matched credit notes; the difference is reported).
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

ZERO = Decimal("0")
CREDIT_NOTE = "CREDIT NOTE"
DEBIT_NOTE = "DEBIT NOTE"
_NOTE_RE = re.compile(r"^\s*(CREDIT NOTE|DEBIT NOTE)\s+(.+?)\s*$", re.IGNORECASE)


def classify_invoice(invoice_number: str, direction: str):
    """Return (type, referenced_invoice). Type is PURCHASE, SALE, CREDIT NOTE or DEBIT NOTE."""
    match = _NOTE_RE.match(invoice_number or "")
    if match:
        return match.group(1).upper(), match.group(2)
    return direction, None


def _s(value) -> Optional[str]:
    return None if value is None else format(Decimal(value).quantize(Decimal("0.01")), "f")


@dataclass
class LedgerRow:
    line_id: int
    trade_id: int
    date: Optional[str]
    particulars: str
    invoice: str
    type: str
    items: str
    holder_company: str
    cif_fc: Decimal
    bill_inr: Decimal
    cif_inr: Decimal
    original_side: str  # PURCHASE or SALE: which side this row belongs to (for notes, the side it adjusts)
    matched_original: Optional[dict] = None
    status: str = "OK"
    sign: int = 1  # +1 adds to the side's total, -1 reduces it (credit notes)
    source: dict = field(default_factory=dict)
    related_boes: list = field(default_factory=list)
    classification: str = "EXTERNAL"  # INTERNAL rows are listed but never counted as external
    classification_reason: str = ""

    def contribution_cif(self) -> Decimal:
        if self.type in (CREDIT_NOTE, DEBIT_NOTE) and self.matched_original is None:
            return ZERO
        return self.cif_fc * self.sign

    def contribution_bill(self) -> Decimal:
        if self.type in (CREDIT_NOTE, DEBIT_NOTE) and self.matched_original is None:
            return ZERO
        return self.bill_inr * self.sign

    def payload(self):
        return {
            "line_id": self.line_id,
            "trade_id": self.trade_id,
            "date": self.date,
            "particulars": self.particulars,
            "invoice": self.invoice,
            "type": self.type,
            "items": self.items,
            "holder_company": self.holder_company,
            # Notes show signed amounts: a credit note is a negative entry in its side's column.
            "sale_cif": _s(self.cif_fc * self.sign) if self.original_side == "SALE" else None,
            "purchase_cif": _s(self.cif_fc * self.sign) if self.original_side == "PURCHASE" else None,
            "sale_bill_inr": _s(self.bill_inr * self.sign) if self.original_side == "SALE" else None,
            "purchase_bill_inr": _s(self.bill_inr * self.sign) if self.original_side == "PURCHASE" else None,
            "cif_inr": _s(self.cif_inr),
            "exchange_rate": (format((self.cif_inr / self.cif_fc).quantize(Decimal("0.0001")), "f")
                              if self.cif_fc else None),
            "effect": self._effect(),
            "matched_original": self.matched_original,
            "status": self.status,
            "counts_in_summary": self.status == "OK" or self.type in ("PURCHASE", "SALE"),
            "related_boes": self.related_boes,
            "source": self.source,
            "classification": self.classification,
            "classification_reason": self.classification_reason,
        }

    def _effect(self) -> str:
        if self.type == "PURCHASE":
            return "Adds to purchase"
        if self.type == "SALE":
            return "Adds to sale"
        if self.matched_original is None:
            return "Not netted (review)"
        if self.type == CREDIT_NOTE:
            return f"Reduces {self.original_side.lower()} (credit note)"
        return f"Increases {self.original_side.lower()} (debit note)"


def build_invoice_ledger(rows: list[LedgerRow], canonical_sale_cif: Optional[Decimal] = None):
    """Summarise rows. `rows` must already carry their match result. Pure: no database access.

    INTERNAL rows are listed in every company section, but they are left out of every total,
    balance and canonical comparison. Their figures are reported on their own.
    """
    internal_rows = [r for r in rows if r.classification == "INTERNAL"]
    rows = [r for r in rows if r.classification != "INTERNAL"]
    gross_internal_sale = sum((r.cif_fc for r in internal_rows if r.type == "SALE"), ZERO)
    gross_internal_purchase = sum((r.cif_fc for r in internal_rows if r.type == "PURCHASE"), ZERO)
    internal_sale_bill = sum((r.bill_inr for r in internal_rows if r.type == "SALE"), ZERO)
    internal_purchase_bill = sum((r.bill_inr for r in internal_rows if r.type == "PURCHASE"), ZERO)

    gross_purchase = sum((r.cif_fc for r in rows if r.type == "PURCHASE"), ZERO)
    gross_sale = sum((r.cif_fc for r in rows if r.type == "SALE"), ZERO)
    purchase_bill = sum((r.bill_inr for r in rows if r.type == "PURCHASE"), ZERO)
    sale_bill = sum((r.bill_inr for r in rows if r.type == "SALE"), ZERO)

    purchase_adj = sum((r.contribution_cif() for r in rows
                        if r.type in (CREDIT_NOTE, DEBIT_NOTE) and r.original_side == "PURCHASE"), ZERO)
    sale_adj = sum((r.contribution_cif() for r in rows
                    if r.type in (CREDIT_NOTE, DEBIT_NOTE) and r.original_side == "SALE"), ZERO)
    purchase_bill_adj = sum((r.contribution_bill() for r in rows
                             if r.type in (CREDIT_NOTE, DEBIT_NOTE) and r.original_side == "PURCHASE"), ZERO)
    sale_bill_adj = sum((r.contribution_bill() for r in rows
                         if r.type in (CREDIT_NOTE, DEBIT_NOTE) and r.original_side == "SALE"), ZERO)

    net_purchase = gross_purchase + purchase_adj
    net_sale = gross_sale + sale_adj
    net_purchase_bill = purchase_bill + purchase_bill_adj
    net_sale_bill = sale_bill + sale_bill_adj

    unmatched = [r for r in rows if r.type in (CREDIT_NOTE, DEBIT_NOTE) and r.matched_original is None]

    summary = {
        "currency": "USD",
        "gross_purchase_cif": _s(gross_purchase),
        "gross_sale_cif": _s(gross_sale),
        "purchase_adjustments_cif": _s(purchase_adj),
        "sale_adjustments_cif": _s(sale_adj),
        "net_purchase_cif": _s(net_purchase),
        "net_sale_cif": _s(net_sale),
        "current_balance_cif": _s(net_purchase - net_sale),
        "purchase_bill_inr_gross": _s(purchase_bill),
        "sale_bill_inr_gross": _s(sale_bill),
        "purchase_bill_inr_adjustments": _s(purchase_bill_adj),
        "sale_bill_inr_adjustments": _s(sale_bill_adj),
        "net_purchase_bill_inr": _s(net_purchase_bill),
        "net_sale_bill_inr": _s(net_sale_bill),
        "net_bill_difference_inr": _s(net_purchase_bill - net_sale_bill),
        "gross_internal_sale_cif": _s(gross_internal_sale),
        "gross_internal_purchase_cif": _s(gross_internal_purchase),
        "gross_sale_all_cif": _s(gross_sale + gross_internal_sale),
        "internal_sale_bill_inr": _s(internal_sale_bill),
        "internal_purchase_bill_inr": _s(internal_purchase_bill),
        "internal_row_count": len(internal_rows),
        "unmatched_notes": len(unmatched),
        "unmatched_note_cif": _s(sum((r.cif_fc for r in unmatched), ZERO)),
    }
    if canonical_sale_cif is not None:
        summary["canonical_sale_cif"] = _s(canonical_sale_cif)
        summary["canonical_vs_net_sale_difference"] = _s(canonical_sale_cif - net_sale)
        summary["canonical_gross_check"] = "MATCHES GROSS SALE" if canonical_sale_cif == gross_sale else "DIFFERS FROM GROSS SALE"

    groups = defaultdict(list)
    for r in sorted(rows + internal_rows, key=lambda r: (r.date or "", r.trade_id, r.line_id)):
        groups[r.holder_company].append(r)
    company_sections = []
    for company, company_rows in sorted(groups.items()):
        external_rows = [r for r in company_rows if r.classification != "INTERNAL"]
        net_p = sum((r.cif_fc for r in external_rows if r.type == "PURCHASE"), ZERO) + sum(
            (r.contribution_cif() for r in external_rows if r.type in (CREDIT_NOTE, DEBIT_NOTE) and r.original_side == "PURCHASE"), ZERO)
        net_s = sum((r.cif_fc for r in external_rows if r.type == "SALE"), ZERO) + sum(
            (r.contribution_cif() for r in external_rows if r.type in (CREDIT_NOTE, DEBIT_NOTE) and r.original_side == "SALE"), ZERO)
        company_internal = sum((r.cif_fc for r in company_rows if r.classification == "INTERNAL"), ZERO)
        company_sections.append({
            "company": company,
            "balance_cif": _s(net_p - net_s),
            "internal_cif": _s(company_internal),
            "rows": [r.payload() for r in company_rows],
        })
    return {"summary": summary, "companies": company_sections}


# ---------------------------------------------------------------------------
# Database loader
# ---------------------------------------------------------------------------

def load_invoice_ledger(license_id: int):
    """Read the licence's trade lines and match credit and debit notes. Read-only."""
    from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
    from apps.license.services.licence_balance_report import build_licence_balance_reports
    from apps.trade.models import LicenseTradeLine

    item_ids = list(LicenseImportItemsModel.objects.filter(license_id=license_id).values_list("id", flat=True))
    currency = (LicenseExportItemModel.objects.filter(license_id=license_id)
                .exclude(currency="").values_list("currency", flat=True).first()) or "usd"
    from apps.trade.models import LicenseTrade

    lines = list(
        LicenseTradeLine.objects.filter(sr_number_id__in=item_ids)
        .select_related("trade__from_company", "trade__to_company", "sr_number")
        .order_by("trade__invoice_date", "trade_id", "id")
    )
    trade_ids = {line.trade_id for line in lines}
    from apps.trade.models import TradeUtilisationClassification

    classifications = {
        c.trade_id: c
        for c in TradeUtilisationClassification.objects.filter(trade_id__in=trade_ids).select_related("authorised_by")
    }
    boes_by_trade = defaultdict(list)
    for trade_id, number in LicenseTrade.boes.through.objects.filter(licensetrade_id__in=trade_ids).values_list(
        "licensetrade_id", "billofentrymodel__bill_of_entry_number"
    ):
        boes_by_trade[trade_id].append(number)

    rows = []
    for line in lines:
        trade = line.trade
        note_type, referenced = classify_invoice(trade.invoice_number, trade.direction)
        holder = trade.to_company if trade.direction == "PURCHASE" else trade.from_company
        other = trade.from_company if trade.direction == "PURCHASE" else trade.to_company
        row = LedgerRow(
            line_id=line.id,
            trade_id=trade.id,
            date=trade.invoice_date.isoformat() if trade.invoice_date else None,
            particulars=other.name if other else "",
            invoice=trade.invoice_number,
            type=note_type,
            items=line.description or (line.sr_number.description if line.sr_number_id else "") or "",
            holder_company=holder.name if holder else "",
            cif_fc=Decimal(line.cif_fc or 0),
            bill_inr=Decimal(line.amount_inr or 0),
            cif_inr=Decimal(line.cif_inr or 0),
            original_side=trade.direction,
            source={"type": "trade", "id": trade.id, "line_id": line.id, "currency": currency.upper()},
            related_boes=sorted(boes_by_trade.get(trade.id, [])),
        )
        record = classifications.get(trade.id)
        if record is not None and record.classification == TradeUtilisationClassification.CLASS_INTERNAL:
            row.classification = "INTERNAL"
            row.classification_reason = record.reason
        if note_type in (CREDIT_NOTE, DEBIT_NOTE):
            row.sign = -1 if note_type == CREDIT_NOTE else 1
            candidates = list(
                LicenseTradeLine.objects.filter(
                    trade__invoice_number=referenced,
                    sr_number_id=line.sr_number_id,
                    cif_fc=line.cif_fc,
                    qty_kg=line.qty_kg,
                ).exclude(trade_id=trade.id).select_related("trade")
            )
            if len(candidates) == 1:
                original = candidates[0]
                row.original_side = original.trade.direction
                row.matched_original = {
                    "trade_id": original.trade_id,
                    "line_id": original.id,
                    "invoice": original.trade.invoice_number,
                    "side": original.trade.direction,
                }
                row.status = "MATCHED TO ORIGINAL"
            elif not candidates:
                row.status = "UNMATCHED NOTE: no original line found (not netted)"
            else:
                row.status = "UNMATCHED NOTE: ambiguous original (not netted)"
        rows.append(row)

    canonical = build_licence_balance_reports([license_id], include_legacy=False).get(license_id)
    canonical_sale = None
    if canonical is not None and canonical.summary_cif.get("invoiced") is not None:
        canonical_sale = Decimal(canonical.summary_cif["invoiced"])
    return build_invoice_ledger(rows, canonical_sale_cif=canonical_sale)
