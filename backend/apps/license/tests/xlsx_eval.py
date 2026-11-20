"""Tiny evaluator for the formulas our exporters write (SUM ranges/lists and A1+B2 sums).

openpyxl cannot compute formulas and ``data_only`` reads ``None`` for files it wrote,
so exporter tests evaluate the formula text against the sheet's own cells.
"""
from __future__ import annotations

import re
from decimal import Decimal

_REF = re.compile(r"\$?([A-Z]{1,3})\$?(\d+)")


def _num(ws, ref: str) -> Decimal:
    value = ws[ref].value
    if isinstance(value, str) and value.startswith("="):
        return evaluate_formula(ws, value)
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return Decimal(0)
    return Decimal(str(value))


def evaluate_formula(ws, formula: str) -> Decimal:
    expr = formula[1:]

    def sum_repl(match):
        total = Decimal(0)
        for part in match.group(1).split(","):
            if ":" in part:
                first, last = part.split(":")
                for row in ws[first:last]:
                    for cell in row:
                        total += _num(ws, cell.coordinate)
            else:
                total += _num(ws, part)
        return format(total, "f")

    expr = re.sub(r"SUM\(([^)]*)\)", sum_repl, expr)
    expr = _REF.sub(lambda m: format(_num(ws, m.group(1) + m.group(2)), "f"), expr)
    return sum((Decimal(term) for term in expr.split("+")), Decimal(0))


def sum_range_of(formula: str):
    """('E', 4, 9) for ``=SUM(E4:E9)``; None when the formula is not a single range SUM."""
    match = re.fullmatch(r"=SUM\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)", formula)
    if not match or match.group(1) != match.group(3):
        return None
    return match.group(1), int(match.group(2)), int(match.group(4))
