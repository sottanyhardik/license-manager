"""
Unit tests for the ``reconcile_masters`` management command (ADR-001 Phase 0).

These are pure-Python tests: they fabricate multi-server ``audit_masters``-shaped
snapshots and drive the command's reconciliation logic directly (no database,
no file I/O beyond what ``handle`` optionally writes).  They assert that rows are
sorted into the correct buckets:

  - unique rows  (present on one server only)
  - a clean collision (same natural key, identical content hash)
  - a conflicting collision (same natural key, different content hash)
  - a keyless row (model with no natural key)
"""
import json
from pathlib import Path
import tempfile
from unittest import TestCase

from apps.core.management.commands.reconcile_masters import (
    Command,
    KEYLESS_MODELS,
    _parse_modified_on,
)


def _rec(key, rec_id, data_hash, modified_on=None, extra=None):
    """Build one audit record entry in the shape audit_masters emits."""
    data = {"id": rec_id}
    if modified_on is not None:
        data["modified_on"] = modified_on
    if extra:
        data.update(extra)
    return {"key": key, "id": rec_id, "data_hash": data_hash, "data": data}


def _table(key_field, records):
    return {"count": len(records), "key_field": key_field, "records": records}


def _snapshot(server_name, tables):
    return {
        "server_name": server_name,
        "generated_at": "2026-07-03T10:00:00",
        "tables": tables,
    }


class TestParseModifiedOn(TestCase):
    def test_parses_full_iso(self):
        dt = _parse_modified_on("2026-05-14T10:00:00")
        assert dt is not None and dt.year == 2026 and dt.hour == 10

    def test_parses_date_only(self):
        dt = _parse_modified_on("2026-05-14")
        assert dt is not None and dt.month == 5

    def test_none_for_empty(self):
        assert _parse_modified_on(None) is None
        assert _parse_modified_on("") is None

    def test_none_for_garbage(self):
        assert _parse_modified_on("not-a-date") is None


class TestReconcileModel(TestCase):
    """Drive _reconcile_model with fabricated per-server tables."""

    def setUp(self):
        self.cmd = Command()

    def test_unique_rows(self):
        """A key present on exactly one server lands in 'unique'."""
        per_server = {
            "s1": _table("iec", [_rec("AAA", 1, "hash-aaa", "2026-01-01T00:00:00")]),
            "s2": _table("iec", [_rec("BBB", 9, "hash-bbb", "2026-01-02T00:00:00")]),
        }
        section = self.cmd._reconcile_model("core.companymodel", per_server)

        unique_keys = {r["key"] for r in section["unique"]}
        assert unique_keys == {"AAA", "BBB"}
        assert section["agreed"] == []
        assert section["conflicts"] == []
        assert section["keyless"] == []

    def test_clean_collision_same_content(self):
        """Same key + identical hash on two servers => 'agreed', not conflict."""
        per_server = {
            "s1": _table("iec", [_rec("SAME", 1, "hash-x", "2026-01-01T00:00:00")]),
            "s2": _table("iec", [_rec("SAME", 42, "hash-x", "2026-02-01T00:00:00")]),
        }
        section = self.cmd._reconcile_model("core.companymodel", per_server)

        assert section["conflicts"] == []
        assert section["unique"] == []
        assert len(section["agreed"]) == 1
        agreed = section["agreed"][0]
        assert agreed["key"] == "SAME"
        assert sorted(agreed["servers"]) == ["s1", "s2"]
        assert agreed["data_hash"] == "hash-x"

    def test_conflicting_collision_different_content(self):
        """Same key + different hash => 'conflicts' (manual-review set)."""
        per_server = {
            "s1": _table("iec", [_rec("DUP", 1, "hash-A", "2026-01-01T00:00:00")]),
            "s2": _table("iec", [_rec("DUP", 7, "hash-B", "2026-06-01T00:00:00")]),
        }
        section = self.cmd._reconcile_model("core.companymodel", per_server)

        assert section["agreed"] == []
        assert len(section["conflicts"]) == 1
        conflict = section["conflicts"][0]
        assert conflict["key"] == "DUP"
        assert sorted(conflict["servers"]) == ["s1", "s2"]
        assert {v["data_hash"] for v in conflict["variants"]} == {"hash-A", "hash-B"}
        # Golden winner = newest modified_on => s2 (2026-06 > 2026-01).
        assert conflict["golden"]["winner_server"] == "s2"
        assert conflict["golden"]["basis"] == "newest_modified_on"
        assert conflict["golden"]["needs_manual_signoff"] is False

    def test_keyless_model_flagged(self):
        """Rows from a keyless model land only in 'keyless'."""
        assert "core.unitpricemodel" in KEYLESS_MODELS
        per_server = {
            "s1": _table(None, [_rec("id=1", 1, "hash-1"), _rec("id=2", 2, "hash-2")]),
            "s2": _table(None, [_rec("id=1", 1, "hash-9")]),
        }
        section = self.cmd._reconcile_model("core.unitpricemodel", per_server)

        assert section["is_keyless"] is True
        assert section["unique"] == []
        assert section["agreed"] == []
        assert section["conflicts"] == []
        assert len(section["keyless"]) == 3  # 2 from s1 + 1 from s2
        for row in section["keyless"]:
            assert "synthetic" in row["reason"]

    def test_conflict_without_timestamp_needs_signoff(self):
        """A content conflict with no timestamps cannot auto-pick a winner."""
        per_server = {
            "s1": _table("code", [_rec("P1", 1, "hash-A")]),
            "s2": _table("code", [_rec("P1", 2, "hash-B")]),
        }
        section = self.cmd._reconcile_model("core.portmodel", per_server)

        assert len(section["conflicts"]) == 1
        golden = section["conflicts"][0]["golden"]
        assert golden["needs_manual_signoff"] is True
        assert golden["basis"] == "no_timestamp_content_conflict"
        assert golden["winner_server"] is None

    def test_model_missing_on_one_server(self):
        """A model errored/absent on one server still reconciles the rest."""
        per_server = {
            "s1": _table("iec", [_rec("AAA", 1, "hash-aaa", "2026-01-01T00:00:00")]),
            "s2": {"error": "model not found"},
        }
        section = self.cmd._reconcile_model("core.companymodel", per_server)

        assert section["per_server_counts"]["s2"] == 0
        assert len(section["unique"]) == 1
        assert section["unique"][0]["key"] == "AAA"


