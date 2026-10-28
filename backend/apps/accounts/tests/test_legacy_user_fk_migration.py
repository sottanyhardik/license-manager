"""Behaviour of accounts migration 0006 (legacy auth_user foreign keys).

Fresh test databases never contain the legacy constraints, so each test builds
a minimal legacy schema inside its own transaction and then runs the
migration helper against it.
"""

import importlib

import pytest
from django.db import connection, transaction

migration = importlib.import_module("apps.accounts.migrations.0006_repoint_legacy_user_fks")

LEGACY = "legacy_auth_user_fk_test"
CHILD = "legacy_user_fk_child_test"


@pytest.fixture
def legacy_schema(db):
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE TABLE {LEGACY} (id bigint PRIMARY KEY)")
        cursor.execute(
            f"CREATE TABLE {CHILD} "
            "(id bigserial PRIMARY KEY, created_by_id bigint NULL, modified_by_id bigint NULL)"
        )
        # Duplicate pair on created_by_id: a deferrable plain FK and an ON DELETE SET NULL FK.
        cursor.execute(
            f"ALTER TABLE {CHILD} ADD CONSTRAINT child_created_plain FOREIGN KEY (created_by_id) "
            f"REFERENCES {LEGACY} (id) DEFERRABLE INITIALLY DEFERRED"
        )
        cursor.execute(
            f"ALTER TABLE {CHILD} ADD CONSTRAINT child_created_set_null FOREIGN KEY (created_by_id) "
            f"REFERENCES {LEGACY} (id) ON DELETE SET NULL"
        )
        cursor.execute(
            f"ALTER TABLE {CHILD} ADD CONSTRAINT child_modified_plain FOREIGN KEY (modified_by_id) "
            f"REFERENCES {LEGACY} (id) DEFERRABLE INITIALLY DEFERRED"
        )


def _run(**kwargs):
    with connection.schema_editor() as schema_editor:
        migration.repoint_legacy_user_fks(schema_editor, **kwargs)


def _constraints(table, column):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT con.conname, pg_get_constraintdef(con.oid) "
            "FROM pg_constraint con "
            "JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1] "
            "WHERE con.contype = 'f' AND con.conrelid = %s::regclass AND a.attname = %s "
            "ORDER BY con.conname",
            [table, column],
        )
        return cursor.fetchall()


def test_documented_exclusions_are_the_four_legacy_tables():
    assert migration.SKIP_TABLES == {
        "auth_user_groups",
        "auth_user_user_permissions",
        "ebrc_fileuploaddetails",
        "shipping_bill_fileuploaddetails",
    }


def test_fresh_schema_without_legacy_constraints_is_a_no_op(db):
    _run()


def test_repoints_each_column_to_accounts_user_with_exactly_one_constraint(legacy_schema):
    _run(legacy_table=LEGACY)

    created = _constraints(CHILD, "created_by_id")
    assert len(created) == 1
    _, definition = created[0]
    assert "REFERENCES accounts_user(id)" in definition
    assert "ON DELETE SET NULL" in definition
    assert "DEFERRABLE INITIALLY DEFERRED" in definition
    assert "NOT VALID" not in definition

    modified = _constraints(CHILD, "modified_by_id")
    assert len(modified) == 1
    _, definition = modified[0]
    assert "REFERENCES accounts_user(id)" in definition
    assert "ON DELETE" not in definition
    assert "DEFERRABLE INITIALLY DEFERRED" in definition
    assert "NOT VALID" not in definition


def test_is_idempotent(legacy_schema):
    _run(legacy_table=LEGACY)
    before = _constraints(CHILD, "created_by_id") + _constraints(CHILD, "modified_by_id")

    _run(legacy_table=LEGACY)

    assert _constraints(CHILD, "created_by_id") + _constraints(CHILD, "modified_by_id") == before


def test_orphaned_ids_stop_the_migration_without_changing_the_schema(legacy_schema):
    with connection.cursor() as cursor:
        cursor.execute(f"INSERT INTO {LEGACY} (id) VALUES (999)")
        cursor.execute(f"INSERT INTO {CHILD} (created_by_id) VALUES (999)")
    before = _constraints(CHILD, "created_by_id")

    with pytest.raises(RuntimeError, match="missing from accounts_user"):
        with transaction.atomic():
            _run(legacy_table=LEGACY)

    assert _constraints(CHILD, "created_by_id") == before
    assert all(LEGACY in definition for _, definition in before)


def test_unexpected_delete_action_stops_the_migration(legacy_schema):
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {CHILD} ADD CONSTRAINT child_modified_cascade FOREIGN KEY (modified_by_id) "
            f"REFERENCES {LEGACY} (id) ON DELETE CASCADE"
        )
    before = _constraints(CHILD, "modified_by_id")

    with pytest.raises(RuntimeError, match="unexpected legacy constraint actions"):
        with transaction.atomic():
            _run(legacy_table=LEGACY)

    assert _constraints(CHILD, "modified_by_id") == before


def test_set_null_on_a_not_null_column_stops_the_migration(legacy_schema):
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {CHILD} ALTER COLUMN created_by_id SET NOT NULL")
    before = _constraints(CHILD, "created_by_id")

    with pytest.raises(RuntimeError, match="ON DELETE SET NULL on NOT NULL columns"):
        with transaction.atomic():
            _run(legacy_table=LEGACY)

    assert _constraints(CHILD, "created_by_id") == before


def test_skipped_tables_keep_their_legacy_constraints(legacy_schema):
    before = _constraints(CHILD, "created_by_id") + _constraints(CHILD, "modified_by_id")

    _run(legacy_table=LEGACY, skip_tables={CHILD})

    assert _constraints(CHILD, "created_by_id") + _constraints(CHILD, "modified_by_id") == before
