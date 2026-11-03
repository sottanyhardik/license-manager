"""Read-only audit: sale ↔ BOE rule vs the current engine, every licence, CIF and quantity.

Writes nothing to the database. Links come from source records:
- Sale = trade SALE lines on the licence's items, grouped by trade.
- BOE debit = RowDetails 'D' rows on the licence's items.
- Link = trade↔BOE membership (trade_licensetrade_boes) where the BOE row sits on an
  item that the sale covers. Amount = the current active InvoiceBOEAllocation for that
  row and line if one exists, otherwise the full row amount (the engine's current
  all-or-nothing treatment).
Engine sale/BOE utilisation = calculate_trade + calculate_debit (unmatched BOE remainder).
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

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel  # noqa: E402
from apps.license.services.balance_calculator import LicenseBalanceCalculator as C  # noqa: E402
from apps.license.services.sale_boe_allocation import (  # noqa: E402
    AllocationError,
    BoeEntry,
    BoeLink,
    SaleEntry,
    compute_utilisation,
)

OUT = sys.argv[1]
DEC0 = Decimal("0")


def q(sql, params=()):
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# Preload everything once (read-only) to avoid per-licence scans.
sale_lines = q("""
    select tl.id, t.id, tl.sr_number_id, li.license_id, tl.cif_fc, coalesce(tl.qty_kg,0)
    from trade_licensetradeline tl
    join trade_licensetrade t on t.id = tl.trade_id
    join license_licenseimportitemsmodel li on li.id = tl.sr_number_id
    where t.direction = 'SALE'
""")
trade_boes = defaultdict(set)
for tid, bid in q("select licensetrade_id, billofentrymodel_id from trade_licensetrade_boes"):
    trade_boes[tid].add(bid)
debit_rows = q("""
    select rd.id, rd.bill_of_entry_id, rd.sr_number_id, li.license_id, rd.cif_fc,
           coalesce(rd.qty,0), b.invoice_no
    from bill_of_entry_rowdetails rd
    join license_licenseimportitemsmodel li on li.id = rd.sr_number_id
    left join bill_of_entry_billofentrymodel b on b.id = rd.bill_of_entry_id
    where rd.transaction_type = 'D'
""")
active_alloc = {}
for rd_id, line_id, cif_amt, qty_amt in q("""
    select row_details_id, trade_line_id, allocated_cif_fc, allocated_qty
    from reconciliation_invoiceboeallocation where is_current and status = 'ACTIVE'
