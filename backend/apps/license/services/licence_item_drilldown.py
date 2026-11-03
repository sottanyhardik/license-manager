"""Item drill-down: the BOE debits, customer allotments and invoices behind one SION item's balance.

Every row comes from the loader and per-item classification that `licence_balance_report` uses,
so a row here contributes exactly what the item table shows. Each group has totals, and
`reconciliation` compares those totals with the item's canonical figures. A difference is
reported as MISMATCH. It is never corrected here.

Previous-owner BOEs (identified by the BOE hide/restore audit trail) are debit rows like any
other. They carry `previous_owner: true` and their debit is also reported as a separate
sub-total, so the Debited figure can be explained by current-owner and previous-owner parts.

Links are shown only where a record exists:
- BOE to invoice: trade to BOE membership. Amounts come from `InvoiceBOEAllocation` when an
  active allocation exists for the pair, otherwise from the full BOE amount.
- BOE to allotment: allotment to BOE membership.
- Allotment to invoice: no such record exists, so the figure is reported as not recorded.

Read-only. Money is returned as strings; quantities are withheld when the unit is not verified.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from apps.license.services.invoice_ledger import CREDIT_NOTE, DEBIT_NOTE, classify_invoice
from apps.license.services.licence_balance_report import (
    CROSS_ITEM_STATUS,
    MISMATCH,
    OVER_LINKED_BOE_STATUS,
    ZERO,
    _index,
    _internal_sales_by_trade,
    _item_inputs,
    _item_report,
    _load,
    _money,
    _qty,
    _s,
    debit_row_status,
    excess_owner,
    over_linked_excess,
)
from apps.license.services.licence_item_balance import RECONCILED, UNIT_UNVERIFIED

CIF_QUANTUM = Decimal("0.01")
QTY_QUANTUM = Decimal("0.001")
NOT_COMPUTED = "NOT COMPUTED"

# Row kind for an over-linked excess row (no BOE). The label for the same row is in `status`.
EXCESS_KIND = "OVER_LINKED_EXCESS"
OVER_LINKED_EXCESS = "OVER-LINKED EXCESS (counted as debit)"
OVER_LINKED_EXCESS_PREVIOUS = "OVER-LINKED EXCESS — PREVIOUS OWNER (counted as debit)"
OVER_LINKED_INVOICE = "OVER-LINKED: excess counted as utilisation"
NOTE_NOT_NETTED = "NOTE NOT NETTED: counted as a sale in the item balance (see invoice ledger)"
LINKED_BOE_WITHOUT_DEBIT = "LINKED BOE WITHOUT A DEBIT ON THIS ITEM (review)"
RELEASE_RECORDED = "RELEASE RECORDED: not deducted by the balance (review)"
SALE_OVERLAP = "SAME ITEM HAS A SALE: overlap unverified (decision O-4)"


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def _fmt(value, measure):
    if value is None:
        return None
    return _qty(value) if measure == "qty" else _money(value)


def _trade_totals(links):
    totals = defaultdict(lambda: {"cif": ZERO, "qty": ZERO})
    for _lid, _rd, trade_id, c, q in links:
        totals[trade_id]["cif"] += c
        totals[trade_id]["qty"] += q
    return totals


def _basis(data, sales_by_trade, rd, trade_id):
    line_id = sales_by_trade[trade_id]["lines"][0].id
    return "ALLOCATION" if (rd.id, line_id) in data["allocations"] else "FULL BOE"


def _boe_refs(ids):
    """BOE number and date for BOEs that may not debit this item. One query."""
    from apps.bill_of_entry.models import BillOfEntryModel

    refs = {}
    for boe_id, number, boe_date in BillOfEntryModel.objects.filter(pk__in=ids).values_list(
        "id", "bill_of_entry_number", "bill_of_entry_date"
    ):
        refs[boe_id] = {"boe_number": _s(number), "boe_date": _iso(boe_date)}
    return refs


def _boe_fields(rd):
    boe = rd.bill_of_entry
    if boe is None:
        return {"boe_number": "", "boe_date": None, "port": "", "importer": ""}
    return {
        "boe_number": _s(boe.bill_of_entry_number),
        "boe_date": _iso(boe.bill_of_entry_date),
        "port": boe.port.name if boe.port_id else "",
        "importer": boe.company.name if boe.company_id else "",
    }


def _boe_section(item, data, sales_by_trade, debit_rows, links, cross, allot_ids, withheld, currency):
    excess = over_linked_excess(sales_by_trade, links)
    over_linked_trades = {tid for tid, (ex_c, _ex_q, _rows) in excess.items() if ex_c > ZERO}

    links_by_row = defaultdict(list)
    for _lid, rd, trade_id, c, q in links:
        links_by_row[rd.id].append((trade_id, c, q))
    cross_ids = {rd.id for rd, _t in cross}
    previous_owner_ids = data["previous_owner_ids"]
    hs_code = item.hs_code.hs_code if item.hs_code_id else None
    sr = _s(item.serial_number)

    rows = []
    for rd in debit_rows:
        previous_owner = rd.id in previous_owner_ids
        cif = Decimal(rd.cif_fc or 0)
        qty = Decimal(rd.qty or 0)
        row_links = links_by_row.get(rd.id, [])
        cov_c = sum((c for _t, c, _q in row_links), ZERO)
        cov_q = sum((q for _t, _c, q in row_links), ZERO)
        unc_c = max(ZERO, cif - cov_c)
        unc_q = max(ZERO, qty - cov_q)
        flags = []
        if cov_c > cif:
            flags.append("BOE_OVER_COVERED: linked sales exceed this BOE; the excess is not debited here")
        status = debit_row_status(
            previous_owner=previous_owner,
            cross=rd.id in cross_ids,
            over_linked=any(t in over_linked_trades for t, _c, _q in row_links),
            covered=cov_c,
            uncovered=unc_c,
        )
        rows.append({
            "kind": "BOE",
            "row_id": rd.id,
            **_boe_fields(rd),
            "sr": sr,
            "hs_code": hs_code,
            "currency": currency,
            "invoice_number": None,
            "boe_cif": _money(cif),
            "boe_qty": None if withheld else _qty(qty),
            "cif_inr": _money(rd.cif_inr),
            "covered_cif": _money(cov_c),
            "covered_qty": None if withheld else _qty(cov_q),
            "debited_cif": _money(unc_c),
            "debited_qty": None if withheld else _qty(unc_q),
            "previous_owner": previous_owner,
            "sale_links": [
                {
                    "trade_id": trade_id,
                    "invoice_number": sales_by_trade[trade_id]["invoice"],
                    "cif": _money(c),
                    "qty": None if withheld else _qty(q),
                    "basis": _basis(data, sales_by_trade, rd, trade_id),
                }
                for trade_id, c, q in row_links
            ],
            "allotment_ids": [aid for aid in allot_ids if rd.bill_of_entry_id in data["allotment_boes"].get(aid, set())],
            "status": status,
            "flags": flags,
            "source": {"type": "bill_of_entry", "id": rd.bill_of_entry_id},
            "_raw": {"cif": cif, "covered_cif": cov_c, "debited_cif": unc_c, "previous_owner": previous_owner,
                     "qty": qty, "covered_qty": cov_q, "debited_qty": unc_q, "excess": False},
        })

    for tid, (ex_c, ex_q, row_ids) in excess.items():
        owner = excess_owner(row_ids, previous_owner_ids)
        previous_owner = owner == "previous"
        flags = ["OVER_LINKED_MIXED_OWNERSHIP: excess ownership not determined (review)"] if owner == "mixed" else []
        rows.append({
            "kind": EXCESS_KIND,
            "row_id": None,
            "boe_number": "",
            "boe_date": None,
            "port": "",
            "importer": "",
            "sr": sr,
            "hs_code": hs_code,
            "currency": currency,
            "invoice_number": sales_by_trade[tid]["invoice"],
            "boe_cif": None,
            "boe_qty": None,
            "cif_inr": None,
            "covered_cif": None,
            "covered_qty": None,
            "debited_cif": _money(ex_c),
            "debited_qty": None if withheld else _qty(ex_q),
            "previous_owner": previous_owner,
            "sale_links": [],
            "allotment_ids": [],
            "status": OVER_LINKED_EXCESS_PREVIOUS if previous_owner else OVER_LINKED_EXCESS,
            "flags": flags,
            "source": {"type": "trade", "id": tid},
            "_raw": {"cif": ZERO, "covered_cif": ZERO, "debited_cif": ex_c, "previous_owner": previous_owner,
                     "qty": ZERO, "covered_qty": ZERO, "debited_qty": ex_q, "excess": True},
        })

    rows.sort(key=lambda r: (r["kind"] == EXCESS_KIND, r["boe_date"] or "", r["row_id"] or 0, r["invoice_number"] or ""))
    raw = _boe_raw_totals(rows)
    totals = {
        "boe_rows": sum(1 for r in rows if r["kind"] == "BOE"),
        "previous_owner_rows": sum(1 for r in rows if r["kind"] == "BOE" and r["_raw"]["previous_owner"]),
        "boe_cif": _money(raw["boe_cif"]),
        "covered_cif": _money(raw["covered_cif"]),
        "uncovered_cif": _money(raw["uncovered_cif"]),
        "previous_owner_debit_cif": _money(raw["previous_owner_debit_cif"]),
        "over_linked_cif": _money(raw["over_linked_cif"]),
        "debited_cif": _money(raw["debited_cif"]),
        "boe_qty": None if withheld else _qty(raw["boe_qty"]),
        "covered_qty": None if withheld else _qty(raw["covered_qty"]),
        "uncovered_qty": None if withheld else _qty(raw["uncovered_qty"]),
        "previous_owner_debit_qty": None if withheld else _qty(raw["previous_owner_debit_qty"]),
        "over_linked_qty": None if withheld else _qty(raw["over_linked_qty"]),
        "debited_qty": None if withheld else _qty(raw["debited_qty"]),
    }
    for row in rows:
        row.pop("_raw")
    return {"totals": totals, "rows": rows, "_raw": raw}


def _boe_raw_totals(rows):
    """Totals from the unrounded row amounts. `uncovered` is current-owner only; previous-owner is its own line."""
    bo = [r["_raw"] for r in rows if r["kind"] == "BOE"]
    current = [x for x in bo if not x["previous_owner"]]
    previous = [x for x in bo if x["previous_owner"]]
    excess = [r["_raw"] for r in rows if r["kind"] == EXCESS_KIND]
    excess_previous = [x for x in excess if x["previous_owner"]]
    excess_current = [x for x in excess if not x["previous_owner"]]

    def add(items, key):
        return sum((x[key] for x in items), ZERO)

    unc_c = add(current, "debited_cif")
    unc_q = add(current, "debited_qty")
    po_c = add(previous, "debited_cif") + add(excess_previous, "debited_cif")
    po_q = add(previous, "debited_qty") + add(excess_previous, "debited_qty")
    over_c = add(excess_current, "debited_cif")
    over_q = add(excess_current, "debited_qty")
    return {
        "boe_cif": add(bo, "cif"),
        "boe_qty": add(bo, "qty"),
        "covered_cif": add(bo, "covered_cif"),
        "covered_qty": add(bo, "covered_qty"),
        "uncovered_cif": unc_c,
        "uncovered_qty": unc_q,
        "previous_owner_debit_cif": po_c,
        "previous_owner_debit_qty": po_q,
        "over_linked_cif": over_c,
        "over_linked_qty": over_q,
        "debited_cif": unc_c + po_c + over_c,
        "debited_qty": unc_q + po_q + over_q,
    }


def _classification_fields(data, trade_id):
    """The audited treatment for one trade, for display. Absent records read as EXTERNAL."""
    record = data.get("trade_classifications", {}).get(trade_id)
    if record is None:
        return {"classification": "EXTERNAL", "classification_reason": "", "classification_authorised_by": None,
                "classification_authorised_on": None}
    return {
        "classification": record.classification,
        "classification_reason": record.reason,
        "classification_authorised_by": record.authorised_by.get_username() if record.authorised_by_id else None,
        "classification_authorised_on": _iso(record.authorised_on),
    }


def _internal_invoice_row(item, data, trade_id, t, currency, withheld):
    """An INTERNAL sale shown for audit. Every amount is listed, and none of them is utilisation."""
    sr = _s(item.serial_number)
    sold_c, sold_q = t["cif"], t["qty"]
    doc_type, referenced = classify_invoice(t["invoice"], "SALE")
    return {
        "kind": "INVOICE",
        "trade_id": trade_id,
        "invoice_number": t["invoice"],
        "document_type": doc_type,
        "referenced_invoice": referenced,
        "invoice_date": _iso(t["date"]),
        "customer": t["customer"],
        "sr": sr,
        "currency": currency,
        "sold_cif": _money(sold_c),
        "sold_qty": None if withheld else _qty(sold_q),
        "sold_cif_inr": _money(t["inr"]),
        "covered_by_boe_cif": _money(ZERO),
        "covered_by_boe_qty": None if withheld else _qty(ZERO),
        "uncovered_cif": _money(ZERO),
        "uncovered_qty": None if withheld else _qty(ZERO),
        "over_linked_cif": _money(ZERO),
        "over_linked_qty": None if withheld else _qty(ZERO),
        "current_balance_cif": _money(ZERO),
        "counts_in_current_balance": False,
        "linked_boes": [],
        "boes_without_debit_on_item": [],
        "status": "INTERNAL TRADE: not external utilisation",
        "flags": [],
        "source": {"type": "trade", "id": trade_id},
        **{**_classification_fields(data, trade_id), "classification": "INTERNAL"},
    }


def _invoice_section(item, data, sales_by_trade, debit_rows, links, withheld, currency, boe_refs, internal_by_trade=None):
    trade_linked = _trade_totals(links)
    on_item = {rd.bill_of_entry_id for rd in debit_rows}
    sr = _s(item.serial_number)
    rows = []
    for trade_id, t in sales_by_trade.items():
        sold_c, sold_q = t["cif"], t["qty"]
        lk_c, lk_q = trade_linked[trade_id]["cif"], trade_linked[trade_id]["qty"]
        cov_c = min(sold_c, lk_c)
        cov_q = min(sold_q, lk_q)
        unc_c = sold_c - cov_c
        unc_q = sold_q - cov_q
        over_c = max(ZERO, lk_c - sold_c)
        over_q = max(ZERO, lk_q - sold_q)
        if over_c > ZERO:
            status = OVER_LINKED_INVOICE
        elif lk_c == ZERO:
            status = "NOT LINKED"
        elif lk_c == sold_c:
            status = "COVERED BY BOE"
        else:
            status = "PARTIALLY COVERED BY BOE"

        doc_type, referenced = classify_invoice(t["invoice"], "SALE")
        flags = []
        if doc_type in (CREDIT_NOTE, DEBIT_NOTE):
            flags.append(NOTE_NOT_NETTED)
        other_boe_ids = sorted(data["trade_boe_members"].get(trade_id, set()) - on_item)
        if other_boe_ids:
            flags.append(LINKED_BOE_WITHOUT_DEBIT)

        linked = []
        for _lid, rd, tid, c, q in links:
            if tid != trade_id:
                continue
            linked.append({
                "row_id": rd.id,
                **_boe_fields(rd),
                "previous_owner": rd.id in data["previous_owner_ids"],
                "cif": _money(c),
                "qty": None if withheld else _qty(q),
                "basis": _basis(data, sales_by_trade, rd, trade_id),
            })
        linked.sort(key=lambda b: (b["boe_date"] or "", b["row_id"]))

        rows.append({
            "kind": "INVOICE",
            "trade_id": trade_id,
            "invoice_number": t["invoice"],
            "document_type": doc_type,
            "referenced_invoice": referenced,
            "invoice_date": _iso(t["date"]),
            "customer": t["customer"],
            "sr": sr,
            "currency": currency,
            "sold_cif": _money(sold_c),
            "sold_qty": None if withheld else _qty(sold_q),
            "sold_cif_inr": _money(t["inr"]),
            "covered_by_boe_cif": _money(cov_c),
            "covered_by_boe_qty": None if withheld else _qty(cov_q),
            "uncovered_cif": _money(unc_c),
            "uncovered_qty": None if withheld else _qty(unc_q),
            "over_linked_cif": _money(over_c),
            "over_linked_qty": None if withheld else _qty(over_q),
            "current_balance_cif": _money(sold_c),
            "counts_in_current_balance": True,
            **_classification_fields(data, trade_id),
            "linked_boes": linked,
            "boes_without_debit_on_item": [
                {"boe_id": bid, **boe_refs.get(bid, {"boe_number": "", "boe_date": None})} for bid in other_boe_ids
            ],
            "status": status,
            "flags": flags,
            "source": {"type": "trade", "id": trade_id},
            "_raw": {"sold_cif": sold_c, "sold_qty": sold_q, "covered_cif": cov_c, "covered_qty": cov_q,
                     "uncovered_cif": unc_c, "uncovered_qty": unc_q, "over_cif": over_c, "over_qty": over_q},
        })

    rows.sort(key=lambda r: (r["invoice_date"] or "", r["trade_id"]))
    raw_sold_c = sum((r["_raw"]["sold_cif"] for r in rows), ZERO)
    raw_sold_q = sum((r["_raw"]["sold_qty"] for r in rows), ZERO)
    raw = {
        "sold_cif": raw_sold_c,
        "sold_qty": raw_sold_q,
        "covered_cif": sum((r["_raw"]["covered_cif"] for r in rows), ZERO),
        "covered_qty": sum((r["_raw"]["covered_qty"] for r in rows), ZERO),
        "uncovered_cif": sum((r["_raw"]["uncovered_cif"] for r in rows), ZERO),
        "uncovered_qty": sum((r["_raw"]["uncovered_qty"] for r in rows), ZERO),
        "over_cif": sum((r["_raw"]["over_cif"] for r in rows), ZERO),
        "over_qty": sum((r["_raw"]["over_qty"] for r in rows), ZERO),
    }
    totals = {
        "invoice_rows": len(rows),
        "sold_cif": _money(raw_sold_c),
        "covered_by_boe_cif": _money(raw["covered_cif"]),
        "uncovered_cif": _money(raw["uncovered_cif"]),
        "over_linked_cif": _money(raw["over_cif"]),
        "current_balance_cif": _money(raw_sold_c),
        "sold_qty": None if withheld else _qty(raw_sold_q),
        "covered_by_boe_qty": None if withheld else _qty(raw["covered_qty"]),
        "uncovered_qty": None if withheld else _qty(raw["uncovered_qty"]),
        "over_linked_qty": None if withheld else _qty(raw["over_qty"]),
    }
    # INTERNAL sales are listed beside the external rows. Totals above stay external-only, so the
    # utilisation figures are unchanged. Gross internal figures are reported separately.
    internal_rows = [_internal_invoice_row(item, data, tid, t, currency, withheld)
                     for tid, t in (internal_by_trade or {}).items()]
    internal_c = sum((Decimal(str(r["sold_cif"])) for r in internal_rows), ZERO)
    internal_q = sum((Decimal(str(r["sold_qty"] or 0)) for r in internal_rows), ZERO)
    totals.update({
        "internal_invoice_rows": len(internal_rows),
        "internal_sold_cif": _money(internal_c),
        "internal_sold_qty": None if withheld else _qty(internal_q),
        "gross_sold_cif": _money(raw_sold_c + internal_c),
    })
    rows = sorted(rows + internal_rows, key=lambda r: (r["invoice_date"] or "", r["trade_id"]))
    for row in rows:
        row.pop("_raw", None)
    return {"totals": totals, "rows": rows, "_raw": raw}


def _allotment_section(item, data, debit_rows, allot_residue, has_sales, withheld, boe_refs):
    from apps.allotment.models import AllotmentItems

    residue = {ai_id: (c, q, elsewhere) for _a, ai_id, c, q, elsewhere in allot_residue}
    previous_owner_ids = data["previous_owner_ids"]
    sr = _s(item.serial_number)
    rows = []
    for ai in data["allot_by_item"].get(item.id, []):
        bids = sorted(data["allotment_boes"].get(ai.allotment_id, set()))
        a_c = Decimal(ai.cif_fc or 0)
        a_q = Decimal(ai.qty or 0)
        out_c, out_q, elsewhere = residue[ai.id]
        boe_c = a_c - out_c
        boe_q = a_q - out_q
        if elsewhere:
            status = "REVIEW REQUIRED"
        elif not bids:
            status = "UNLINKED"
        elif out_c == ZERO:
            status = "LINKED"
        elif boe_c > ZERO:
            status = "PARTIALLY LINKED"
        else:
            status = "UNLINKED"
        flags = []
        if has_sales and out_c > ZERO:
            flags.append(SALE_OVERLAP)
        if ai.released_quantity and Decimal(ai.released_quantity) > ZERO:
            flags.append(RELEASE_RECORDED)
        if elsewhere:
            flags.append("A linked BOE does not debit this item")

        linked_boes = []
        for bid in bids:
            on_item = [rd for rd in debit_rows if rd.bill_of_entry_id == bid]
            linked_boes.append({
                "boe_id": bid,
                **boe_refs.get(bid, {"boe_number": "", "boe_date": None}),
                "on_this_item": bool(on_item),
                "previous_owner": any(rd.id in previous_owner_ids for rd in on_item),
                "debit_on_item_cif": _money(sum((Decimal(rd.cif_fc or 0) for rd in on_item), ZERO)),
                "debit_on_item_qty": None if withheld else _qty(sum((Decimal(rd.qty or 0) for rd in on_item), ZERO)),
                "row_ids": [rd.id for rd in on_item],
            })

        rows.append({
            "kind": "ALLOTMENT",
            "allotment_id": ai.allotment_id,
            "allotment_item_id": ai.id,
            "reference": f"ALLOT-{ai.allotment_id}",
            "allotment_date": _iso(ai.allotment.created_on.date()) if ai.allotment.created_on else None,
            "customer": ai.allotment.company.name if ai.allotment.company_id else "",
            "sr": sr,
            "original_cif": _money(a_c),
            "original_qty": None if withheld else _qty(a_q),
            "boe_linked_cif": _money(boe_c),
            "boe_linked_qty": None if withheld else _qty(boe_q),
            "invoice_linked_cif": None,
            "invoice_linked_qty": None,
            "outstanding_cif": _money(out_c),
            "outstanding_qty": None if withheld else _qty(out_q),
            "status": status,
            "source_status": ai.status,
            "linked_boes": linked_boes,
            "flags": flags,
            "source": {"type": "allotment_item", "id": ai.id},
            "_raw": {"original_cif": a_c, "boe_linked_cif": boe_c, "outstanding_cif": out_c,
                     "original_qty": a_q, "boe_linked_qty": boe_q, "outstanding_qty": out_q, "cancelled": False},
        })

    for ai in AllotmentItems.objects.filter(item_id=item.id).exclude(status="CREATED").select_related("allotment__company").order_by("id"):
        # RELEASED is the cancelled reservation. COMPLETED and REACTIVATED are not counted by the balance.
        flags = [f"Source status {ai.status}: not counted by the balance"]
        if ai.status == "REACTIVATED":
            flags.append("REACTIVATED: not counted by the balance (review)")
        rows.append({
            "kind": "ALLOTMENT",
            "allotment_id": ai.allotment_id,
            "allotment_item_id": ai.id,
            "reference": f"ALLOT-{ai.allotment_id}",
            "allotment_date": _iso(ai.allotment.created_on.date()) if ai.allotment.created_on else None,
            "customer": ai.allotment.company.name if ai.allotment.company_id else "",
            "sr": sr,
            "original_cif": _money(ai.cif_fc),
            "original_qty": None if withheld else _qty(ai.qty),
            "boe_linked_cif": None,
            "boe_linked_qty": None,
            "invoice_linked_cif": None,
            "invoice_linked_qty": None,
            "outstanding_cif": _money(ZERO),
            "outstanding_qty": None if withheld else _qty(ZERO),
            "status": "CANCELLED" if ai.status == "RELEASED" else f"EXCLUDED ({ai.status})",
            "source_status": ai.status,
            "linked_boes": [],
            "flags": flags,
            "source": {"type": "allotment_item", "id": ai.id},
            "_raw": {"original_cif": Decimal(ai.cif_fc or 0), "boe_linked_cif": ZERO, "outstanding_cif": ZERO,
                     "original_qty": Decimal(ai.qty or 0), "boe_linked_qty": ZERO, "outstanding_qty": ZERO,
                     "cancelled": True},
        })

    live = [r["_raw"] for r in rows if not r["_raw"]["cancelled"]]
    cancelled = [r["_raw"] for r in rows if r["_raw"]["cancelled"]]
    raw = {
        "outstanding_cif": sum((x["outstanding_cif"] for x in live), ZERO),
        "outstanding_qty": sum((x["outstanding_qty"] for x in live), ZERO),
    }
    totals = {
        "allotment_rows": len(live),
        "cancelled_rows": len(cancelled),
        "original_cif": _money(sum((x["original_cif"] for x in live), ZERO)),
        "boe_linked_cif": _money(sum((x["boe_linked_cif"] for x in live), ZERO)),
        "invoice_linked_cif": None,
        "outstanding_cif": _money(raw["outstanding_cif"]),
        "cancelled_cif_excluded": _money(sum((x["original_cif"] for x in cancelled), ZERO)),
        "original_qty": None if withheld else _qty(sum((x["original_qty"] for x in live), ZERO)),
        "boe_linked_qty": None if withheld else _qty(sum((x["boe_linked_qty"] for x in live), ZERO)),
        "outstanding_qty": None if withheld else _qty(raw["outstanding_qty"]),
    }
    for row in rows:
        row.pop("_raw")
    return {"totals": totals, "rows": rows, "_raw": raw}


def _check(field, drill, table, measure):
    """Compare a drill-down total with the item table at the figure's own precision (half-up)."""
    quantum = QTY_QUANTUM if measure == "qty" else CIF_QUANTUM
    drill_q = drill.quantize(quantum, rounding=ROUND_HALF_UP)
    if table is None:
        return {"field": field, "drill": _fmt(drill_q, measure), "item_table": None, "difference": None, "status": NOT_COMPUTED}
    table_q = table.quantize(quantum, rounding=ROUND_HALF_UP)
    diff = drill_q - table_q
    return {
        "field": field,
        "drill": _fmt(drill_q, measure),
        "item_table": _fmt(table_q, measure),
        "difference": _fmt(diff, measure),
        "status": RECONCILED if diff == ZERO else MISMATCH,
    }


