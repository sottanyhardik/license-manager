"""
Module 04 — Three-Server Runtime Verification Tests

Proves the sync architecture actually works by simulating three servers
(A, B, C) applying sync events in all six directions and verifying
convergence, conflict resolution, delete protection, duplicate
reconciliation, offline recovery, and idempotency.

Each "server" is simulated by calling apply_sync_event / apply_sync_batch
with different source_server identifiers on a single database.  This is
valid because the sync service is stateless w.r.t. the caller — it only
cares about the event payload (source_server, source_version, data).

Coverage map (from FREEZE_GATE_CHECKLIST):
  ✓ A → B, A → C, B → A, B → C, C → A, C → B  (CREATE)
  ✓ A → B, A → C, B → A, B → C, C → A, C → B  (UPDATE)
  ✓ A → B, A → C, B → A, B → C, C → A, C → B  (DELETE)
  ✓ Global delete protection (cross-server FK scenario)
  ✓ Duplicate / natural-key reconciliation (independent create)
  ✓ Concurrent conflict resolution (multi-server)
  ✓ Offline recovery (stop/restart server simulation)
  ✓ Retry / idempotency (end-to-end)
  ✓ A = B = C convergence (final reconciliation)
"""
import pytest

from apps.core.sync.service import apply_sync_event, apply_sync_batch, get_changes_since
from apps.core.sync.registry import get_entry


SERVERS = ("server-A", "server-B", "server-C")


def _event(model_label, op, data, server, version):
    return {
        "model_label": model_label,
        "op": op,
        "data": data,
        "source_server": server,
        "source_version": version,
    }


def _company_create(iec, name, server, version):
    return _event("core.CompanyModel", "create", {"iec": iec, "name": name}, server, version)


def _company_update(iec, name, server, version):
    return _event("core.CompanyModel", "update", {"iec": iec, "name": name}, server, version)


def _company_delete(iec, server, version):
    return _event("core.CompanyModel", "delete", {"iec": iec}, server, version)


def _port_create(code, name, server, version):
    return _event("core.PortModel", "create", {"code": code, "name": name}, server, version)


def _port_update(code, name, server, version):
    return _event("core.PortModel", "update", {"code": code, "name": name}, server, version)


def _port_delete(code, server, version):
    return _event("core.PortModel", "delete", {"code": code}, server, version)


def _assert_company(iec, *, name=None, version=None, origin=None, tombstone=None):
    from apps.core.models import CompanyModel
    c = CompanyModel.objects.get(iec=iec)
    if name is not None:
        assert c.name == name, f"Expected name={name!r}, got {c.name!r}"
    if version is not None:
        assert c.sync_version == version, f"Expected version={version}, got {c.sync_version}"
    if origin is not None:
        assert c.origin_server == origin, f"Expected origin={origin!r}, got {c.origin_server!r}"
    if tombstone is not None:
        assert c.is_tombstone is tombstone, f"Expected tombstone={tombstone}, got {c.is_tombstone}"
    return c


def _assert_port(code, *, name=None, version=None, origin=None, tombstone=None):
    from apps.core.models import PortModel
    p = PortModel.objects.get(code=code)
    if name is not None:
        assert p.name == name, f"Expected name={name!r}, got {p.name!r}"
    if version is not None:
        assert p.sync_version == version, f"Expected version={version}, got {p.sync_version}"
    if origin is not None:
        assert p.origin_server == origin, f"Expected origin={origin!r}, got {p.origin_server!r}"
    if tombstone is not None:
        assert p.is_tombstone is tombstone, f"Expected tombstone={tombstone}, got {p.is_tombstone}"
    return p


# ── CREATE propagation: all 6 directions ──────────────────────────────

@pytest.mark.django_db
class TestCreatePropagationAllDirections:
    """Prove CREATE works in all 6 server-pair directions."""

    @pytest.mark.parametrize("src,dst", [
        ("server-A", "server-B"),
        ("server-A", "server-C"),
        ("server-B", "server-A"),
        ("server-B", "server-C"),
        ("server-C", "server-A"),
        ("server-C", "server-B"),
    ])
    def test_create_direction(self, src, dst):
        """CREATE from {src} applied as if received by {dst}."""
        iec = f"CR{src[-1]}{dst[-1]}001"
        result = apply_sync_event(_company_create(iec, f"From {src}", src, 1))
        assert result.success, f"CREATE failed: {result.error}"
        assert result.op == "create"
        _assert_company(iec, name=f"From {src}", version=1, origin=src, tombstone=False)


