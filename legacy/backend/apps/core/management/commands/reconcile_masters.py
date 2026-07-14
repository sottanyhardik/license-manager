"""
Master Data Reconciliation — ADR-001 Phase 0 (Decision 6, step 1 & 2).

Consumes the per-server JSON snapshots produced by ``audit_masters`` (one per
server: license-manager @ .201, labdhi, tractor) and produces a reconciliation
report that classifies every master row into decision buckets *before* any
cutover.  This is pure analysis: it reads JSON files and emits a JSON report.
**It never touches a database and never writes to any master table.**

Usage::

    # 1. On each server (see audit_masters):
    python manage.py audit_masters --out audit-201.json --server-name license-manager
    python manage.py audit_masters --out audit-labdhi.json --server-name labdhi
    python manage.py audit_masters --out audit-tractor.json --server-name tractor

    # 2. Locally, feed all snapshots to the reconciler:
    python manage.py reconcile_masters \
        --input license-manager=audit-201.json \
        --input labdhi=audit-labdhi.json \
        --input tractor=audit-tractor.json \
        --out reconciliation-report.json

Report buckets (per master model):
  - ``unique``    : rows present on exactly one server (by natural key).
  - ``agreed``    : same natural key on >1 server, identical content hash
                    (a clean collision — safe auto-merge, no manual review).
  - ``conflicts`` : same natural key on >1 server, DIFFERENT content hash
                    (the manual-review set — genuine divergence).
  - ``keyless``   : rows from models with no natural key (HeadSIONNormsModel,
                    SIONExportModel, SIONImportModel, SionNormNote,
                    SionNormCondition, ProductDescriptionModel, UnitPriceModel,
                    TransferLetterModel) — flagged for synthetic-key assignment.

For each natural key that appears on any server, a proposed "golden" winner is
computed: newest ``modified_on`` where available, else flagged
``needs_manual_signoff`` (the timestamp-less models cannot be auto-decided).

The command mutates nothing.  Its only side effects are writing the report file
(``--out``) and printing a human-readable summary to stdout.
"""
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

# Models that have NO natural (business) key — they must be assigned a synthetic
# stable key before they can participate in a keyed sync (ADR-001 Decision 6,
# step 3).  Their audit "key" is a per-server ``id=<pk>`` placeholder that is
# NOT portable across servers, so we never key-match them; we only enumerate
# them for the synthetic-key assignment task.
KEYLESS_MODELS = {
    "core.headsionnormsmodel",
    "core.sionexportmodel",
    "core.sionimportmodel",
    "core.sionnormnote",
    "core.sionnormcondition",
    "core.productdescriptionmodel",
    "core.unitpricemodel",
    "core.transferlettermodel",
}