"""):
    active_alloc[(rd_id, line_id)] = (Decimal(cif_amt or 0), Decimal(qty_amt or 0))
rd_ids_by_bid_item = defaultdict(list)
for rd_id, bid, item, lic, cif_amt, qty_amt, inv in debit_rows:
    rd_ids_by_bid_item[(bid, item)].append((rd_id, Decimal(cif_amt or 0), Decimal(qty_amt or 0), inv))

lines_by_license = defaultdict(list)
for line_id, trade_id, item, lic, cif_amt, qty_amt in sale_lines:
    lines_by_license[lic].append((line_id, trade_id, item, Decimal(cif_amt or 0), Decimal(qty_amt or 0)))
debits_by_license = defaultdict(list)
for row in debit_rows:
    debits_by_license[row[3]].append(row)
items_by_license = defaultdict(list)
for item_id, lic, qty_amt in q("select id, license_id, coalesce(quantity,0) from license_licenseimportitemsmodel"):
    items_by_license[lic].append((item_id, Decimal(qty_amt or 0)))
export_cif_fc = {}

rows = []
for lic in LicenseDetailsModel.objects.order_by("id").iterator():
    lic_id = lic.id
    items = items_by_license.get(lic_id, [])
    original_cif = sum((Decimal(r) for r in q("select coalesce(sum(cif_fc),0) from license_licenseimportitemsmodel where license_id=%s", (lic_id,))[0]), DEC0)
    original_qty = sum((qty for _, qty in items), DEC0)

    lines = lines_by_license.get(lic_id, [])
    sale_map = defaultdict(lambda: {"cif": DEC0, "qty": DEC0, "lines": []})
    for line_id, trade_id, item, cif_amt, qty_amt in lines:
        sale_map[trade_id]["cif"] += cif_amt
        sale_map[trade_id]["qty"] += qty_amt
        sale_map[trade_id]["lines"].append((line_id, item))

    debits = debits_by_license.get(lic_id, [])
    # Hidden = the engine's own definition (audit-trail aware), not the raw OTH string.
    visible_ids = set(C.get_debit_rows(lic).values_list("id", flat=True))
    all_ids = set(C.get_debit_rows(lic, include_hidden=True).values_list("id", flat=True))
    hidden_row_ids = all_ids - visible_ids
    boe_entries = {}
    hidden_entries = {}
    for rd_id, bid, item, _lic, cif_amt, qty_amt, inv in debits:
        entry = {"bid": bid, "item": item, "cif": Decimal(cif_amt or 0), "qty": Decimal(qty_amt or 0), "inv": inv}
        if rd_id in hidden_row_ids:
            hidden_entries[rd_id] = entry
        else:
            boe_entries[rd_id] = entry

    link_defs = []  # (link_id, rd_id, trade_id, cif, qty, cross_item)
    for trade_id, s in sale_map.items():
        for rd_id, e in boe_entries.items():
            if e["bid"] not in trade_boes.get(trade_id, set()):
                continue
            same_item_lines = [lid for lid, item in s["lines"] if item == e["item"]]
            if not same_item_lines:
                link_defs.append((f"X{rd_id}-T{trade_id}", rd_id, trade_id, DEC0, DEC0, True))
                continue
            line_id = same_item_lines[0]
            if (rd_id, line_id) in active_alloc:
                a_cif, a_qty = active_alloc[(rd_id, line_id)]
            else:
                a_cif, a_qty = e["cif"], e["qty"]
            link_defs.append((f"L{rd_id}-T{trade_id}", rd_id, trade_id, a_cif, a_qty, False))

    cross_item = sum(1 for d in link_defs if d[5])
    sales = [SaleEntry(f"T{tid}", s["cif"], s["qty"]) for tid, s in sale_map.items()]
    boes = [BoeEntry(f"R{rd}", e["cif"], e["qty"]) for rd, e in boe_entries.items()]
    links_cif = [BoeLink(lid, f"R{rd}", f"T{tid}", c) for lid, rd, tid, c, _q, x in link_defs if not x]
    links_qty = [BoeLink(lid, f"R{rd}", f"T{tid}", cif=DEC0, qty=qq) for lid, rd, tid, _c, qq, x in link_defs if not x]

    status = "OK"
    try:
        r_cif = compute_utilisation(measure="cif", original=original_cif, sales=sales, boes=boes, links=links_cif)
        r_qty = compute_utilisation(measure="qty", original=original_qty, sales=sales, boes=boes, links=links_qty)
    except AllocationError as exc:
        status = f"ALLOCATION_ERROR: {exc}"[:200]
        r_cif = r_qty = None

    engine_sale_boe = None
    engine_available = None
    try:
        engine_sale_boe = C.calculate_trade(lic) + C.calculate_debit(lic)
        engine_available = C.calculate_financial_balance(lic)
    except Exception as exc:  # pragma: no cover
        status = f"ENGINE_ERROR {type(exc).__name__}"

    hidden_cif = sum((e["cif"] for e in hidden_entries.values()), DEC0)
    unlinked_boe_cif = sum((e["cif"] for rd, e in boe_entries.items()
                            if not any(rd == d[1] and not d[5] for d in link_defs)), DEC0)
    sold_no_boe = sum((s["cif"] for tid, s in sale_map.items()
                       if not any(d[2] == tid and not d[5] for d in link_defs)), DEC0)
    dup_boe = sum(1 for rd in boe_entries if sum(1 for d in link_defs if d[1] == rd and not d[5]) > 1)
    unmapped_items = sum(1 for (item_id, _q) in items if q("select hs_code_id from license_licenseimportitemsmodel where id=%s", (item_id,))[0][0] is None)

    row = {
        "licence_id": lic_id,
        "licence_number": lic.license_number,
        "original_cif": original_cif,
        "original_qty": original_qty,
        "sold_cif": sum((s["cif"] for s in sale_map.values()), DEC0),
        "sold_qty": sum((s["qty"] for s in sale_map.values()), DEC0),
        "boe_cif_all": sum((e["cif"] for e in boe_entries.values()), DEC0),
        "hidden_rows_excluded": len(hidden_entries),
        "boe_qty_all": sum((e["qty"] for e in boe_entries.values()), DEC0),
        "linked_cif": sum((d[3] for d in link_defs if not d[5]), DEC0),
        "linked_qty": sum((d[4] for d in link_defs if not d[5]), DEC0),
        "cross_item_links": cross_item,
        "hidden_boe_cif": hidden_cif,
        "unlinked_boe_cif": unlinked_boe_cif,
        "sold_without_boe_cif": sold_no_boe,
        "duplicate_boe_links": dup_boe,
        "unmapped_items": unmapped_items,
        "engine_sale_boe_utilisation": engine_sale_boe,
        "engine_available_cif": engine_available,
        "rule_utilised_cif": r_cif.utilised if r_cif else None,
        "rule_available_cif": r_cif.available if r_cif else None,
        "rule_over_linked_cif": r_cif.over_linked_total if r_cif else None,
        "rule_available_qty": r_qty.available if r_qty else None,
        "rule_over_linked_qty": r_qty.over_linked_total if r_qty else None,
        "status": status,
    }
    if r_cif and engine_sale_boe is not None:
        row["engine_vs_rule_sale_boe_cif"] = (r_cif.utilised - engine_sale_boe)
    else:
        row["engine_vs_rule_sale_boe_cif"] = None
    rows.append(row)

with open(OUT, "w", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

with_sales = [r for r in rows if r["sold_cif"] > 0]
print("licences:", len(rows), " with sales:", len(with_sales))
print("status != OK:", sum(1 for r in rows if r["status"] != "OK"))
print("licences with any BOE-linked sale:", sum(1 for r in rows if r["linked_cif"] > 0))
print("licences with rule ≠ engine (sale/BOE utilisation):",
      sum(1 for r in rows if r["engine_vs_rule_sale_boe_cif"] not in (None,) and abs(r["engine_vs_rule_sale_boe_cif"]) > Decimal("0.01")))
print("licences with over-linked sales:", sum(1 for r in rows if (r["rule_over_linked_cif"] or 0) > 0))
print("licences with sales but no BOE links:", sum(1 for r in rows if r["sold_cif"] > 0 and r["linked_cif"] == 0))
print("licences with duplicate BOE links:", sum(1 for r in rows if r["duplicate_boe_links"] > 0))
print("licences with cross-item links:", sum(1 for r in rows if r["cross_item_links"] > 0))
print("licences with unmapped items:", sum(1 for r in rows if r["unmapped_items"] > 0))
print("total sold CIF:", sum(r["sold_cif"] for r in rows), " total linked CIF:", sum(r["linked_cif"] for r in rows))