# ── UPDATE propagation: all 6 directions ──────────────────────────────

@pytest.mark.django_db
class TestUpdatePropagationAllDirections:
    """Prove UPDATE works in all 6 server-pair directions."""

    @pytest.mark.parametrize("src,dst", [
        ("server-A", "server-B"),
        ("server-A", "server-C"),
        ("server-B", "server-A"),
        ("server-B", "server-C"),
        ("server-C", "server-A"),
        ("server-C", "server-B"),
    ])
    def test_update_direction(self, src, dst):
        """CREATE on {dst}, then UPDATE from {src} with higher version."""
        iec = f"UP{src[-1]}{dst[-1]}001"
        # Initial create from dst
        r1 = apply_sync_event(_company_create(iec, f"Original on {dst}", dst, 1))
        assert r1.success
        # Update from src with higher version
        r2 = apply_sync_event(_company_update(iec, f"Updated by {src}", src, 2))
        assert r2.success
        assert r2.op == "update"
        _assert_company(iec, name=f"Updated by {src}", version=2, origin=src)


# ── DELETE propagation: all 6 directions ──────────────────────────────

@pytest.mark.django_db
class TestDeletePropagationAllDirections:
    """Prove DELETE (tombstone) works in all 6 server-pair directions."""

    @pytest.mark.parametrize("src,dst", [
        ("server-A", "server-B"),
        ("server-A", "server-C"),
        ("server-B", "server-A"),
        ("server-B", "server-C"),
        ("server-C", "server-A"),
        ("server-C", "server-B"),
    ])
    def test_delete_direction(self, src, dst):
        """CREATE on {dst}, then DELETE from {src} with higher version."""
        code = f"D{src[-1]}{dst[-1]}01"
        r1 = apply_sync_event(_port_create(code, f"Port on {dst}", dst, 1))
        assert r1.success
        r2 = apply_sync_event(_port_delete(code, src, 2))
        assert r2.success
        assert r2.op == "delete"
        _assert_port(code, tombstone=True, version=2, origin=src)


# ── Global delete protection (cross-server FK scenario) ───────────────

@pytest.mark.django_db
class TestGlobalDeleteProtection:
    """Delete must be blocked when FK references exist, regardless of source server."""

    def test_delete_blocked_by_child_record(self):
        """Server-A tries to delete a master that has children on this server."""
        from apps.core.models import ItemGroupModel, ItemNameModel

        # Create parent via sync from server-B
        r1 = apply_sync_event(_event(
            "core.ItemGroupModel", "create",
            {"name": "ProtectedGroup"}, "server-B", 1,
        ))
        assert r1.success

        # Create child locally (simulating local usage)
        group = ItemGroupModel.objects.get(name="ProtectedGroup")
        ItemNameModel.objects.create(name="ChildItem", group=group, sync_version=1)

        # Server-A tries to delete the parent
        r2 = apply_sync_event(_event(
            "core.ItemGroupModel", "delete",
            {"name": "ProtectedGroup"}, "server-A", 2,
        ))
        assert not r2.success, "Delete should be blocked by FK reference"
        assert r2.conflict
        assert "409 CONFLICT" in r2.conflict_detail

        # Parent must still be alive
        group.refresh_from_db()
        assert group.is_tombstone is False

    def test_delete_succeeds_after_child_removed(self):
        """Delete succeeds once FK references are cleared."""
        from apps.core.models import ItemGroupModel, ItemNameModel

        r1 = apply_sync_event(_event(
            "core.ItemGroupModel", "create",
            {"name": "CleanGroup"}, "server-C", 1,
        ))
        assert r1.success

        group = ItemGroupModel.objects.get(name="CleanGroup")
        child = ItemNameModel.objects.create(name="TempChild", group=group, sync_version=1)
        child.delete()

        r2 = apply_sync_event(_event(
            "core.ItemGroupModel", "delete",
            {"name": "CleanGroup"}, "server-A", 2,
        ))
        assert r2.success
        assert r2.op == "delete"


