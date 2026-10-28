"""Regression: allotment create fails on legacy auth_user audit FKs and succeeds after repoint.

Production returned HTTP 500 on POST /api/allotments/ because created_by_id still
referenced the legacy auth_user table, which lacked the logged-in user's id. This
test restores that legacy constraint, reproduces the IntegrityError through the
public endpoint, then runs accounts migration 0006 and repeats the same request.
"""

import importlib

import pytest
from django.db import IntegrityError, connection, transaction
from django.urls import reverse

from apps.allotment.models import AllotmentModel

migration = importlib.import_module("apps.accounts.migrations.0006_repoint_legacy_user_fks")

LEGACY = "legacy_auth_user_allotment_test"


def _accounts_fk_names(table, column):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT con.conname FROM pg_constraint con "
            "JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1] "
            "WHERE con.contype = 'f' AND con.conrelid = %s::regclass AND a.attname = %s "
            "AND con.confrelid = 'accounts_user'::regclass",
            [table, column],
        )
        return [row[0] for row in cursor.fetchall()]


@pytest.fixture
def legacy_allotment_audit_fks(db):
    """Point allotment created_by / modified_by at an empty legacy table."""
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE TABLE {LEGACY} (id bigint PRIMARY KEY)")
        for column in ("created_by_id", "modified_by_id"):
            for name in _accounts_fk_names("allotment_allotmentmodel", column):
                cursor.execute(f"ALTER TABLE allotment_allotmentmodel DROP CONSTRAINT {name}")
            cursor.execute(
                f"ALTER TABLE allotment_allotmentmodel ADD CONSTRAINT legacy_{column} "
                f"FOREIGN KEY ({column}) REFERENCES {LEGACY} (id) DEFERRABLE INITIALLY DEFERRED"
            )


def test_allotment_create_succeeds_after_legacy_user_fks_are_repointed(
    authenticated_client, test_user, test_company, test_port, legacy_allotment_audit_fks
):
    url = reverse("allotment:allotment-list")
    payload = {
        "type": "AT",
        "company": test_company.pk,
        "port": test_port.pk,
        "item_name": "Alloy Steel",
        "required_quantity": "1926",
        "unit_value_per_unit": "41.311",
        "exchange_rate": "96.95",
    }

    with pytest.raises(IntegrityError, match="created_by_id"):
        with transaction.atomic():
            authenticated_client.post(url, payload, format="json")
            # The legacy FKs are DEFERRABLE INITIALLY DEFERRED, so production fails at commit.
            # Force the deferred check here so the test fails at the same point.
            connection.check_constraints()

    with connection.schema_editor() as schema_editor:
        migration.repoint_legacy_user_fks(schema_editor, legacy_table=LEGACY)

    response = authenticated_client.post(url, payload, format="json")

    assert response.status_code == 201, response.content
    allotment = AllotmentModel.objects.get(pk=response.json()["id"])
    assert allotment.created_by_id == test_user.pk
    assert allotment.item_name == "Alloy Steel"
    assert allotment.required_quantity == 1926
