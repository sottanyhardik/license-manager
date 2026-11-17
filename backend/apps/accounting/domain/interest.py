"""Loan interest arithmetic (actual/365 day count by default)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .money import q2

DAYS_IN_YEAR = Decimal("365")


@dataclass(frozen=True)
class BalanceSegment:
    """Outstanding principal (and unpaid interest, for compounding) constant over [start, end]."""
    start: date
    end: date          # inclusive
    principal: Decimal
    unpaid_interest: Decimal = Decimal("0")


def simple_interest(principal: Decimal, annual_rate_pct: Decimal, days: int,
                    day_count: Decimal = DAYS_IN_YEAR) -> Decimal:
    if days <= 0 or principal <= 0 or annual_rate_pct <= 0:
        return Decimal("0.00")
    return q2(principal * annual_rate_pct / Decimal("100") * Decimal(days) / day_count)


def accrue(segments: list[BalanceSegment], annual_rate_pct: Decimal, compound: bool) -> Decimal:
    """Interest over consecutive segments. Compound = interest also charged on unpaid accrued interest."""
    total = Decimal("0.00")
    for seg in segments:
        days = (seg.end - seg.start).days + 1
        base = seg.principal + (seg.unpaid_interest if compound else Decimal("0"))
        total += simple_interest(base, annual_rate_pct, days)
    return q2(total)


def month_end(d: date) -> date:
    nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return nxt - timedelta(days=1)


def emi_amount(principal: Decimal, annual_rate_pct: Decimal, months: int) -> Decimal:
    """Standard reducing-balance EMI."""
    if months <= 0:
        raise ValueError("months must be positive")
    r = annual_rate_pct / Decimal("1200")
    if r == 0:
        return q2(principal / months)
    factor = (1 + r) ** months
    return q2(principal * r * factor / (factor - 1))