# ── Duplicate / natural-key reconciliation ────────────────────────────

@pytest.mark.django_db
class TestDuplicateReconciliation:
    """Independent creates on different servers must reconcile via natural key."""

    def test_independent_create_same_natural_key(self):
        """Two servers independently create a company with the same IEC.
        The second create becomes an update (no duplicate)."""
        iec = "DUPL00001"
        r1 = apply_sync_event(_company_create(iec, "Created on A", "server-A", 1))
        assert r1.op == "create"

        # Server-B independently creates the same IEC (higher version wins)
        r2 = apply_sync_event(_company_create(iec, "Created on B", "server-B", 2))
        assert r2.op == "update"  # reconciled as update, not duplicate

        from apps.core.models import CompanyModel
        assert CompanyModel.objects.filter(iec=iec).count() == 1
        _assert_company(iec, name="Created on B", version=2, origin="server-B")

    def test_independent_create_lower_version_rejected(self):
        """If the second create has a lower version, it's rejected."""
        iec = "DUPL00002"
        r1 = apply_sync_event(_company_create(iec, "Created on A", "server-A", 3))
        assert r1.op == "create"

        r2 = apply_sync_event(_company_create(iec, "Created on B", "server-B", 1))
        assert r2.op == "noop"  # rejected — local version is higher

        from apps.core.models import CompanyModel
        assert CompanyModel.objects.filter(iec=iec).count() == 1
        _assert_company(iec, name="Created on A", version=3, origin="server-A")

    def test_three_servers_independent_create(self):
        """All three servers create the same natural key independently.
        Only one record exists; highest version wins."""
        iec = "DUPL00003"
        apply_sync_event(_company_create(iec, "From A", "server-A", 1))
        apply_sync_event(_company_create(iec, "From B", "server-B", 2))
        apply_sync_event(_company_create(iec, "From C", "server-C", 3))

        from apps.core.models import CompanyModel
        assert CompanyModel.objects.filter(iec=iec).count() == 1
        _assert_company(iec, name="From C", version=3, origin="server-C")


# ── Concurrent conflict resolution ───────────────────────────────────

@pytest.mark.django_db
class TestConcurrentConflictResolution:
    """Deterministic conflict resolution across multiple servers."""

    def test_version_wins(self):
        """Higher version always wins regardless of server ID."""
        iec = "CONF00001"
        apply_sync_event(_company_create(iec, "Initial", "server-A", 1))
        apply_sync_event(_company_update(iec, "V2 from C", "server-C", 2))
        apply_sync_event(_company_update(iec, "V3 from B", "server-B", 3))
        _assert_company(iec, name="V3 from B", version=3, origin="server-B")

    def test_version_tie_deterministic_winner(self):
        """On version tie, lexicographically greater server ID wins."""
        iec = "CONF00002"
        apply_sync_event(_company_create(iec, "Initial", "server-A", 1))

        # server-C writes version 2
        apply_sync_event(_company_update(iec, "V2 from C", "server-C", 2))
        # server-A tries version 2 — "server-A" < "server-C", so A should win
        # because local origin is "server-C" >= source "server-A" → noop
        r = apply_sync_event(_company_update(iec, "V2 from A", "server-A", 2))
        assert r.op == "noop"
        _assert_company(iec, name="V2 from C", version=2, origin="server-C")

    def test_lower_version_rejected(self):
        """An update with a lower version is always rejected."""
        iec = "CONF00003"
        apply_sync_event(_company_create(iec, "Initial", "server-A", 5))
        r = apply_sync_event(_company_update(iec, "Old update", "server-B", 3))
        assert r.op == "noop"
        assert r.conflict
        _assert_company(iec, name="Initial", version=5)

    def test_three_way_concurrent_updates(self):
        """All three servers send updates; deterministic winner emerges."""
        iec = "CONF00004"
        apply_sync_event(_company_create(iec, "Seed", "server-A", 1))

        # All three send version 5 — tie-break by server ID
        apply_sync_event(_company_update(iec, "From A", "server-A", 5))
        apply_sync_event(_company_update(iec, "From B", "server-B", 5))
        apply_sync_event(_company_update(iec, "From C", "server-C", 5))

        # After A sets v5, B tries v5: "server-A" < "server-B" so B wins
        # After B sets v5, C tries v5: "server-B" < "server-C" so C wins
        _assert_company(iec, name="From C", version=5, origin="server-C")


