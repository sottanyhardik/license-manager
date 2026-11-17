"""on_delete handlers that keep Trade deletable until it has ledger effect.

Django evaluates on_delete while collecting (before any signal), so the guard must live here:
draft/cancelled accounting links are cascaded away; anything posted/reversed blocks the delete.
"""
from django.db.models import CASCADE, ProtectedError

UNPOSTED = ("DRAFT", "CANCELLED")


def _status(obj) -> str:
    return getattr(obj, "status", None) or getattr(getattr(obj, "invoice", None), "status", "")


def protect_if_posted(collector, field, sub_objs, using):
    posted = [o for o in sub_objs if _status(o) not in UNPOSTED]
    if posted:
        raise ProtectedError(
            "This trade has posted accounting entries; reverse them in Accounting before deleting the trade.",
            posted,
        )
    CASCADE(collector, field, sub_objs, using)
