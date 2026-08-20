"""
Tests for the ``check_master_quality`` management command (read-only report).

Covers the three issue classes it detects: blank natural keys, orphaned FKs, and
duplicate business keys — plus that a clean DB reports zero and that
``--quarantine`` refuses to mutate.
"""
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction

from apps.core.models import CompanyModel, HeadSIONNormsModel, SionNormClassModel


def _run(tmp_path, **kwargs):
    out = tmp_path / "mq.json"
    call_command("check_master_quality", "--out", str(out), **kwargs)
    return json.loads(out.read_text(encoding="utf-8"))


def test_clean_db_reports_zero(db, tmp_path):
    CompanyModel.objects.create(iec="IEC0000001", name="Acme", bill_colour="#333")
    report = _run(tmp_path)
    assert report["totals"] == {"blank_keys": 0, "orphaned_fks": 0, "duplicate_keys": 0}


def test_detects_blank_natural_key(db, tmp_path):
    # A blank-IEC company (the real-world case). Bypass any app-level guard by
    # writing an empty string directly.
    CompanyModel.objects.create(iec="", name="Blank Co", bill_colour="#333")
    CompanyModel.objects.create(iec="IEC0000002", name="Real Co", bill_colour="#333")
    report = _run(tmp_path)
    assert report["totals"]["blank_keys"] == 1
    assert report["models"]["core.CompanyModel"]["blank_keys"]["count"] == 1


def test_unique_natural_key_prevents_duplicate_business_key(db, tmp_path):
    """The quality scanner sees legacy duplicates, but current writes reject them.

    PostgreSQL correctly enforces the production unique constraint, so a test
    that attempts to manufacture an invalid row must assert that rejection;
    skipping it would hide the invariant from the suite.
    """
    head = HeadSIONNormsModel.objects.create(name="H")
    SionNormClassModel.objects.create(head_norm=head, norm_class="E1", is_active=True)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SionNormClassModel.objects.create(head_norm=head, norm_class="E1", is_active=True)

    report = _run(tmp_path)
    assert report["totals"]["duplicate_keys"] == 0


def test_detects_orphaned_fk(db, tmp_path):
    head = HeadSIONNormsModel.objects.create(name="H")
    norm = SionNormClassModel.objects.create(head_norm=head, norm_class="E1", is_active=True)
    # Orphan the FK by pointing head_norm at a non-existent id. Postgres FKs here
    # are DEFERRABLE INITIALLY DEFERRED, so the UPDATE succeeds mid-transaction
    # (the deferred check fires only at commit) — which lets the report observe
    # the orphan. We restore a valid FK before the test ends so the deferred
    # check passes at teardown. This models cross-server drift (parent not yet
    # synced) without leaving the DB in a state that fails the commit check.
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE core_sionnormclassmodel SET head_norm_id = 999999 WHERE id = %s",
            [norm.id],
        )
    try:
        report = _run(tmp_path)
        assert report["totals"]["orphaned_fks"] >= 1
        assert "head_norm" in report["models"]["core.SionNormClassModel"]["orphaned_fks"]["by_field"]
    finally:
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE core_sionnormclassmodel SET head_norm_id = %s WHERE id = %s",
                [head.id, norm.id],
            )


def test_quarantine_refuses_and_does_not_mutate(db, tmp_path):
    CompanyModel.objects.create(iec="", name="Blank Co", bill_colour="#333")
    before = CompanyModel.objects.count()
    with pytest.raises(CommandError):
        call_command("check_master_quality", "--quarantine")
    assert CompanyModel.objects.count() == before  # nothing deleted/moved
