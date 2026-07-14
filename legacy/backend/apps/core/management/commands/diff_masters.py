"""
Compare master audit snapshots from multiple servers and produce a manual-review
plan showing what's missing, what conflicts, and what's identical.

Usage:
    python manage.py diff_masters \\
        --winner audit-license-manager.json \\
        --others audit-labdhi.json audit-tractor.json \\
        --out merge-plan.csv

Output: a CSV file you can review/edit before running the merge command.
Columns:
    table | key | status | winner_has | others_have | action
Status values:
    IDENTICAL    — same record everywhere, no action
    MISSING_ON_WINNER  — exists in other server(s) only, will be IMPORTED
    MISSING_ON_OTHER   — exists only on winner, will be PUSHED later
    CONFLICT     — same business key but different data, needs MANUAL REVIEW
"""
import csv
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Diff master audit snapshots from multiple servers and emit a merge plan"

    def add_arguments(self, parser):
        parser.add_argument("--winner", required=True, help="Path to winner server's audit JSON")
        parser.add_argument("--others", nargs="+", required=True, help="Paths to other servers' audit JSON")
        parser.add_argument("--out", default="merge-plan.csv", help="Output CSV path")

    def handle(self, *args, **opts):
        winner = json.load(open(opts["winner"]))
        others = [json.load(open(p)) for p in opts["others"]]

        rows = []
        # Iterate every table present in the winner snapshot
        for table_name, w_table in winner["tables"].items():
            if "error" in w_table:
                continue

            # Winner records indexed by business key
            w_by_key = {r["key"]: r for r in w_table["records"]}

            # All keys present on any "other" server
            other_keys = set()
            for o in others:
                o_table = o["tables"].get(table_name, {"records": []})
                for r in o_table.get("records", []):
                    other_keys.add(r["key"])

            # Every key seen anywhere
            all_keys = set(w_by_key.keys()) | other_keys

            for key in sorted(all_keys):
                w_rec = w_by_key.get(key)
                o_recs = []
                for o in others:
                    o_table = o["tables"].get(table_name, {"records": []})
                    for r in o_table.get("records", []):
                        if r["key"] == key:
                            o_recs.append((o["server_name"], r))

                if w_rec and o_recs:
                    # Compare hashes
                    other_hashes = {o["data_hash"] for _, o in o_recs}
                    if {w_rec["data_hash"]} == other_hashes:
                        status = "IDENTICAL"
                        action = "—"
                    else:
                        status = "CONFLICT"
                        action = "MANUAL_REVIEW"
                elif w_rec and not o_recs:
                    status = "MISSING_ON_OTHER"
                    action = "PUSH_TO_OTHERS"
                elif not w_rec and o_recs:
                    status = "MISSING_ON_WINNER"
                    action = "IMPORT_TO_WINNER"
                else:
                    continue

                rows.append({
                    "table": table_name,
                    "key": key,
                    "status": status,
                    "winner_has": "yes" if w_rec else "no",
                    "winner_id": w_rec["id"] if w_rec else "",
                    "others_have": ",".join(sn for sn, _ in o_recs) or "—",
                    "action": action,
                    "winner_hash": w_rec["data_hash"] if w_rec else "",
                    "other_hashes": "|".join(f"{sn}:{o['data_hash']}" for sn, o in o_recs),
                })

        # Write CSV
        with open(opts["out"], "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "table", "key", "status", "winner_has", "winner_id",
                "others_have", "action", "winner_hash", "other_hashes",
            ])
            writer.writeheader()
            writer.writerows(rows)

        # Print summary by table & status
        summary = {}
        for r in rows:
            t, s = r["table"], r["status"]
            summary.setdefault(t, {}).setdefault(s, 0)
            summary[t][s] += 1

        self.stdout.write(self.style.SUCCESS(f"\nWrote {len(rows)} rows to {opts['out']}\n"))
        self.stdout.write("Summary by table:")
        for t, sts in sorted(summary.items()):
            line = "  " + t.ljust(40)
            for s in ["IDENTICAL", "MISSING_ON_WINNER", "MISSING_ON_OTHER", "CONFLICT"]:
                line += f"  {s}={sts.get(s, 0):4d}"
            self.stdout.write(line)
