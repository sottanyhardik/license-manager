"""GST split and TDS arithmetic. Rates are always inputs (configuration), never constants."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .money import ZERO, q2


@dataclass(frozen=True)
class GstSplit:
    cgst: Decimal
    sgst: Decimal
    igst: Decimal

    @property
    def total(self) -> Decimal:
        return self.cgst + self.sgst + self.igst


def state_code_from_gstin(gstin: str | None) -> str:
    """First two digits of a GSTIN are the state code; '' when unknown."""
    gstin = (gstin or "").strip()
    return gstin[:2] if len(gstin) >= 2 and gstin[:2].isdigit() else ""


def split_gst(taxable: Decimal, rate_pct: Decimal, supplier_state: str, recipient_state: str) -> GstSplit:
    """Intra-state -> CGST+SGST (half each); inter-state or unknown state -> IGST."""
    if not rate_pct:
        return GstSplit(ZERO, ZERO, ZERO)
    tax = q2(taxable * rate_pct / Decimal("100"))
    if supplier_state and supplier_state == recipient_state:
        cgst = q2(tax / 2)
        return GstSplit(cgst, tax - cgst, ZERO)
    return GstSplit(ZERO, ZERO, tax)


def pan_category(pan: str | None) -> str:
    """4th PAN character: P individual, H HUF, C company, F firm/LLP, ... ; '' if no valid PAN."""
    pan = (pan or "").strip().upper()
    return pan[3] if len(pan) == 10 else ""


@dataclass(frozen=True)
class TdsRule:
    rate_individual: Decimal  # P / H
    rate_other: Decimal       # C, F, ... (companies, firms, LLPs)
    rate_no_pan: Decimal
    threshold_single: Decimal
    threshold_aggregate: Decimal
    threshold_mode: str       # "FULL" (whole amount once crossed) | "EXCESS" (only amount above threshold)


def tds_rate(rule: TdsRule, pan: str | None, lower_rate: Decimal | None = None) -> Decimal:
    if lower_rate is not None:
        return lower_rate
    category = pan_category(pan)
    if not category:
        return rule.rate_no_pan
    return rule.rate_individual if category in ("P", "H") else rule.rate_other


def tds_base(rule: TdsRule, amount: Decimal, prior_aggregate: Decimal) -> Decimal:
    """Portion of ``amount`` subject to TDS given the party's prior FY aggregate."""
    after = prior_aggregate + amount
    single_hit = rule.threshold_single > 0 and amount > rule.threshold_single
    aggregate_hit = rule.threshold_aggregate > 0 and after > rule.threshold_aggregate
    no_threshold = rule.threshold_single <= 0 and rule.threshold_aggregate <= 0
    if not (no_threshold or single_hit or aggregate_hit):
        return ZERO
    if rule.threshold_mode == "EXCESS" and aggregate_hit and not single_hit:
        return q2(after - max(rule.threshold_aggregate, prior_aggregate))
    return q2(amount)


def compute_tds(rule: TdsRule, amount: Decimal, prior_aggregate: Decimal, pan: str | None,
                lower_rate: Decimal | None = None) -> Decimal:
    base = tds_base(rule, amount, prior_aggregate)
    return q2(base * tds_rate(rule, pan, lower_rate) / Decimal("100")) if base else ZERO
