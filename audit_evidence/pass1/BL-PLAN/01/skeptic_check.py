"""
BL-PLAN-01 — SKEPTIC independent re-verification script.

Does NOT reuse the claimant's repro.py. Written independently in this
verification pass, calling the same real, unmodified production function
(apps.license.services.e126_plan.plan_e126_per_item_split) but with
DIFFERENT synthetic inputs (available_quantity=77, not 101; a different
HS/description string) to rule out that the reported mismatch was somehow
an artifact of the claimant's specific chosen numbers. The exact
_floor_qty()/_r2() arithmetic applied below was verified by directly
reading backend/apps/license/services/e126_auto_plan.py lines 104-116 and
242-266 in this session (not copied blind from the claimant's script).

Run with:
  cd backend && PYTHONPATH=. ../.venv/bin/python \
      ../audit_evidence/pass1/BL-PLAN/01/skeptic_check.py

No DB writes are performed anywhere in this script.
"""
import math
import os
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

from apps.license.services.e126_plan import plan_e126_per_item_split  # noqa: E402


def _r2(x):
    """Copied verbatim from e126_auto_plan.py (verified by direct Read,
    lines 104-108, during this verification session)."""
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return 0.0


def _floor_qty(x):
    """Copied verbatim from e126_auto_plan.py (verified by direct Read,
    lines 111-115, during this verification session)."""
    try:
        return float(math.floor(float(x)))
    except (TypeError, ValueError):
        return 0.0


def check_lines(label, lines):
    any_mismatch = False
    total_cif = 0.0
    for sp in lines:
        planned_qty = sp.get("planned_quantity")
        unit_price = sp.get("unit_price")
        planned_cif = sp.get("planned_cif")
        if not planned_qty or float(planned_qty) <= 0 or planned_cif is None:
            continue
        fqty = _floor_qty(planned_qty)
        cif = _r2(planned_cif)
        up = _r2(unit_price) if unit_price is not None else 0.0
        if fqty <= 0 or cif <= 0:
            continue
        expected = round(fqty * up, 2)
        mismatch = round(cif - expected, 4)
        total_cif += cif
        if mismatch != 0:
            any_mismatch = True
        print(
            f"  [{label}] {sp['planning_item']}: raw_planned_quantity={planned_qty} "
            f"raw_planned_cif={planned_cif} -> SAVED planned_quantity={fqty} "
            f"unit_price={up} planned_cif_fc={cif}  qty*price={expected}  "
            f"MISMATCH={mismatch}"
        )
    return any_mismatch, total_cif


def main():
    print("=== Independent re-run: available_quantity=77 (claimant used 101) ===")
    qty = Decimal("77")
    # balance_cif == exactly the base 50/50 split's value, so the
    # wastage-rebalance pass (verified separately, see notes.md) has
    # nothing to shift -- isolates the floor/cif bug on its own, same
    # isolation technique as the claimant's repro but with different
    # numbers and a different HS/description string.
    balance_cif = qty / 2 * Decimal("1.80") + qty / 2 * Decimal("5.00")
    print("balance_cif =", balance_cif)
    records = [
        {
            "record_id": 99,
            "hs_code": "1513",
            "description": "PKO OLIVE OIL BLEND 1509",
            "quantity": qty,
        }
    ]
    split_result = plan_e126_per_item_split(records, balance_cif)
    lines = split_result[99]
    print("\nRaw engine output (plan_e126_per_item_split, unmodified production code):")
    for line in lines:
        print(" ", line)
    print("\nSimulated persisted LicenseItemPlan row construction (non-preserved branch):")
    any_mismatch, total_cif = check_lines("qty=77", lines)
    print(f"\ntotal recorded planned_cif_fc = {total_cif}  vs balance_cif = {float(balance_cif)}")
    print("ANY_MISMATCH:", any_mismatch)

    print("\n=== Control: available_quantity=100 (EVEN -> 50/50 split is whole) ===")
    records2 = [
        {
            "record_id": 100,
            "hs_code": "1513",
            "description": "PKO OLIVE OIL BLEND 1509",
            "quantity": Decimal("100"),
        }
    ]
    balance_cif2 = Decimal("50") * Decimal("1.80") + Decimal("50") * Decimal("5.00")
    split_result2 = plan_e126_per_item_split(records2, balance_cif2)
    lines2 = split_result2[100]
    any_mismatch2, total_cif2 = check_lines("qty=100 (control)", lines2)
    print("ANY_MISMATCH (control, should be False):", any_mismatch2)

    print("\n=== FINAL VERDICT ===")
    print("Fractional-split case reproduces the mismatch:", any_mismatch)
    print("Whole-number control case does NOT mismatch:", not any_mismatch2)


if __name__ == "__main__":
    main()
