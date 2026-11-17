"""Discover legal entities from Trade (the exclusive entity source). Nothing is hardcoded."""
from __future__ import annotations

from collections import Counter

from apps.accounting.models import EntityBooks
from apps.core.models import CompanyModel
from apps.trade.models import LicenseTrade


def discover_entities() -> list[dict]:
    """Companies that are the *own side* of trade documents (buyer on purchases, seller on sales),
    ranked by document count, with whether their books are active.

    A counterparty can also appear here if it is the own side of a copied leg (see AD-03); the
    accountant activates books only for the group's own legal entities.
    """
    counts: Counter = Counter()
    for direction, field in (("PURCHASE", "to_company_id"), ("COMMISSION_PURCHASE", "to_company_id"),
                             ("SALE", "from_company_id"), ("COMMISSION_SALE", "from_company_id")):
        for company_id in (LicenseTrade.objects.filter(direction=direction).exclude(**{field: None})
                           .values_list(field, flat=True)):
            counts[company_id] += 1
    books = {b.pk: b for b in EntityBooks.objects.all()}
    ids = set(counts) | set(books)
    companies = {c.pk: c for c in CompanyModel.objects.filter(pk__in=ids)}
    rows = []
    for cid in ids:
        c = companies.get(cid)
        if not c:
            continue
        b = books.get(cid)
        rows.append({"company_id": cid, "name": c.name, "gstin": c.gst_number, "pan": c.pan,
                     "own_side_documents": counts.get(cid, 0), "has_books": b is not None,
                     "books_active": bool(b and b.is_active),
                     "books_start_date": b.books_start_date if b else None})
    return sorted(rows, key=lambda r: (not r["has_books"], -r["own_side_documents"], r["name"]))
