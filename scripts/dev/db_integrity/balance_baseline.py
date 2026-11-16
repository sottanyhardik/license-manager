"""Per-licence CIF balance baseline (read-only).

Usage (from repo root):
    backend/.venv/bin/python scripts/dev/db_integrity/balance_baseline.py OUT.csv

Writes one row per licence with every LicenseBalanceCalculator term, the signed
customs/financial balances, the over-utilisation flag and the stored LicenseBalance
value(s), then prints a summary (negatives, engine divergence, stale stored rows).
Compare two runs with ``diff_baseline.py``.
"""
from __future__ import annotations

import collections
import csv
import sys
from decimal import Decimal

from _common import read_only, setup

TERMS = [
    "calculate_credit",
    "calculate_boe_debit_total",
    "calculate_debit",
    "calculate_allotment",
    "calculate_trade",
    "calculate_balance",
    "calculate_financial_balance",
]


def main(out_path: str) -> int:
    setup()
    from django.apps import apps

    from apps.license.services.balance_calculator import LicenseBalanceCalculator as C

    License = apps.get_model("license", "LicenseDetailsModel")
    LicenseBalance = apps.get_model("license", "LicenseBalance")
    rows, errors = [], collections.Counter()

    with read_only():
        fk = next(f.name for f in LicenseBalance._meta.fields if f.is_relation)
        stored: dict[int, list[Decimal]] = {}
        for r in LicenseBalance.objects.values(f"{fk}_id", "balance_cif"):
            stored.setdefault(r[f"{fk}_id"], []).append(r["balance_cif"])
        for lic in License.objects.order_by("id").iterator(chunk_size=200):
            row = {"id": lic.id, "license_number": lic.license_number}
            for name in TERMS:
                try:
                    row[name] = getattr(C, name)(lic)
                except Exception as exc:  # recorded, never swallowed silently
                    row[name] = "ERR"
                    errors[(name, type(exc).__name__, str(exc)[:80])] += 1
            bal = row["calculate_balance"]
            row["is_over_utilised"] = isinstance(bal, Decimal) and C.is_over_utilised(bal)
            vals = stored.get(lic.id) or []
            row["stored"] = "|".join(str(v) for v in vals)
            rows.append(row)

    if not rows:
        print("no licences found")
        return 0
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    ok = [r for r in rows if all(isinstance(r[t], Decimal) for t in TERMS)]
    neg = [r for r in ok if r["calculate_balance"] < 0]
    diverge = [r for r in ok if r["calculate_balance"] != r["calculate_financial_balance"]]
    stale = [
        r for r in ok
        if r["stored"] and "|" not in r["stored"]
        and abs(Decimal(r["stored"]) - r["calculate_financial_balance"]) > Decimal("0.01")
    ]
    print(f"licences={len(rows)} errors={dict(errors) or 0}")
    print(f"over_utilised={len(neg)} sum={sum((r['calculate_balance'] for r in neg), Decimal(0))}")
    print(f"customs!=financial={len(diverge)} (expected where trades exist: financial carries billed term)")
    print(f"stored LicenseBalance: missing={sum(1 for r in rows if not r['stored'])} "
          f"duplicate={sum(1 for r in rows if '|' in r['stored'])} stale_vs_financial={len(stale)}")
    print(f"wrote {out_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
