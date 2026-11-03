"""Read-only item-level audit (CIF and quantity), every licence item.

Per SR item:
- Original = import item quantity and cif_fc.
- Invoiced = SALE trade lines on the item (full amount), of which BOE-covered is shown as a sub-amount.
- Debited  = BOE debit rows on the item not covered by a sale, plus over-linked excess.
- Allotted = outstanding allotment residue on the item: full cif/qty when the parent allotment has no BOE link,
             otherwise max(0, allotted − BOE debit matched on the item within the linked BOEs).
- Available = Original − Debited − Allotted − Invoiced (mutually exclusive by construction).
Compared with the stored item columns (debited_value, allotted_value, available_value) as the "old" view.
Writes nothing to the database.
"""
import csv
import os
import sys
from collections import defaultdict
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

from django.db import connection  # noqa: E402

from apps.license.services.sale_boe_allocation import (  # noqa: E402
    AllocationError,
    BoeEntry,
    BoeLink,
    SaleEntry,
    compute_utilisation,
)

OUT = sys.argv[1]
DEC0 = Decimal("0")


def rows(sql, params=()):
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def unit_class(u):
    if u is None:
        return "MISSING"
    key = u.strip()
    if key.lower() == "kg":
        return "KG (case-normalised)" if key != "kg" else "kg"
    if key.lower() == "mts":
        return "MTS (unverified: tonnes or kg?)"
    return f"OTHER:{key}"


items = rows("""select li.id, li.license_id, li.serial_number, li.unit, coalesce(li.quantity,0),
                       coalesce(li.cif_fc,0), li.hs_code_id, coalesce(li.debited_value,0),
                       coalesce(li.allotted_value,0), coalesce(li.available_value,0)
                from license_licenseimportitemsmodel li order by li.id""")
sales = defaultdict(list)  # item -> [(trade_id, line_id, cif, qty)]
for trade_id, line_id, item, cif_amt, qty_amt in rows("""
        select t.id, tl.id, tl.sr_number_id, tl.cif_fc, coalesce(tl.qty_kg,0)
        from trade_licensetradeline tl join trade_licensetrade t on t.id = tl.trade_id
        where t.direction = 'SALE' and tl.sr_number_id is not null"""):
    sales[item].append((trade_id, line_id, Decimal(cif_amt or 0), Decimal(qty_amt or 0)))
trade_boes = defaultdict(set)
boe_trades = defaultdict(set)
for tid, bid in rows("select licensetrade_id, billofentrymodel_id from trade_licensetrade_boes"):
    trade_boes[tid].add(bid)
    boe_trades[bid].add(tid)
from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden  # noqa: E402

# Hidden previous-owner BOEs are excluded with the engine's own definition (audit-trail aware).
VISIBLE_D_ROWS = set(annotate_and_exclude_hidden(
    RowDetails.objects.filter(transaction_type='D', sr_number__isnull=False), boe_field='bill_of_entry'
).values_list('id', flat=True))

debits = defaultdict(list)  # item -> [(rd_id, bid, cif, qty)]  (visible rows only)
for rd_id, bid, item, cif_amt, qty_amt in rows("""
        select rd.id, rd.bill_of_entry_id, rd.sr_number_id, rd.cif_fc, coalesce(rd.qty,0)
        from bill_of_entry_rowdetails rd where rd.transaction_type = 'D' and rd.sr_number_id is not null"""):
    if rd_id not in VISIBLE_D_ROWS:
        continue
    debits[item].append((rd_id, bid, Decimal(cif_amt or 0), Decimal(qty_amt or 0)))
active_alloc = {}
for rd_id, line_id, cif_amt, qty_amt in rows("""
        select row_details_id, trade_line_id, allocated_cif_fc, coalesce(allocated_qty,0)
        from reconciliation_invoiceboeallocation where is_current and status = 'ACTIVE'"""):
    active_alloc[(rd_id, line_id)] = (Decimal(cif_amt or 0), Decimal(qty_amt or 0))