def _reconciliation(item, report, boe_raw, inv_raw, allot_raw, withheld):
    cif = report.cif.get("_obj")
    original = Decimal(item.cif_fc or 0)
    debited = boe_raw["debited_cif"]
    allotted = allot_raw["outstanding_cif"]
    invoiced = inv_raw["sold_cif"]
    cif_checks = [
        _check("debited", debited, getattr(cif, "debited", None), "cif"),
        _check("allotted", allotted, getattr(cif, "allotted", None), "cif"),
        _check("invoiced", invoiced, getattr(cif, "invoiced", None), "cif"),
        _check("available", original - debited - allotted - invoiced, getattr(cif, "available", None), "cif"),
    ]
    if withheld:
        qty_checks = [{"field": f, "status": UNIT_UNVERIFIED} for f in ("debited", "allotted", "invoiced", "available")]
    else:
        qty = report.qty.get("_obj")
        original_q = Decimal(item.quantity or 0)
        debited_q = boe_raw["debited_qty"]
        allotted_q = allot_raw["outstanding_qty"]
        invoiced_q = inv_raw["sold_qty"]
        qty_checks = [
            _check("debited", debited_q, getattr(qty, "debited", None), "qty"),
            _check("allotted", allotted_q, getattr(qty, "allotted", None), "qty"),
            _check("invoiced", invoiced_q, getattr(qty, "invoiced", None), "qty"),
            _check("available", original_q - debited_q - allotted_q - invoiced_q, getattr(qty, "available", None), "qty"),
        ]
    statuses = [c["status"] for c in cif_checks + qty_checks]
    if MISMATCH in statuses:
        status = MISMATCH
    elif NOT_COMPUTED in statuses:
        status = NOT_COMPUTED
    else:
        status = RECONCILED
    return {"status": status, "cif": cif_checks, "qty": qty_checks}


