"""Compare two balance_baseline.py CSVs by licence id.

Usage: python3 scripts/dev/db_integrity/diff_baseline.py BEFORE.csv AFTER.csv [--cols a,b]
Exit 0 when every compared column matches for every licence present in both files,
1 otherwise. Added/removed licences are reported too. No Django or DB needed.
"""
from __future__ import annotations

import csv
import sys

DEFAULT_COLS = ["calculate_credit", "calculate_boe_debit_total", "calculate_debit",
                "calculate_allotment", "calculate_trade", "calculate_balance",
                "calculate_financial_balance"]


def load(path: str) -> dict[str, dict[str, str]]:
    with open(path, newline="") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--cols")]
    cols = DEFAULT_COLS
    for a in argv:
        if a.startswith("--cols="):
            cols = a.split("=", 1)[1].split(",")
    if len(args) != 2:
        sys.exit(__doc__)
    before, after = load(args[0]), load(args[1])
    only_b, only_a = sorted(before.keys() - after.keys()), sorted(after.keys() - before.keys())
    diffs = []
    for lid in sorted(before.keys() & after.keys(), key=int):
        for c in cols:
            if c in before[lid] and c in after[lid] and before[lid][c] != after[lid][c]:
                diffs.append((lid, before[lid].get("license_number"), c, before[lid][c], after[lid][c]))
    for d in diffs[:200]:
        print("DIFF id=%s lic=%s %s: %s -> %s" % d)
    print(f"compared={len(before.keys() & after.keys())} diffs={len(diffs)} "
          f"only_before={len(only_b)} only_after={len(only_a)}")
    return 1 if diffs or only_b or only_a else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