allot_items = defaultdict(list)  # item -> [(allotment_id, cif, qty)]
for allot_id, item, cif_amt, qty_amt in rows("""
        select ai.allotment_id, ai.item_id, ai.cif_fc, coalesce(ai.qty,0)
        from allotment_allotmentitems ai where ai.status = 'CREATED'"""):
    allot_items[item].append((allot_id, Decimal(cif_amt or 0), Decimal(qty_amt or 0)))
allot_boe = defaultdict(set)
for allot_id, bid in rows("select allotmentmodel_id, billofentrymodel_id from bill_of_entry_billofentrymodel_allotment"):
    allot_boe[allot_id].add(bid)

out = []
for (item_id, lic_id, serial, unit, qty_auth, cif_auth, hs, old_debit, old_allot, old_avail) in items:
    qty_auth = Decimal(qty_auth or 0)
    cif_auth = Decimal(cif_auth or 0)
    item_sales = sales.get(item_id, [])
    item_debits = debits.get(item_id, [])
    if not item_sales and not item_debits and not allot_items.get(item_id) and cif_auth == 0 and qty_auth == 0:
        continue

    # Sale-side keys: one SaleEntry per trade on this item.
    sale_by_trade = defaultdict(lambda: [DEC0, DEC0])
    for trade_id, _line, cif_amt, qty_amt in item_sales:
        sale_by_trade[trade_id][0] += cif_amt
        sale_by_trade[trade_id][1] += qty_amt

    boe_cif = {}
    boe_qty = {}
    for rd_id, bid, cif_amt, qty_amt in item_debits:
        key = f"R{rd_id}"
        boe_cif[key] = cif_amt
        boe_qty[key] = qty_amt

    links_cif, links_qty, cross = [], [], 0
    # Cross-item from the BOE side: a trade linked to this BOE with no sale line on this item.
    for rd_id, bid, _c, _q in item_debits:
        for tid in boe_trades.get(bid, set()):
            if not any(t == tid for (t, _l, _c2, _q2) in item_sales):
                cross += 1
    for trade_id, _line_ids in ((t, None) for t in sale_by_trade):
        for rd_id, bid, cif_amt, qty_amt in item_debits:
            if bid not in trade_boes.get(trade_id, set()):
                continue
            line_ids = [lid for (t, lid, _c, _q) in item_sales if t == trade_id]
            if not line_ids:
                cross += 1
                continue
            a = active_alloc.get((rd_id, line_ids[0]))
            a_cif, a_qty = a if a else (cif_amt, qty_amt)
            links_cif.append(BoeLink(f"L{rd_id}-T{trade_id}", f"R{rd_id}", f"T{trade_id}", a_cif))
            links_qty.append(BoeLink(f"L{rd_id}-T{trade_id}", f"R{rd_id}", f"T{trade_id}", qty=a_qty))

    sales_cif = [SaleEntry(f"T{t}", v[0], v[1]) for t, v in sale_by_trade.items()]
    boes_cif = [BoeEntry(k, boe_cif[k]) for k in boe_cif]
    boes_qty = [BoeEntry(k, qty=boe_qty[k]) for k in boe_qty]

    # Over-allocation of a BOE row across sales is a hard error: record it, do not compute.
    status_flags = []
    try:
        r_cif = compute_utilisation(measure="cif", original=cif_auth, sales=sales_cif, boes=boes_cif, links=links_cif)
        r_qty = compute_utilisation(measure="qty", original=qty_auth, sales=[SaleEntry(s.sale_id, qty=s.qty) for s in sales_cif], boes=boes_qty, links=links_qty)
    except AllocationError as exc:
        status_flags.append(f"OVER_ALLOCATED")
        r_cif = r_qty = None
        err = str(exc)[:160]
    else:
        err = ""

    # Allotted residue (D-1 §3.4 style), CIF and quantity.
    allot_cif = DEC0
    allot_qty = DEC0
    allot_mixed_with_sale = bool(allot_items.get(item_id)) and bool(item_sales)
    for allot_id, a_cif, a_qty in allot_items.get(item_id, []):
        bids = allot_boe.get(allot_id, set())
        if not bids:
            allot_cif += a_cif
            allot_qty += a_qty
            continue
        debit_c = sum((c for rd, b, c, _q in item_debits if b in bids), DEC0)
        debit_q = sum((q for rd, b, _c, q in item_debits if b in bids), DEC0)
        allot_cif += max(DEC0, a_cif - min(a_cif, debit_c))
        allot_qty += max(DEC0, a_qty - min(a_qty, debit_q))

    invoiced_cif = sum((v[0] for v in sale_by_trade.values()), DEC0)
    invoiced_qty = sum((v[1] for v in sale_by_trade.values()), DEC0)
    if r_cif:
        # Debited = uncovered BOE plus over-linked excess (approved rule: excess is never dropped).
        debited_cif = r_cif.uncovered_boe_total + r_cif.over_linked_total
        debited_qty = r_qty.uncovered_boe_total + r_qty.over_linked_total
        covered_cif = r_cif.covered_total
        available_cif = cif_auth - debited_cif - allot_cif - invoiced_cif
        available_qty = qty_auth - debited_qty - allot_qty - invoiced_qty
    else:
        debited_cif = debited_qty = covered_cif = DEC0
        available_cif = available_qty = None

    flags = list(status_flags)
    if cross:
        flags.append("CROSS_ITEM_LINK")
    if allot_mixed_with_sale:
        flags.append("ALLOT_AND_SALE_ON_ITEM_OVERLAP_UNVERIFIED")
    if unit_class(unit).startswith("MTS"):
        flags.append("UNIT_UNVERIFIED")
    if unit is None or unit.strip().lower() not in ("kg", "mts"):
        flags.append("UNIT_CHECK")
    if available_cif is not None and available_cif < 0:
        flags.append("OVER_UTILISED")
    if hs is None:
        flags.append("UNMAPPED_HS")
    if not flags:
        status = "RECONCILED"
    elif "OVER_ALLOCATED" in flags:
        status = "OVER_ALLOCATED"
    elif "OVER_UTILISED" in flags and len(flags) == 1:
        status = "OVER_UTILISED"
    elif "UNMAPPED_HS" in flags and len(flags) == 1:
        status = "UNMAPPED ITEM"
    else:
        status = "REVIEW REQUIRED"

    out.append({
        "item_id": item_id, "licence_id": lic_id, "sr": serial, "unit_raw": unit, "unit_class": unit_class(unit),
        "original_qty": qty_auth, "debited_qty": debited_qty, "allotted_qty": allot_qty, "invoiced_qty": invoiced_qty,
        "available_qty": available_qty,
        "original_cif": cif_auth, "debited_cif": debited_cif, "allotted_cif": allot_cif,
        "invoiced_cif": invoiced_cif, "invoiced_cif_boe_covered": covered_cif,
        "available_cif": available_cif,
        "old_debited_value": Decimal(old_debit), "old_allotted_value": Decimal(old_allot), "old_available_value": Decimal(old_avail),
        "cross_item_links": cross,
        "flags": "|".join(flags), "status": status, "error": err,
    })

with open(OUT, "w", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
    writer.writeheader()
    writer.writerows(out)

from collections import Counter  # noqa: E402

print("items audited:", len(out))
print("status:", dict(Counter(r["status"] for r in out)))
print("unit classes:", dict(Counter(r["unit_class"] for r in out)))
print("items with allot+sale overlap (unverified):", sum(1 for r in out if "ALLOT_AND_SALE" in r["flags"]))
print("items with cross-item links:", sum(1 for r in out if r["cross_item_links"] > 0))
print("items with stored available ≠ new available (CIF):",
      sum(1 for r in out if r["available_cif"] is not None and abs(Decimal(r["available_cif"]) - r["old_available_value"]) > Decimal("0.01")))
print("items with stored debited ≠ new debited (CIF):",
      sum(1 for r in out if abs(r["debited_cif"] - r["old_debited_value"]) > Decimal("0.01")))
print("items with negative available CIF:", sum(1 for r in out if r["available_cif"] is not None and r["available_cif"] < 0))
