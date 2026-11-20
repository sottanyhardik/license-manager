"""
SAT-DEF-150 / owner decision C-2 (2026-11-20): "Auto-link exact matches, review
the rest."

An unlinked allotment whose matching BOE is already debited is double counted
(allotment reservation + BOE debit). An EXACT match creates the existing
`BillOfEntryModel.allotment` M2M link (the Balance Engine already treats it as
full consumption), audited via `ReconciliationLog`. Every other candidate goes
to `review_candidates` and stays outstanding. Sibling-item matches (DEC-60)
are never auto-linked.

Exact (G3): the allotment's items ALL still reserve CIF (`contributed > 0`),
the BOE is not genuinely hidden / not linked to any allotment / same company,
and its DEBIT rows on the allotment's licence(s) map one-to-one onto the
allotment's items (same import item, qty equal at 0.001, cif_fc equal at
0.01). Unique both ways, otherwise AMBIGUOUS -> review.

Read-only use of `LicenseBalanceCalculator`; this module never edits balance
math. `ReconciliationLog` is append-only.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef

from django.apps import apps as django_apps
from apps.bill_of_entry.models import (
    BillOfEntryModel,
    RowDetails,
    genuinely_hidden_boe_ids,
)
from apps.core.constants import DEBIT
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.reconciliation.models import BOEAllotmentAllocation, ReconciliationLog

Q3 = Decimal("0.001")
Q2 = Decimal("0.01")
ZERO = Decimal("0")

REASON_QTY_DIFF = "QTY_DIFF"
REASON_CIF_DIFF = "CIF_DIFF"
REASON_PARTIAL_ITEMS = "PARTIAL_ITEMS"
REASON_AMBIGUOUS = "AMBIGUOUS"
REASON_SIBLING_ITEM = "SIBLING_ITEM"

LOG_REASON = "SAT-DEF-150 / C-2 exact match"


def _q3(v) -> Decimal:
    return Decimal(v or 0).quantize(Q3)


def _q2(v) -> Decimal:
    return Decimal(v or 0).quantize(Q2)


def _key(sr_id, qty, cif):
    return (sr_id, _q3(qty), _q2(cif))


def _load(license_ids):
    """Return (allotments, boes) for the licences.

    allotments: {allotment_id: {"company_id", "license_ids", "items": [(item_pk, sr_id, qty, cif)]}}
        only allotments where EVERY item reserves CIF.
    boes: {boe_id: {"company_id", "number", "rows": {license_id: [(sr_id, qty, cif)]}}}
        only visible, unlinked BOEs with DEBIT rows on the licences.
    """
    license_ids = list(license_ids)
    rows = list(
        LicenseBalanceCalculator.get_allotment_rows_bulk(license_ids).select_related("allotment", "item")
    )
    reserving = defaultdict(list)
    for r in rows:
        reserving[r.allotment_id].append(r)
    # An allotment is only a candidate if ALL its items (any licence) reserve.
    all_items = defaultdict(list)
    for ai in django_apps.get_model("allotment", "AllotmentItems").objects.filter(allotment_id__in=list(reserving)).select_related("item"):
        all_items[ai.allotment_id].append(ai)
    allotments = {}
    for aid, rs in reserving.items():
        if len(all_items[aid]) != len(rs) or any((r.contributed or 0) <= 0 for r in rs):
            continue
        allotments[aid] = {
            "company_id": rs[0].allotment.company_id,
            "license_ids": {r.item.license_id for r in rs},
            "items": [(r.pk, r.item_id, r.qty, r.cif_fc) for r in rs],
        }

    boe_rows = (
        RowDetails.objects.filter(
            sr_number__license_id__in=license_ids,
            transaction_type=DEBIT,
            bill_of_entry__isnull=False,
            bill_of_entry__allotment__isnull=True,
        )
        # Audit F1: a BOE whose DEBIT row already carries an ACTIVE formal
        # allocation is consumed by that allotment; never auto-link a second
        # (duplicate) allotment to it.
        .exclude(
            Exists(
                BOEAllotmentAllocation.objects.filter(
                    row_details__bill_of_entry_id=OuterRef("bill_of_entry_id"),
                    status=BOEAllotmentAllocation.STATUS_ACTIVE,
                    is_current=True,
                )
            )
        )
        .select_related("bill_of_entry", "sr_number")
    )
    hidden = genuinely_hidden_boe_ids({r.bill_of_entry_id for r in boe_rows})
    boes = {}
    for r in boe_rows:
        if r.bill_of_entry_id in hidden:
            continue
        b = boes.setdefault(
            r.bill_of_entry_id,
            {
                "company_id": r.bill_of_entry.company_id,
                "number": r.bill_of_entry.bill_of_entry_number,
                "rows": defaultdict(list),
            },
        )
        b["rows"][r.sr_number.license_id].append((r.sr_number_id, r.qty, r.cif_fc))
    return allotments, boes


def _classify(allot, boe):
    """Return (reason or None for exact, qty_delta, cif_delta) or None if not a candidate."""
    if allot["company_id"] != boe["company_id"]:
        return None
    lic_ids = [lid for lid in allot["license_ids"] if lid in boe["rows"]]
    if not lic_ids:
        return None
    b_rows = [r for lid in lic_ids for r in boe["rows"][lid]]
    a_items = [(sr, q, c) for _pk, sr, q, c in allot["items"]]
    a_keys = sorted(_key(*i) for i in a_items)
    b_keys = sorted(_key(*r) for r in b_rows)
    qty_delta = sum((_q3(r[1]) for r in b_rows), ZERO) - sum((_q3(i[1]) for i in a_items), ZERO)
    cif_delta = sum((_q2(r[2]) for r in b_rows), ZERO) - sum((_q2(i[2]) for i in a_items), ZERO)
    if a_keys == b_keys and len({k[0] for k in a_keys}) == len(a_keys):
        return None, qty_delta, cif_delta  # exact
    a_sr = {i[0] for i in a_items}
    b_sr = {r[0] for r in b_rows}
    if a_sr & b_sr:
        if a_sr == b_sr and len(a_items) == len(b_rows) == len(a_sr):
            a_map = {i[0]: (_q3(i[1]), _q2(i[2])) for i in a_items}
            b_map = {r[0]: (_q3(r[1]), _q2(r[2])) for r in b_rows}
            if any(a_map[s][0] != b_map[s][0] for s in a_sr):
                return REASON_QTY_DIFF, qty_delta, cif_delta
            return REASON_CIF_DIFF, qty_delta, cif_delta
        return REASON_PARTIAL_ITEMS, qty_delta, cif_delta
    if qty_delta == 0 and a_items:
        return REASON_SIBLING_ITEM, qty_delta, cif_delta
    return None


def _analyse(license_ids):
    allotments, boes = _load(license_ids)
    exact = []   # (allotment_id, boe_id, qty_delta, cif_delta)
    review = []  # dict rows (without ambiguity applied)
    for aid, a in allotments.items():
        for bid, b in boes.items():
            res = _classify(a, b)
            if res is None:
                continue
            reason, qd, cd = res
            if reason is None:
                exact.append((aid, bid))
            else:
                review.append((aid, bid, reason, qd, cd))
    per_a = defaultdict(list)
    per_b = defaultdict(list)
    for aid, bid in exact:
        per_a[aid].append(bid)
        per_b[bid].append(aid)
    clean, ambiguous = [], []
    for aid, bid in exact:
        (clean if len(per_a[aid]) == 1 and len(per_b[bid]) == 1 else ambiguous).append((aid, bid))
    for aid, bid in ambiguous:
        review.append((aid, bid, REASON_AMBIGUOUS, ZERO, ZERO))
    return allotments, boes, clean, review


def _license_of(allot, boe):
    return sorted(lid for lid in allot["license_ids"] if lid in boe["rows"])


def review_candidates(license_ids) -> list[dict]:
    """Read-only review list of non-exact candidates (never linked automatically)."""
    allotments, boes, _clean, review = _analyse(license_ids)
    out = []
    for aid, bid, reason, qd, cd in review:
        a, b = allotments[aid], boes[bid]
        out.append(
            {
                "license_ids": _license_of(a, b),
                "allotment_id": aid,
                "allotment_item_ids": [i[0] for i in a["items"]],
                "boe_id": bid,
                "boe_number": b["number"],
                "reason": reason,
                "qty_delta": qd,
                "cif_delta": cd,
            }
        )
    out.sort(key=lambda r: (r["allotment_id"], r["boe_id"], r["reason"]))
    return out


def _all_license_ids():
    return list(
        django_apps.get_model("allotment", "AllotmentItems").objects.values_list("item__license_id", flat=True).distinct()
    )


def apply_exact_links(license_ids=None, *, user=None, dry_run=True, boe_id=None) -> dict:
    """Auto-link unique EXACT allotment<->BOE matches. Dry run by default.

    `boe_id` restricts linking to one BOE (used by the post-save trigger).
    Returns {"batch_id", "dry_run", "exact": [...], "review": [...], "linked": [...]}.
    """
    ids = list(license_ids) if license_ids is not None else _all_license_ids()
    allotments, boes, clean, review = _analyse(ids)
    if boe_id is not None:
        clean = [p for p in clean if p[1] == boe_id]
    exact = [
        {
            "license_ids": _license_of(allotments[aid], boes[bid]),
            "allotment_id": aid,
            "allotment_item_ids": [i[0] for i in allotments[aid]["items"]],
            "boe_id": bid,
            "boe_number": boes[bid]["number"],
        }
        for aid, bid in clean
    ]
    result = {
        "batch_id": str(uuid.uuid4()),
        "dry_run": dry_run,
        "exact": exact,
        "review": [
            {"allotment_id": a, "boe_id": b, "reason": r, "qty_delta": q, "cif_delta": c}
            for a, b, r, q, c in review
            if boe_id is None or b == boe_id
        ],
        "linked": [],
    }
    if dry_run:
        return result
    for aid, bid in clean:
        link = _link_one(aid, bid, result["batch_id"], ids, user)
        if link:
            result["linked"].append(link)
    return result


def _link_one(allotment_id, boe_id, batch_id, license_ids, user):
    with transaction.atomic():
        boe = BillOfEntryModel.objects.select_for_update().filter(pk=boe_id).first()
        allotment = django_apps.get_model("allotment", "AllotmentModel").objects.select_for_update().filter(pk=allotment_id).first()
        if boe is None or allotment is None:
            return None
        if boe.allotment.exists():
            return None
        # Re-check exactness on fresh, locked state.
        allotments, boes, clean, _ = _analyse(license_ids)
        if (allotment_id, boe_id) not in clean:
            return None
        prev = allotment.is_boe
        items = [
            {"item_id": pk, "sr_id": sr, "qty": str(_q3(q)), "cif_fc": str(_q2(c))}
            for pk, sr, q, c in allotments[allotment_id]["items"]
        ]
        boe.allotment.add(allotment)
        if not allotment.is_boe:
            allotment.is_boe = True
            allotment.save()
        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_AUTO_LINK_ALLOTMENT,
            bill_of_entry=boe,
            before={"is_boe": prev},
            after={
                "batch_id": batch_id,
                "allotment_id": allotment_id,
                "match": "EXACT",
                "items": items,
            },
            reason=LOG_REASON,
            user=user,
        )
        return {"allotment_id": allotment_id, "boe_id": boe_id, "previous_is_boe": prev}


def reverse_batch(batch_id, *, user=None) -> dict:
    """Undo links created by `batch_id` that are still present. Idempotent."""
    reversed_links = []
    logs = ReconciliationLog.objects.filter(
        action=ReconciliationLog.ACTION_AUTO_LINK_ALLOTMENT, after__batch_id=batch_id
    ).order_by("id")
    for log in logs:
        aid = log.after["allotment_id"]
        with transaction.atomic():
            boe = BillOfEntryModel.objects.select_for_update().filter(pk=log.bill_of_entry_id).first()
            allotment = django_apps.get_model("allotment", "AllotmentModel").objects.select_for_update().filter(pk=aid).first()
            if boe is None or allotment is None:
                continue
            already = ReconciliationLog.objects.filter(
                action=ReconciliationLog.ACTION_REVERSE_AUTO_LINK_ALLOTMENT,
                bill_of_entry=boe,
                after__batch_id=batch_id,
                after__allotment_id=aid,
            ).exists()
            if already or not boe.allotment.filter(pk=aid).exists():
                continue
            boe.allotment.remove(allotment)
            prev = (log.before or {}).get("is_boe", False)
            restored = allotment.is_boe
            if not prev and not allotment.bill_of_entry.exists() and allotment.is_boe:
                allotment.is_boe = False
                allotment.save()
                restored = False
            ReconciliationLog.objects.create(
                action=ReconciliationLog.ACTION_REVERSE_AUTO_LINK_ALLOTMENT,
                bill_of_entry=boe,
                before={"is_boe": True},
                after={"batch_id": batch_id, "allotment_id": aid, "is_boe": restored},
                reason=f"Reverse SAT-DEF-150 / C-2 auto-link batch {batch_id}",
                user=user,
            )
            reversed_links.append({"allotment_id": aid, "boe_id": boe.pk})
    return {"batch_id": batch_id, "reversed": reversed_links}
