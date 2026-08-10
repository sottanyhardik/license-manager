"""
BL-PLAN-01 supporting context (read-only queries against the real local
"lmanagement" DB, 228 licenses) -- establishes that:

  1. detect_norm() currently classifies 2 real licenses as E132 and 0 as
     E126 (so the floor/cif bug has not yet been triggered by a real
     license in THIS snapshot -- see finding notes for why it is still a
     live, provable defect).
  2. Fractional / odd available_quantity values are common in this same
     database for OTHER norms (E1), confirming the DGFT-sourced weight
     figures that would trigger this bug on an E126/E132 license are an
     entirely realistic occurrence, not a contrived edge case.
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

from collections import Counter  # noqa: E402
from decimal import Decimal  # noqa: E402

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel  # noqa: E402
from apps.license.services.e132_plan import classify_e132_record  # noqa: E402
from apps.license.services.norm_plan import detect_norm  # noqa: E402


def main():
    counts = Counter(detect_norm(lic) for lic in LicenseDetailsModel.objects.all())
    print("detect_norm() distribution across all 228 real licenses:", dict(counts))

    print("\nThe 2 real E132 licenses and their import items' classification:")
    for lic in LicenseDetailsModel.objects.all():
        if detect_norm(lic) != "E132":
            continue
        print(f"LICENSE id={lic.id} number={lic.license_number} balance_cif={float(lic.get_balance_cif or 0)}")
        for ii in lic.import_license.all().select_related("hs_code"):
            item, reason = classify_e132_record(
                ii.hs_code.hs_code if ii.hs_code else None, ii.description
            )
            print(
                f"    import_item={ii.id} available_quantity={ii.available_quantity} "
                f"-> classified={item!r}  ({reason})"
            )

    print(
        "\nFractional available_quantity DOES occur in this same real DB "
        "(other norms) -- confirms the underlying data shape that would "
        "trigger BL-PLAN-01 on an E126/E132 license is realistic:"
    )
    total = 0
    frac = 0
    examples = []
    for ii in LicenseImportItemsModel.objects.all():
        total += 1
        aq = ii.available_quantity
        if aq is not None and aq != aq.to_integral_value():
            frac += 1
            if len(examples) < 10:
                examples.append((ii.id, ii.license_id, aq))
    print(f"  {frac} of {total} import items across the whole DB have a fractional available_quantity")
    for iid, lic_id, aq in examples:
        print(f"    import_item={iid} license_id={lic_id} available_quantity={aq}")


if __name__ == "__main__":
    main()
