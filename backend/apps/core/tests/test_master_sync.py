"""
Module 04 — Master Synchronization Tests

Covers:
- Registry completeness
- Deterministic master_uid
- Sync service (create/update/delete)
- Conflict resolution
- Duplicate reconciliation
- Delete protection
- Tombstone behavior
- Idempotent events
- Media sync tasks
- Offline recovery (delta pull)
- Batch ordering
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase, override_settings

from apps.core.sync.registry import (
    get_entry, get_all_entries, get_model_labels, get_media_entries,
    MASTER_SYNC_REGISTRY, MasterSyncEntry,
)
from apps.core.sync.mixins import deterministic_uid, MasterSyncMixin, media_sha256


# ── Registry tests ──────────────────────────────────────────────────────

class TestSyncRegistry(TestCase):
    """Verify the registry is complete and consistent."""

    def test_all_20_masters_registered(self):
        assert len(MASTER_SYNC_REGISTRY) == 20

    def test_all_labels_unique(self):
        labels = get_model_labels()
        assert len(labels) == len(set(labels))

    def test_get_entry_returns_correct(self):
        entry = get_entry("core.CompanyModel")
        assert entry is not None
        assert entry.natural_key == ("iec",)
        assert entry.media_fields == ("logo", "signature", "stamp")

    def test_get_entry_unknown_returns_none(self):
        assert get_entry("core.NonExistent") is None

    def test_media_entries(self):
        media = get_media_entries()
        labels = [e.model_label for e in media]
        assert "core.CompanyModel" in labels
        assert "core.InvoiceEntity" in labels
        assert "core.TransferLetterModel" in labels

    def test_topological_order(self):
        """Parents must appear before children in the registry."""
        label_order = {e.model_label: i for i, e in enumerate(get_all_entries())}
        for entry in get_all_entries():
            for dep in entry.fk_deps:
                assert label_order[dep] < label_order[entry.model_label], (
                    f"{entry.model_label} depends on {dep} but appears before it"
                )

    def test_all_entries_have_natural_key(self):
        for entry in get_all_entries():
            assert len(entry.natural_key) > 0, f"{entry.model_label} has empty natural_key"


# ── Deterministic UID tests ─────────────────────────────────────────────

class TestDeterministicUid(TestCase):
    """Verify UIDs are deterministic and collision-free."""

    def test_same_input_same_uid(self):
        uid1 = deterministic_uid("core.CompanyModel", "C001")
        uid2 = deterministic_uid("core.CompanyModel", "C001")
        assert uid1 == uid2

    def test_different_input_different_uid(self):
        uid1 = deterministic_uid("core.CompanyModel", "C001")
        uid2 = deterministic_uid("core.CompanyModel", "C002")
        assert uid1 != uid2

    def test_different_model_different_uid(self):
        uid1 = deterministic_uid("core.CompanyModel", "C001")
        uid2 = deterministic_uid("core.PortModel", "C001")
        assert uid1 != uid2

    def test_returns_uuid(self):
        uid = deterministic_uid("core.CompanyModel", "C001")
        assert isinstance(uid, uuid.UUID)

    def test_multi_part_key(self):
        uid1 = deterministic_uid("core.ProductDescriptionModel", "8501", "Motor")
        uid2 = deterministic_uid("core.ProductDescriptionModel", "8501", "Motor")
        assert uid1 == uid2

        uid3 = deterministic_uid("core.ProductDescriptionModel", "8501", "Generator")
        assert uid1 != uid3


# ── Model mixin tests ──────────────────────────────────────────────────

class TestMasterSyncMixinFields(TestCase):
    """Verify MasterSyncMixin adds the correct fields."""

    def test_company_has_sync_fields(self):
        from apps.core.models import CompanyModel
        field_names = [f.name for f in CompanyModel._meta.get_fields()]
        assert "master_uid" in field_names
        assert "sync_version" in field_names
        assert "is_tombstone" in field_names
        assert "origin_server" in field_names
        assert "synced_at" in field_names

    def test_port_has_sync_fields(self):
        from apps.core.models import PortModel
        field_names = [f.name for f in PortModel._meta.get_fields()]
        assert "master_uid" in field_names
        assert "sync_version" in field_names

    def test_all_masters_have_get_natural_key_values(self):
        """Every registered master model must implement get_natural_key_values."""
        from django.apps import apps
        for entry in get_all_entries():
            Model = apps.get_model(entry.model_label)
            assert hasattr(Model, "get_natural_key_values"), (
                f"{entry.model_label} missing get_natural_key_values()"
            )


# ── Sync service tests ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestSyncService:
    """Test the core sync service operations."""

    def test_create_company(self):
        from apps.core.sync.service import apply_create_or_update
        entry = get_entry("core.CompanyModel")
        result = apply_create_or_update(
            entry,
            {"iec": "TEST00001", "name": "Test Company"},
            source_server="server-A",
            source_version=1,
        )
        assert result.success
        assert result.op == "create"

        from apps.core.models import CompanyModel
        company = CompanyModel.objects.get(iec="TEST00001")
        assert company.name == "Test Company"
        assert company.sync_version == 1
        assert company.origin_server == "server-A"

    def test_update_company(self):
        from apps.core.models import CompanyModel
        CompanyModel.objects.create(
            iec="UPD000001", name="Original", sync_version=1, origin_server="server-A",
        )

        from apps.core.sync.service import apply_create_or_update
        entry = get_entry("core.CompanyModel")
        result = apply_create_or_update(
            entry,
            {"iec": "UPD000001", "name": "Updated"},
            source_server="server-B",
            source_version=2,
        )
        assert result.success
        assert result.op == "update"

        company = CompanyModel.objects.get(iec="UPD000001")
        assert company.name == "Updated"
        assert company.sync_version == 2

    def test_duplicate_reconciliation(self):
        """Creating a record with same NK should update, not duplicate."""
        from apps.core.models import CompanyModel
        CompanyModel.objects.create(iec="DUP000001", name="First")

        from apps.core.sync.service import apply_create_or_update
        entry = get_entry("core.CompanyModel")
        result = apply_create_or_update(
            entry,
            {"iec": "DUP000001", "name": "Second"},
            source_server="server-B",
            source_version=2,
        )
        assert result.op == "update"
        assert CompanyModel.objects.filter(iec="DUP000001").count() == 1
        assert CompanyModel.objects.get(iec="DUP000001").name == "Second"

    def test_conflict_higher_local_version(self):
        """Local version > source version → skip (noop)."""
        from apps.core.models import CompanyModel
        CompanyModel.objects.create(
            iec="CNF000001", name="Local", sync_version=5, origin_server="server-A",
        )

        from apps.core.sync.service import apply_create_or_update
        entry = get_entry("core.CompanyModel")
        result = apply_create_or_update(
            entry,
            {"iec": "CNF000001", "name": "Stale"},
            source_server="server-B",
            source_version=3,
        )
        assert result.op == "noop"
        assert result.conflict

        company = CompanyModel.objects.get(iec="CNF000001")
        assert company.name == "Local"  # unchanged

    def test_conflict_version_tie_deterministic(self):
        """Version tie → lexicographically greater server wins."""
        from apps.core.models import CompanyModel
        CompanyModel.objects.create(
            iec="TIE000001", name="ServerB", sync_version=3, origin_server="server-B",
        )

        from apps.core.sync.service import apply_create_or_update
        entry = get_entry("core.CompanyModel")

        # server-A < server-B → server-A should lose
        result = apply_create_or_update(
            entry,
            {"iec": "TIE000001", "name": "ServerA"},
            source_server="server-A",
            source_version=3,
        )
        assert result.op == "noop"
        assert result.conflict

    def test_idempotent_create(self):
        """Applying the same create twice should not fail or duplicate."""
        from apps.core.sync.service import apply_create_or_update
        entry = get_entry("core.PortModel")

        result1 = apply_create_or_update(
            entry, {"code": "IDEMP1", "name": "Port"}, "server-A", 1,
        )
        assert result1.op == "create"

        result2 = apply_create_or_update(
            entry, {"code": "IDEMP1", "name": "Port"}, "server-A", 1,
        )
        # Same version, same server → noop
        assert result2.op == "noop"

        from apps.core.models import PortModel
        assert PortModel.objects.filter(code="IDEMP1").count() == 1


# ── Delete protection tests ────────────────────────────────────────────

@pytest.mark.django_db
class TestDeleteProtection:
    """Test delete protection (FK reference checking)."""

    def test_delete_without_references(self):
        from apps.core.models import PortModel
        PortModel.objects.create(code="DEL001", name="Delete Me", sync_version=1)

        from apps.core.sync.service import apply_delete
        entry = get_entry("core.PortModel")
        result = apply_delete(
            entry, {"code": "DEL001"}, "server-A", source_version=2,
        )
        assert result.success
        assert result.op == "delete"

        port = PortModel.objects.get(code="DEL001")
        assert port.is_tombstone is True

    def test_delete_nonexistent_is_noop(self):
        from apps.core.sync.service import apply_delete
        entry = get_entry("core.PortModel")
        result = apply_delete(
            entry, {"code": "GHOST1"}, "server-A", source_version=1,
        )
        assert result.op == "noop"

    def test_delete_already_tombstoned_is_idempotent(self):
        from apps.core.models import PortModel
        PortModel.objects.create(
            code="TOMB01", name="Dead", sync_version=1, is_tombstone=True,
        )

        from apps.core.sync.service import apply_delete
        entry = get_entry("core.PortModel")
        result = apply_delete(
            entry, {"code": "TOMB01"}, "server-A", source_version=2,
        )
        assert result.op == "noop"

    def test_delete_blocked_by_fk_reference(self):
        """Delete must be rejected when FK references exist (409 CONFLICT)."""
        from apps.core.models import ItemGroupModel, ItemNameModel
        group = ItemGroupModel.objects.create(name="BlockGroup", sync_version=1)
        ItemNameModel.objects.create(
            name="BlockItem", group=group, sync_version=1,
        )

        from apps.core.sync.service import apply_delete
        entry = get_entry("core.ItemGroupModel")
        result = apply_delete(
            entry, {"name": "BlockGroup"}, "server-A", source_version=2,
        )
        assert not result.success
        assert result.conflict
        assert "409 CONFLICT" in result.conflict_detail


# ── Tombstone tests ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTombstone:
    """Test tombstone (soft-delete) behavior."""

    def test_tombstone_method(self):
        from apps.core.models import PortModel
        port = PortModel.objects.create(code="TST001", name="Test", sync_version=1)
        port.tombstone()
        port.refresh_from_db()
        assert port.is_tombstone is True
        assert port.sync_version == 2

    def test_is_alive(self):
        from apps.core.models import PortModel
        port = PortModel.objects.create(code="ALV001", name="Alive", sync_version=1)
        assert port.is_alive() is True
        port.is_tombstone = True
        assert port.is_alive() is False


# ── Batch sync tests ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestBatchSync:
    """Test batch sync operations."""

    def test_batch_creates_in_order(self):
        from apps.core.sync.service import apply_sync_batch

        events = [
            {
                "model_label": "core.PortModel",
                "op": "create",
                "data": {"code": "BAT001", "name": "Batch Port"},
                "source_server": "server-A",
                "source_version": 1,
            },
            {
                "model_label": "core.CompanyModel",
                "op": "create",
                "data": {"iec": "BAT000001", "name": "Batch Company"},
                "source_server": "server-A",
                "source_version": 1,
            },
        ]

        result = apply_sync_batch(events)
        assert result.ok
        assert len(result.applied) == 2

    def test_batch_with_error(self):
        from apps.core.sync.service import apply_sync_batch

        events = [
            {
                "model_label": "core.UnknownModel",
                "op": "create",
                "data": {},
                "source_server": "server-A",
                "source_version": 1,
            },
        ]

        result = apply_sync_batch(events)
        assert not result.ok
        assert len(result.errors) == 1


# ── Change feed tests ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestChangeFeed:
    """Test MasterChange records are created correctly."""

    def test_create_emits_change(self):
        from apps.core.sync.service import apply_create_or_update
        from apps.core.models import MasterChange

        entry = get_entry("core.PortModel")
        apply_create_or_update(
            entry, {"code": "CHG001", "name": "Change"}, "server-A", 1,
        )

        changes = MasterChange.objects.filter(
            model_label="core.PortModel", natural_key="CHG001",
        )
        assert changes.exists()
        assert changes.first().op == "create"

    def test_delete_emits_change(self):
        from apps.core.models import PortModel, MasterChange
        PortModel.objects.create(code="CHG002", name="Delete Me", sync_version=1)

        from apps.core.sync.service import apply_delete
        entry = get_entry("core.PortModel")
        apply_delete(entry, {"code": "CHG002"}, "server-A", 2)

        changes = MasterChange.objects.filter(
            model_label="core.PortModel", natural_key="CHG002", op="delete",
        )
        assert changes.exists()


# ── Delta pull tests ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestDeltaPull:
    """Test offline recovery via delta pull."""

    def test_get_changes_since_returns_events(self):
        from apps.core.models import PortModel, MasterChange
        PortModel.objects.create(code="PULL01", name="Pull Test", sync_version=1)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="PULL01", op="create",
        )

        from apps.core.sync.service import get_changes_since
        events = get_changes_since()
        port_events = [e for e in events if e["data"].get("code") == "PULL01"]
        assert len(port_events) >= 1

    def test_get_changes_since_with_timestamp(self):
        from apps.core.models import MasterChange
        from django.utils import timezone
        from datetime import timedelta

        future = (timezone.now() + timedelta(hours=1)).isoformat()
        events = get_changes_since_wrapper(future)
        assert len(events) == 0


def get_changes_since_wrapper(since):
    from apps.core.sync.service import get_changes_since
    return get_changes_since(since)


# ── Media sync tests ──────────────────────────────────────────────────

class TestMediaSync(TestCase):
    """Test media sync task creation and processing."""

    def test_media_sha256_empty_field(self):
        assert media_sha256(None) is None
        assert media_sha256("") is None

    @pytest.mark.django_db
    def test_create_media_tasks(self):
        from apps.core.sync.media import create_media_tasks

        tasks = create_media_tasks(
            "core.CompanyModel",
            "TEST001",
            {
                "logo": {"path": "companies/logos/test.png", "sha256": "abc123"},
                "signature": None,
            },
            "server-A",
        )
        assert len(tasks) == 1
        assert tasks[0].field_name == "logo"
        assert tasks[0].expected_sha256 == "abc123"

    @pytest.mark.django_db
    def test_create_media_tasks_idempotent(self):
        from apps.core.sync.media import create_media_tasks

        tasks1 = create_media_tasks(
            "core.CompanyModel", "TEST002",
            {"logo": {"path": "test.png", "sha256": "abc"}},
            "server-A",
        )
        tasks2 = create_media_tasks(
            "core.CompanyModel", "TEST002",
            {"logo": {"path": "test.png", "sha256": "abc"}},
            "server-A",
        )
        assert len(tasks1) == 1
        assert len(tasks2) == 0  # idempotent — no duplicate task


# ── Sync event tests ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestSyncEvent:
    """Test the apply_sync_event dispatcher."""

    def test_unknown_model_label(self):
        from apps.core.sync.service import apply_sync_event
        result = apply_sync_event({
            "model_label": "core.FakeModel",
            "op": "create",
            "data": {},
        })
        assert not result.success
        assert "Unknown" in result.error

    def test_unknown_op(self):
        from apps.core.sync.service import apply_sync_event
        result = apply_sync_event({
            "model_label": "core.PortModel",
            "op": "explode",
            "data": {"code": "X"},
        })
        assert not result.success
        assert "Unknown op" in result.error


# ── Three-server simulation ────────────────────────────────────────────

@pytest.mark.django_db
class TestThreeServerSync:
    """Simulate A→B, A→C, B→A, B→C, C→A, C→B sync directions."""

    def _create_event(self, iec, name, server, version):
        return {
            "model_label": "core.CompanyModel",
            "op": "create",
            "data": {"iec": iec, "name": name},
            "source_server": server,
            "source_version": version,
        }

    def _update_event(self, iec, name, server, version):
        return {
            "model_label": "core.CompanyModel",
            "op": "update",
            "data": {"iec": iec, "name": name},
            "source_server": server,
            "source_version": version,
        }

    def test_a_to_b_create(self):
        from apps.core.sync.service import apply_sync_event
        result = apply_sync_event(self._create_event("AB000001", "From A", "server-A", 1))
        assert result.op == "create"

    def test_b_to_a_create(self):
        from apps.core.sync.service import apply_sync_event
        result = apply_sync_event(self._create_event("BA000001", "From B", "server-B", 1))
        assert result.op == "create"

    def test_a_creates_b_updates(self):
        from apps.core.sync.service import apply_sync_event
        apply_sync_event(self._create_event("ABUP0001", "Original", "server-A", 1))
        result = apply_sync_event(self._update_event("ABUP0001", "Updated by B", "server-B", 2))
        assert result.op == "update"

        from apps.core.models import CompanyModel
        assert CompanyModel.objects.get(iec="ABUP0001").name == "Updated by B"

    def test_convergence_all_three(self):
        """All three servers applying same events converge to same state."""
        from apps.core.sync.service import apply_sync_batch

        events = [
            self._create_event("CONV0001", "Created on A", "server-A", 1),
            self._update_event("CONV0001", "Updated on B", "server-B", 2),
            self._update_event("CONV0001", "Final on C", "server-C", 3),
        ]

        result = apply_sync_batch(events)
        assert result.ok

        from apps.core.models import CompanyModel
        company = CompanyModel.objects.get(iec="CONV0001")
        assert company.name == "Final on C"
        assert company.sync_version == 3
        assert company.origin_server == "server-C"
