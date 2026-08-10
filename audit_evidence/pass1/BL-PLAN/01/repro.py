"""
BL-PLAN-01 evidence script.

Demonstrates that compute_e126_auto_plan() / compute_e132_auto_plan()
(backend/apps/license/services/e126_auto_plan.py,
backend/apps/license/services/e132_auto_plan.py) persist a LicenseItemPlan
row whose planned_cif_fc does NOT equal planned_quantity * unit_price,
whenever the classified quantity for a category (in particular, either half
of the PKO/Olive-Oil 50/50 split for E126, or the PKO/Cheese 40/60 split for
E132) is not a whole number.

Root cause (both files, identical pattern):

    fqty = _floor_qty(planned_qty)   # floors the engine's raw quantity
    cif  = _r2(planned_cif)          # but keeps the CIF computed from the
                                      # UN-FLOORED quantity -- never
                                      # recomputed as fqty * unit_price.

    item_lines.append({
        'planned_quantity': fqty,
        'unit_price':       _r2(unit_price),
        'planned_cif_fc':   cif,     # <-- inconsistent with fqty*unit_price
        ...
    })

This reproduction calls the REAL, unmodified production function
`plan_e126_per_item_split` (services/e126_plan.py) with a realistic
E126 PKO/Olive-Oil split-eligible record, then applies the EXACT
`_floor_qty` / `_r2` helpers copied verbatim from
services/e126_auto_plan.py to show the persisted-row values it would
produce (no DB writes are performed).

Sibling engine E5 shows the CORRECT pattern for the exact same
"floor the auto-plan quantity to a whole number" requirement -- see
`_fixed_rate_line()` in services/e5_plan.py, which recomputes
`planned_cif = planned_qty * rate` AFTER flooring `planned_qty`. E126/E132's
auto-plan modules deviate from this established, correct pattern.
"""
import math
import os
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

from apps.license.services.e126_plan import plan_e126_per_item_split  # noqa: E402


def _r2(x):
    """Copied verbatim from e126_auto_plan.py / e132_auto_plan.py."""
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return 0.0


def _floor_qty(x):
    """Copied verbatim from e126_auto_plan.py / e132_auto_plan.py."""
    try:
        return float(math.floor(float(x)))
    except (TypeError, ValueError):
        return 0.0


def main():
    # A PKO/Olive-Oil split-eligible E126 record whose summed group
    # available_quantity (101) is an ODD whole number -- an entirely
    # ordinary real-world DGFT weight figure (see e.g. the real DB's
    # license 2435 / import item 37986, available_quantity=4959.00, also
    # odd -- audit_evidence/pass1/BL-PLAN/01/query_result.txt).
    records = [
        {
            "record_id": 1,
            "hs_code": "15132900",
            "description": "PALM KERNEL OIL / OLIVE OIL BLEND 1509 1513",
            "quantity": Decimal("101"),
        },
    ]
    # balance_cif == exactly the base 50/50 split's value, so the
    # wastage-rebalance pass has nothing to shift (isolates the floor/cif
    # bug from the (correct, by-design) wastage-rebalance behaviour).
    balance_cif = Decimal("50.5") * Decimal("1.80") + Decimal("50.5") * Decimal("5.00")
    print("balance_cif =", balance_cif)

    split_result = plan_e126_per_item_split(records, balance_cif)
    print("\nRaw engine output (plan_e126_per_item_split, unmodified production code):")
    for line in split_result[1]:
        print(" ", line)

    print("\nPersisted LicenseItemPlan row values exactly as compute_e126_auto_plan builds them:")
    total_planned_cif = 0.0
    for line in split_result[1]:
        fqty = _floor_qty(line["planned_quantity"])
        cif = _r2(line["planned_cif"])
        unit_price = _r2(line["unit_price"])
        total_planned_cif += cif
        expected_cif_from_saved_qty = round(fqty * unit_price, 2)
        mismatch = round(cif - expected_cif_from_saved_qty, 4)
        print(
            f"  item_name={line['planning_item']!r}  "
            f"planned_quantity={fqty}  unit_price={unit_price}  planned_cif_fc={cif}"
        )
        print(
            f"    -> planned_quantity * unit_price = {expected_cif_from_saved_qty}"
            f"   MISMATCH (planned_cif_fc - qty*price) = {mismatch}"
        )
    print(
        "\ntotal_planned_cif recorded against license balance:",
        total_planned_cif,
        " vs balance_cif:",
        float(balance_cif),
    )
    print(
        "\nNet effect: 1 unit of the group's 101-unit available_quantity "
        "(101 - 50 - 50 = 1) is NEVER recorded in any plan line's "
        "planned_quantity, yet 100% of balance_cif ($343.40) is marked "
        "consumed -- $3.40 of real DFIA license CIF entitlement is "
        "permanently unaccounted for against any plannable quantity."
    )


if __name__ == "__main__":
    main()
