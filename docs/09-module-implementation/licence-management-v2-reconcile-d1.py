"""Read-only D-1 reconciliation across all licences.

Writes nothing to the database. Compares the current engines (financial list
figure and customs figure) with a D-1 reconstruction that:
  - Original  = sum of import-item cif_fc (authorised CIF, FC)
  - BOE       = sum of BOE debit rows (RowDetails 'D') on the licence's items
  - Allotment = outstanding reservation per allotment item:
        unlinked allotment          -> full cif_fc
        allotment linked to BOE(s)  -> max(0, cif_fc - BOE debit on that item
                                       within the linked BOEs)   [D-1 s3.4]
  - Billed without BOE = 0 (no reliable invoice-to-licence relation found)
"""
import csv
import os
import sys
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

from django.db.models import Sum  # noqa: E402

from apps.allotment.models import AllotmentItems  # noqa: E402
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails  # noqa: E402
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel  # noqa: E402
from apps.license.services.balance_calculator import LicenseBalanceCalculator as C  # noqa: E402

DEC0 = Decimal("0")
M2M = BillOfEntryModel.allotment.through  # billofentrymodel_id <-> allotmentmodel_id
OUT = sys.argv[1]


def q2(value):
    return Decimal(value or 0).quantize(Decimal("0.01"))


rows = []
for lic in LicenseDetailsModel.objects.order_by("id").iterator():
    items = LicenseImportItemsModel.objects.filter(license=lic)
    original = q2(items.aggregate(t=Sum("cif_fc"))["t"])

    boe = q2(
        RowDetails.objects.filter(sr_number__license=lic, transaction_type="D")
        .aggregate(t=Sum("cif_fc"))["t"]
    )

    allot_open = DEC0
    residue_items = 0
    linked_items = 0
    for ai in AllotmentItems.objects.filter(item__license=lic, status="CREATED"):
        boe_ids = list(M2M.objects.filter(allotmentmodel_id=ai.allotment_id).values_list("billofentrymodel_id", flat=True))
        if not boe_ids:
            allot_open += ai.cif_fc or DEC0
            continue
        linked_items += 1
        debit = (
            RowDetails.objects.filter(
                sr_number_id=ai.item_id, transaction_type="D", bill_of_entry_id__in=boe_ids
            ).aggregate(t=Sum("cif_fc"))["t"]
            or DEC0
        )
        residue = max(DEC0, (ai.cif_fc or DEC0) - min(ai.cif_fc or DEC0, debit))
        if residue > 0:
            residue_items += 1
        allot_open += residue
    allot_open = q2(allot_open)

    d1_available = q2(original - boe - allot_open)
    financial = q2(C.calculate_financial_balance(lic))
    customs = q2(C.calculate_balance(lic))
    purchase = q2(C.calculate_purchase_credit(lic))
    trade = q2(C.calculate_trade(lic))

    if d1_available < 0:
        klass = "over_utilised_under_D1"
    elif purchase or trade:
        klass = "purchase_or_trade_activity"
    elif linked_items and residue_items:
        klass = "linked_allotment_residue"
    elif financial != d1_available:
        klass = "other_difference"
    else:
        klass = "match"

    rows.append({
        "licence_id": lic.id,
        "licence_number": lic.license_number,
        "original_cif_fc": original,
        "boe_cif_fc": boe,
        "allotment_outstanding_fc": allot_open,
        "billed_without_boe_fc": DEC0,
        "d1_available_fc": d1_available,
        "list_financial_fc": financial,
        "customs_fc": customs,
        "purchase_credit_fc": purchase,
        "trade_debit_fc": trade,
        "diff_d1_minus_list": q2(d1_available - financial),
        "linked_allotment_items": linked_items,
        "linked_items_with_residue": residue_items,
        "classification": klass,
    })

with open(OUT, "w", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

from collections import Counter  # noqa: E402

counts = Counter(r["classification"] for r in rows)
print("licences:", len(rows))
for k, v in counts.most_common():
    print(f"  {k}: {v}")
match_diff = sum(abs(r["diff_d1_minus_list"]) for r in rows)
print("sum |D1 - list| FC:", match_diff)
print("total residue FC:", sum(r["allotment_outstanding_fc"] for r in rows))