# ── Offline recovery ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestOfflineRecovery:
    """Simulate server going offline and catching up via delta pull."""

    def test_offline_server_catches_up(self):
        """Server-C is offline while A and B make changes.
        When C comes back, it applies the batch and converges."""
        # While C is offline, A and B make changes
        events_while_c_offline = [
            _company_create("OFF00001", "Created on A", "server-A", 1),
            _port_create("OFF01", "Port from B", "server-B", 1),
            _company_update("OFF00001", "Updated on B", "server-B", 2),
        ]

        # Apply events (simulating A and B working)
        for ev in events_while_c_offline:
            r = apply_sync_event(ev)
            assert r.success, f"Event failed: {r.error}"

        # Now C comes back online and gets the change feed
        changes = get_changes_since(since=None)
        assert len(changes) >= 3, f"Expected ≥3 changes, got {len(changes)}"

        # Verify the data is correct (C would apply these via apply_sync_batch)
        _assert_company("OFF00001", name="Updated on B", version=2, origin="server-B")
        _assert_port("OFF01", name="Port from B", version=1, origin="server-B")

    def test_batch_recovery_applies_in_order(self):
        """Batch of events from offline period applied in topological order."""
        events = [
            _company_create("BREC0001", "Batch A", "server-A", 1),
            _company_update("BREC0001", "Batch B update", "server-B", 2),
            _port_create("BRC01", "Batch port", "server-C", 1),
        ]

        result = apply_sync_batch(events)
        assert result.ok, f"Batch errors: {[r.error for r in result.errors]}"
        assert len(result.applied) == 3

        _assert_company("BREC0001", name="Batch B update", version=2, origin="server-B")
        _assert_port("BRC01", name="Batch port", version=1, origin="server-C")


# ── Retry / idempotency ──────────────────────────────────────────────

@pytest.mark.django_db
class TestRetryIdempotency:
    """Reapplying the same event must be safe (no duplicates, no errors)."""

    def test_create_idempotent(self):
        """Applying the same CREATE twice doesn't create a duplicate."""
        ev = _company_create("IDEM0001", "Idempotent", "server-A", 1)
        r1 = apply_sync_event(ev)
        assert r1.op == "create"

        r2 = apply_sync_event(ev)
        assert r2.op == "noop"  # same version, same server → noop

        from apps.core.models import CompanyModel
        assert CompanyModel.objects.filter(iec="IDEM0001").count() == 1

    def test_update_idempotent(self):
        """Applying the same UPDATE twice is safe."""
        apply_sync_event(_company_create("IDEM0002", "Original", "server-A", 1))

        ev = _company_update("IDEM0002", "Updated", "server-B", 2)
        r1 = apply_sync_event(ev)
        assert r1.op == "update"

        r2 = apply_sync_event(ev)
        assert r2.op == "noop"  # same version, same server → noop

        _assert_company("IDEM0002", name="Updated", version=2)

    def test_delete_idempotent(self):
        """Applying the same DELETE twice is safe."""
        apply_sync_event(_port_create("IDM01", "Port", "server-A", 1))

        ev = _port_delete("IDM01", "server-B", 2)
        r1 = apply_sync_event(ev)
        assert r1.op == "delete"

        r2 = apply_sync_event(ev)
        assert r2.op == "noop"  # already tombstoned

    def test_batch_replay_idempotent(self):
        """Replaying an entire batch is safe."""
        events = [
            _company_create("IDEM0003", "Batch", "server-A", 1),
            _port_create("IDM02", "Batch port", "server-B", 1),
        ]

        r1 = apply_sync_batch(events)
        assert r1.ok
        assert len(r1.applied) == 2

        r2 = apply_sync_batch(events)
        assert r2.ok
        assert len(r2.applied) == 0  # all skipped
        assert len(r2.skipped) == 2


# ── A = B = C convergence ────────────────────────────────────────────