class TestBuildReport(TestCase):
    """Full report assembly + totals across a fabricated 2-server universe."""

    def setUp(self):
        self.cmd = Command()
        self.snapshots = {
            "server1": _snapshot("license-manager", {
                "core.companymodel": _table("iec", [
                    _rec("UNIQUE1", 1, "h1", "2026-01-01T00:00:00"),   # unique
                    _rec("AGREE", 2, "hsame", "2026-01-01T00:00:00"),  # agreed
                    _rec("CONFLICT", 3, "hA", "2026-01-01T00:00:00"),  # conflict
                ]),
                "core.unitpricemodel": _table(None, [
                    _rec("id=1", 1, "up1"),  # keyless
                ]),
            }),
            "server2": _snapshot("labdhi", {
                "core.companymodel": _table("iec", [
                    _rec("UNIQUE2", 8, "h2", "2026-03-01T00:00:00"),   # unique
                    _rec("AGREE", 9, "hsame", "2026-05-01T00:00:00"),  # agreed
                    _rec("CONFLICT", 10, "hB", "2026-09-01T00:00:00"), # conflict (newer)
                ]),
                "core.unitpricemodel": _table(None, [
                    _rec("id=1", 1, "up9"),  # keyless
                ]),
            }),
        }

    def test_totals(self):
        report = self.cmd._build_report(self.snapshots)
        t = report["totals"]
        assert t["unique"] == 2      # UNIQUE1, UNIQUE2
        assert t["agreed"] == 1      # AGREE
        assert t["conflicts"] == 1   # CONFLICT
        assert t["keyless"] == 2     # one per server

    def test_conflict_golden_is_newest(self):
        report = self.cmd._build_report(self.snapshots)
        conflicts = report["models"]["core.companymodel"]["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["golden"]["winner_server"] == "server2"

    def test_servers_recorded(self):
        report = self.cmd._build_report(self.snapshots)
        assert set(report["servers"].keys()) == {"server1", "server2"}
        assert report["servers"]["server1"]["server_name"] == "license-manager"


class TestParseInputs(TestCase):
    def setUp(self):
        self.cmd = Command()

    def test_rejects_missing_equals(self):
        from django.core.management.base import CommandError
        try:
            self.cmd._parse_inputs(["justapath.json"])
            assert False, "expected CommandError"
        except CommandError:
            pass

    def test_rejects_empty(self):
        from django.core.management.base import CommandError
        try:
            self.cmd._parse_inputs([])
            assert False, "expected CommandError"
        except CommandError:
            pass

    def test_reads_valid_file_and_reconciles_end_to_end(self):
        """Write two real snapshot files, parse, build report, verify buckets."""
        snap1 = _snapshot("s1", {
            "core.companymodel": _table("iec", [
                _rec("K", 1, "hA", "2026-01-01T00:00:00"),
            ]),
        })
        snap2 = _snapshot("s2", {
            "core.companymodel": _table("iec", [
                _rec("K", 2, "hB", "2026-02-01T00:00:00"),
            ]),
        })
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            p1 = temp_dir / "s1.json"
            p2 = temp_dir / "s2.json"
            p1.write_text(json.dumps(snap1), encoding="utf-8")
            p2.write_text(json.dumps(snap2), encoding="utf-8")

            parsed = self.cmd._parse_inputs([f"s1={p1}", f"s2={p2}"])
            assert set(parsed.keys()) == {"s1", "s2"}

            report = self.cmd._build_report(parsed)
            assert report["totals"]["conflicts"] == 1
            golden = report["models"]["core.companymodel"]["conflicts"][0]["golden"]
            assert golden["winner_server"] == "s2"  # newer modified_on