def _currency(license_id) -> str:
    from apps.license.models import LicenseExportItemModel

    return (LicenseExportItemModel.objects.filter(license_id=license_id).exclude(currency="")
            .values_list("currency", flat=True).first() or "usd").upper()


def build_item_drilldown(license_id: int, item_id: int) -> Optional[dict]:
    """Return the drill-down for one item, or None when the item is not on this licence."""
    data = _index(_load([license_id]))
    licence = next(iter(data["licences"]), None)
    item = next((i for i in data["items"] if i.id == item_id), None)
    if licence is None or item is None:
        return None
    return _drill_item(item, data, licence, _currency(license_id))


def _drill_item(item, data, licence, currency):
    """The drill-down for one loaded item. Shared by the item view and the licence-wide reconciliation."""
    license_id = licence.id
    report = _item_report(item, data, licence.license_number)
    sales_by_trade, debit_rows, links, cross, allot_residue = _item_inputs(item, data)
    withheld = report.unit_status == UNIT_UNVERIFIED

    allot_ids = [ai.allotment_id for ai in data["allot_by_item"].get(item.id, [])]
    on_item = {rd.bill_of_entry_id for rd in debit_rows}
    needed = set()
    for tid in sales_by_trade:
        needed |= data["trade_boe_members"].get(tid, set()) - on_item
    for aid in allot_ids:
        needed |= data["allotment_boes"].get(aid, set())
    boe_refs = _boe_refs(needed) if needed else {}

    boe = _boe_section(item, data, sales_by_trade, debit_rows, links, cross, allot_ids, withheld, currency)
    inv = _invoice_section(item, data, sales_by_trade, debit_rows, links, withheld, currency, boe_refs,
                           internal_by_trade=_internal_sales_by_trade(item, data))
    allot = _allotment_section(item, data, debit_rows, allot_residue, bool(sales_by_trade), withheld, boe_refs)
    recon = _reconciliation(item, report, boe.pop("_raw"), inv.pop("_raw"), allot.pop("_raw"), withheld)

    canonical_cif = {k: report.cif.get(k) for k in ("original", "debited", "allotted", "invoiced", "available")}
    canonical_qty = {k: report.qty.get(k) for k in ("original", "debited", "allotted", "invoiced", "available")}
    return {
        "license_id": license_id,
        "item": {
            "item_id": item.id,
            "sr": _s(item.serial_number),
            "description": item.description or "",
            "hs_code": item.hs_code.hs_code if item.hs_code_id else None,
            "unit": report.unit,
            "unit_raw": report.unit_raw,
            "unit_status": report.unit_status,
            "currency": currency,
            "original_cif": _money(item.cif_fc),
            "original_qty": None if withheld else _qty(item.quantity),
        },
        "canonical": {
            "status": report.status,
            "cif": canonical_cif if report.cif.get("_obj") is not None else {},
            "qty": {} if withheld or report.qty.get("_obj") is None else canonical_qty,
            "previous_owner_debit_cif": _money(report.previous_owner_debit_cif),
            "previous_owner_debit_qty": None if withheld else _qty(report.previous_owner_debit_qty),
        },
        "boes": boe,
        "allotments": allot,
        "invoices": inv,
        "reconciliation": recon,
    }