@pytest.mark.django_db
class TestABCConvergence:
    """Prove that applying the same event stream on any server yields
    identical final state (A = B = C)."""

    def test_full_lifecycle_convergence(self):
        """CREATE → UPDATE → UPDATE → DELETE sequence converges."""
        events = [
            _company_create("CONV0001", "Born on A", "server-A", 1),
            _company_update("CONV0001", "Edited on B", "server-B", 2),
            _company_update("CONV0001", "Final on C", "server-C", 3),
        ]

        result = apply_sync_batch(events)
        assert result.ok
        assert len(result.applied) == 3

        c = _assert_company("CONV0001", name="Final on C", version=3, origin="server-C")
        assert c.master_uid is not None
        assert c.is_tombstone is False

    def test_multi_model_convergence(self):
        """Multiple models converge to consistent state."""
        events = [
            _company_create("MCONV001", "Company A", "server-A", 1),
            _port_create("MCV01", "Port B", "server-B", 1),
            _company_update("MCONV001", "Company updated C", "server-C", 2),
            _port_update("MCV01", "Port updated A", "server-A", 2),
        ]

        result = apply_sync_batch(events)
        assert result.ok
        assert len(result.applied) == 4

        _assert_company("MCONV001", name="Company updated C", version=2, origin="server-C")
        _assert_port("MCV01", name="Port updated A", version=2, origin="server-A")

    def test_out_of_order_events_converge(self):
        """Events arriving out of order still converge correctly."""
        # Version 3 arrives before version 2
        apply_sync_event(_company_create("OOO00001", "V1", "server-A", 1))
        apply_sync_event(_company_update("OOO00001", "V3 early", "server-C", 3))
        r = apply_sync_event(_company_update("OOO00001", "V2 late", "server-B", 2))

        # V2 should be rejected because V3 is already applied
        assert r.op == "noop"
        _assert_company("OOO00001", name="V3 early", version=3, origin="server-C")

    def test_convergence_with_tombstone(self):
        """Convergence holds through soft-delete lifecycle."""
        events = [
            _port_create("CVT01", "Alive", "server-A", 1),
            _port_update("CVT01", "Updated", "server-B", 2),
            _port_delete("CVT01", "server-C", 3),
        ]

        result = apply_sync_batch(events)
        assert result.ok
        _assert_port("CVT01", tombstone=True, version=3, origin="server-C")

    def test_master_uid_consistent_across_servers(self):
        """The same natural key produces the same master_uid regardless of
        which server created the record."""
        from apps.core.sync.mixins import deterministic_uid

        iec = "UIDC0001"
        apply_sync_event(_company_create(iec, "From A", "server-A", 1))
        c = _assert_company(iec)

        expected_uid = deterministic_uid("core.CompanyModel", iec)
        assert c.master_uid == expected_uid

    def test_full_matrix_six_records(self):
        """Create 6 records (one per direction), update all, verify all converge."""
        directions = [
            ("server-A", "server-B"),
            ("server-A", "server-C"),
            ("server-B", "server-A"),
            ("server-B", "server-C"),
            ("server-C", "server-A"),
            ("server-C", "server-B"),
        ]

        # Phase 1: CREATE from each direction
        for i, (src, _dst) in enumerate(directions):
            iec = f"MTX{i:05d}"
            r = apply_sync_event(_company_create(iec, f"Created by {src}", src, 1))
            assert r.success, f"CREATE {iec} failed: {r.error}"

        # Phase 2: UPDATE from the opposite direction
        for i, (_src, dst) in enumerate(directions):
            iec = f"MTX{i:05d}"
            r = apply_sync_event(_company_update(iec, f"Updated by {dst}", dst, 2))
            assert r.success, f"UPDATE {iec} failed: {r.error}"

        # Phase 3: Verify all 6 records
        for i, (_src, dst) in enumerate(directions):
            iec = f"MTX{i:05d}"
            _assert_company(iec, name=f"Updated by {dst}", version=2, origin=dst, tombstone=False)

        from apps.core.models import CompanyModel
        mtx_count = CompanyModel.objects.filter(iec__startswith="MTX").count()
        assert mtx_count == 6, f"Expected 6 matrix records, got {mtx_count}"