def _parse_modified_on(value):
    """Best-effort parse of an ISO ``modified_on`` string into a datetime.

    ``audit_masters`` serializes datetimes via ``.isoformat()``.  Returns None
    when the field is missing/empty/unparseable so the caller can fall back to
    manual sign-off rather than silently picking a wrong winner.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # Handles both "2026-05-14T10:00:00" and date-only "2026-05-14".
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = (
        "Reconcile per-server audit_masters JSON snapshots into a "
        "unique/agreed/conflict/keyless report with proposed golden winners "
        "(read-only; no DB writes)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            action="append",
            default=[],
            metavar="SERVER=PATH",
            help=(
                "A server-labelled audit JSON file, e.g. "
                "--input labdhi=audit-labdhi.json. Repeat for each server."
            ),
        )
        parser.add_argument(
            "--out",
            default=None,
            help="Write the JSON reconciliation report to this file (default: stdout report is summary-only).",
        )

    # ── input parsing ────────────────────────────────────────────────────────
    def _parse_inputs(self, raw_inputs):
        """Turn ``["labdhi=path", ...]`` into ``{label: snapshot_dict}``.

        Fails loudly on bad syntax, missing files, duplicate labels, and
        malformed JSON — a silently-skipped server would corrupt the whole
        reconciliation, which is the opposite of what Phase 0 needs.
        """
        if not raw_inputs:
            raise CommandError(
                "No --input given. Provide at least one SERVER=PATH "
                "(two or more servers are needed for a meaningful diff)."
            )
        snapshots = {}
        for item in raw_inputs:
            if "=" not in item:
                raise CommandError(
                    f"Bad --input '{item}'. Expected SERVER=PATH "
                    f"(e.g. --input labdhi=audit-labdhi.json)."
                )
            label, path = item.split("=", 1)
            label = label.strip()
            path = path.strip()
            if not label or not path:
                raise CommandError(f"Bad --input '{item}': empty server label or path.")
            if label in snapshots:
                raise CommandError(f"Duplicate server label '{label}' in --input.")
            if not os.path.isfile(path):
                raise CommandError(f"Input file not found for server '{label}': {path}")
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                raise CommandError(f"Could not read/parse JSON for server '{label}' ({path}): {exc}")
            if not isinstance(data, dict) or "tables" not in data:
                raise CommandError(
                    f"File for server '{label}' ({path}) is not an audit_masters "
                    f"snapshot (missing top-level 'tables')."
                )
            snapshots[label] = data
        if len(snapshots) < 2:
            self.stdout.write(self.style.WARNING(
                "Only one server supplied — every row will be reported as 'unique'. "
                "Reconciliation is only meaningful with 2+ servers."
            ))
        return snapshots

    # ── core reconciliation ──────────────────────────────────────────────────
    def _reconcile_model(self, label, per_server_table):
        """Reconcile a single master model across servers.

        ``per_server_table`` maps ``server_label -> table_dict`` where each
        table_dict is the ``audit_masters`` entry
        ``{"count", "key_field", "records": [...]}`` for this model on that
        server.  Returns the per-model report section.
        """
        is_keyless = label in KEYLESS_MODELS

        # key_field is reported by audit_masters and is consistent across servers
        # for the same model; grab the first non-error one we see.
        key_field = None
        for tbl in per_server_table.values():
            if isinstance(tbl, dict) and tbl.get("key_field"):
                key_field = tbl["key_field"]
                break

        section = {
            "key_field": key_field,
            "is_keyless": is_keyless,
            "per_server_counts": {},
            "unique": [],
            "agreed": [],
            "conflicts": [],
            "keyless": [],
        }

        # Group every record by its natural key across servers.
        # by_key: natural_key -> list of {server, id, data_hash, modified_on, record}
        by_key = {}
        for server, tbl in per_server_table.items():
            if not isinstance(tbl, dict) or "records" not in tbl:
                # Model missing/errored on this server — record a 0 and skip.
                section["per_server_counts"][server] = 0
                continue
            records = tbl.get("records") or []
            section["per_server_counts"][server] = len(records)

            for rec in records:
                entry = {
                    "server": server,
                    "id": rec.get("id"),
                    "data_hash": rec.get("data_hash"),
                    "modified_on": (rec.get("data") or {}).get("modified_on"),
                    "key": rec.get("key"),
                }
                if is_keyless:
                    # No portable key — enumerate for synthetic-key assignment.
                    section["keyless"].append({
                        "server": server,
                        "id": rec.get("id"),
                        "data_hash": rec.get("data_hash"),
                        "reason": "no natural key; needs synthetic stable key (ADR-001 Decision 6.3)",
                    })
                    continue
                natural_key = rec.get("key")
                by_key.setdefault(natural_key, []).append(entry)

        if is_keyless:
            # Keyless models produce no unique/agreed/conflict buckets — only the
            # keyless list above. Sort for deterministic output.
            section["keyless"].sort(key=lambda e: (e["server"], str(e["id"])))
            return section

        for natural_key, entries in by_key.items():
            servers = sorted({e["server"] for e in entries})
            hashes = {e["data_hash"] for e in entries}
            golden = self._propose_golden(entries)

            if len(servers) == 1:
                section["unique"].append({
                    "key": natural_key,
                    "server": servers[0],
                    "data_hash": entries[0]["data_hash"],
                    "golden": golden,
                })
            elif len(hashes) == 1:
                # Same key, identical content on all servers => clean merge.
                section["agreed"].append({
                    "key": natural_key,
                    "servers": servers,
                    "data_hash": next(iter(hashes)),
                    "golden": golden,
                })
            else:
                # Same key, divergent content => manual-review set.
                section["conflicts"].append({
                    "key": natural_key,
                    "servers": servers,
                    "variants": [
                        {
                            "server": e["server"],
                            "id": e["id"],
                            "data_hash": e["data_hash"],
                            "modified_on": e["modified_on"],
                        }
                        for e in sorted(entries, key=lambda e: e["server"])
                    ],
                    "golden": golden,
                })

        # Deterministic ordering for stable diffs / signoff.
        section["unique"].sort(key=lambda e: str(e["key"]))
        section["agreed"].sort(key=lambda e: str(e["key"]))
        section["conflicts"].sort(key=lambda e: str(e["key"]))
        return section

    def _propose_golden(self, entries):
        """Propose the golden winner for one natural key.

        Rule (ADR-001 Decision 6.2): newest ``modified_on`` wins.  When no entry
        carries a parseable ``modified_on`` (the timestamp-less masters), we do
        NOT guess — we flag ``needs_manual_signoff`` so a human decides.
        Single-server keys are auto-won by that server but still carry the
        timestamp basis so the audit trail is explicit.
        """
        dated = [
            (e, _parse_modified_on(e["modified_on"]))
            for e in entries
        ]
        dated_with_ts = [(e, ts) for e, ts in dated if ts is not None]

        if not dated_with_ts:
            # No timestamps anywhere for this key.
            if len({e["data_hash"] for e in entries}) == 1:
                # Content agrees, so the value is unambiguous even without a ts.
                winner = sorted(entries, key=lambda e: e["server"])[0]
                return {
                    "winner_server": winner["server"],
                    "winner_id": winner["id"],
                    "basis": "content_identical_no_timestamp",
                    "needs_manual_signoff": False,
                }
            return {
                "winner_server": None,
                "winner_id": None,
                "basis": "no_timestamp_content_conflict",
                "needs_manual_signoff": True,
            }

        # Pick newest modified_on; tie-break deterministically by server label.
        winner_entry, winner_ts = max(
            dated_with_ts, key=lambda pair: (pair[1], pair[0]["server"])
        )
        return {
            "winner_server": winner_entry["server"],
            "winner_id": winner_entry["id"],
            "winner_modified_on": winner_entry["modified_on"],
            "basis": "newest_modified_on",
            "needs_manual_signoff": False,
        }

    def _build_report(self, snapshots):
        """Assemble the full cross-model reconciliation report."""
        # Union of every model label seen across all snapshots.
        model_labels = set()
        for snap in snapshots.values():
            model_labels.update((snap.get("tables") or {}).keys())

        report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "servers": {
                label: {
                    "server_name": snap.get("server_name"),
                    "generated_at": snap.get("generated_at"),
                }
                for label, snap in snapshots.items()
            },
            "models": {},
            "totals": {
                "unique": 0,
                "agreed": 0,
                "conflicts": 0,
                "keyless": 0,
                "needs_manual_signoff": 0,
            },
        }

        for label in sorted(model_labels):
            per_server_table = {
                server: (snap.get("tables") or {}).get(label)
                for server, snap in snapshots.items()
                if (snap.get("tables") or {}).get(label) is not None
            }
            section = self._reconcile_model(label, per_server_table)
            report["models"][label] = section

            report["totals"]["unique"] += len(section["unique"])
            report["totals"]["agreed"] += len(section["agreed"])
            report["totals"]["conflicts"] += len(section["conflicts"])
            report["totals"]["keyless"] += len(section["keyless"])
            report["totals"]["needs_manual_signoff"] += sum(
                1
                for bucket in ("unique", "agreed", "conflicts")
                for row in section[bucket]
                if row.get("golden", {}).get("needs_manual_signoff")
            )

        return report

    # ── stdout summary ────────────────────────────────────────────────────────
    def _print_summary(self, report):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Master reconciliation summary (ADR-001 Phase 0)"))
        servers = ", ".join(report["servers"].keys())
        self.stdout.write(f"  Servers reconciled: {servers}")
        self.stdout.write("")

        header = f"  {'model':<32} {'unique':>7} {'agreed':>7} {'conflict':>9} {'keyless':>8}"
        self.stdout.write(header)
        self.stdout.write(f"  {'-' * 66}")
        for label, section in report["models"].items():
            self.stdout.write(
                f"  {label:<32} "
                f"{len(section['unique']):>7} "
                f"{len(section['agreed']):>7} "
                f"{len(section['conflicts']):>9} "
                f"{len(section['keyless']):>8}"
            )
        t = report["totals"]
        self.stdout.write(f"  {'-' * 66}")
        self.stdout.write(
            f"  {'TOTAL':<32} {t['unique']:>7} {t['agreed']:>7} "
            f"{t['conflicts']:>9} {t['keyless']:>8}"
        )
        self.stdout.write("")

        if t["conflicts"]:
            self.stdout.write(self.style.WARNING(
                f"  {t['conflicts']} natural-key CONFLICT(S) need manual review "
                f"(same key, divergent content)."
            ))
        if t["keyless"]:
            self.stdout.write(self.style.WARNING(
                f"  {t['keyless']} keyless row(s) need synthetic-key assignment "
                f"(Decision 6.3)."
            ))
        if t["needs_manual_signoff"]:
            self.stdout.write(self.style.WARNING(
                f"  {t['needs_manual_signoff']} golden winner(s) need manual sign-off "
                f"(no timestamp to auto-decide)."
            ))
        if not (t["conflicts"] or t["keyless"] or t["needs_manual_signoff"]):
            self.stdout.write(self.style.SUCCESS(
                "  No conflicts, no keyless rows, no manual sign-off needed — clean reconciliation."
            ))
        self.stdout.write("")

    # ── entrypoint ────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        snapshots = self._parse_inputs(opts.get("input") or [])
        report = self._build_report(snapshots)

        out_path = opts.get("out")
        if out_path:
            try:
                with open(out_path, "w") as f:
                    json.dump(report, f, indent=2, default=str)
            except OSError as exc:
                raise CommandError(f"Could not write report to {out_path}: {exc}")
            self.stdout.write(self.style.SUCCESS(f"Wrote reconciliation report to {out_path}"))

        self._print_summary(report)