def _allocation_issues(drill):
    """Allocation records that need review, one per source. Each carries its own quantity and CIF."""
    issues = []
    for row in drill["boes"]["rows"]:
        flags = list(row["flags"])
        if row["kind"] == "BOE":
            if row["status"] in (CROSS_ITEM_STATUS, OVER_LINKED_BOE_STATUS) or any(f.startswith("BOE_OVER_COVERED") for f in flags):
                issues.append({
                    "kind": "BOE", "reference": row["boe_number"], "source": row["source"], "status": row["status"], "flags": flags,
                    "amount": {"qty": row["boe_qty"], "cif": row["boe_cif"]},
                })
        elif any("MIXED" in f for f in flags):
            issues.append({
                "kind": "BOE", "reference": f"Excess on {row['invoice_number']}", "source": row["source"], "status": row["status"],
                "flags": flags, "amount": {"qty": row["debited_qty"], "cif": row["debited_cif"]},
            })
    for row in drill["invoices"]["rows"]:
        flags = list(row["flags"])
        if row["status"].startswith("OVER-LINKED") or LINKED_BOE_WITHOUT_DEBIT in flags:
            issues.append({
                "kind": "INVOICE", "reference": row["invoice_number"], "source": row["source"], "status": row["status"], "flags": flags,
                "amount": {"qty": row["sold_qty"], "cif": row["sold_cif"]},
            })
    for row in drill["allotments"]["rows"]:
        flags = list(row["flags"])
        if row["status"] == "REVIEW REQUIRED" or SALE_OVERLAP in flags or RELEASE_RECORDED in flags:
            issues.append({
                "kind": "ALLOTMENT", "reference": row["reference"], "source": row["source"], "status": row["status"], "flags": flags,
                "amount": {"qty": row["outstanding_qty"], "cif": row["outstanding_cif"]},
            })
    return issues


def build_licence_source_reconciliation(license_id: int) -> Optional[dict]:
    """Source-level reconciliation for every item on a licence, from the same per-item drill-downs. Read-only."""
    data = _index(_load([license_id]))
    licence = next(iter(data["licences"]), None)
    if licence is None:
        return None
    currency = _currency(license_id)
    items = []
    for item in data["items"]:
        drill = _drill_item(item, data, licence, currency)
        items.append({
            "item_id": item.id,
            "sr": drill["item"]["sr"],
            "description": drill["item"]["description"],
            "canonical_status": drill["canonical"]["status"],
            "reconciliation": drill["reconciliation"],
            "issues": _allocation_issues(drill),
        })
    return {
        "license_id": license_id,
        "items": items,
        "items_not_reconciled": sum(1 for i in items if i["reconciliation"]["status"] != RECONCILED),
        "issue_count": sum(len(i["issues"]) for i in items),
    }
