"""
Repoint stale FKs on legacy license tables from auth_user → accounts_user.

Background
----------
Settings now declares ``AUTH_USER_MODEL = "accounts.User"`` and every license
migration writes its user FKs against ``settings.AUTH_USER_MODEL``. On
databases originally created BEFORE the switch, however, the physical FK
constraints on the older tables still reference the legacy ``auth_user``
table from Django's default user model. Inserting a license therefore
fails with:

    IntegrityError: insert or update on table "license_licensedetailsmodel"
    violates foreign key constraint "..._fk_auth_user"
    DETAIL: Key (created_by_id)=(21) is not present in table "auth_user".

…even though user 21 exists in ``accounts_user`` (where login actually
authenticates them).

Affected constraints observed on the source environment:

    license_licensedetailsmodel.created_by_id  → auth_user(id)
    license_licensedetailsmodel.modified_by_id → auth_user(id)
    license_licensepurchase.created_by_id      → auth_user(id)
    license_licensepurchase.modified_by_id     → auth_user(id)

(The newer ``license_incentivelicense`` and ``license_licensetransfermodel``
FKs were created after the AUTH_USER_MODEL switch and already point to
``accounts_user`` — they are skipped automatically by the lookup below.)

This migration is idempotent: each block only rewrites a constraint when
it is currently pointing at ``auth_user``. On databases where the FK
already targets ``accounts_user`` (or where ``auth_user`` no longer exists),
every block is a no-op.
"""
from django.db import migrations


# (table, column) pairs whose user FKs need repointing if still on auth_user.
_FK_TARGETS = [
    ("license_licensedetailsmodel", "created_by_id"),
    ("license_licensedetailsmodel", "modified_by_id"),
    ("license_licensepurchase", "created_by_id"),
    ("license_licensepurchase", "modified_by_id"),
]


def _repoint_sql(table: str, column: str) -> str:
    """Build a self-healing DO block that repoints a single FK."""
    new_constraint = f"{table}_{column}_fk_accounts_user"
    return f"""
DO $$
DECLARE
    bad_constraint TEXT;
BEGIN
    -- If the legacy auth_user table no longer exists, there is nothing to fix.
    IF to_regclass('auth_user') IS NULL THEN
        RETURN;
    END IF;

    SELECT c.conname INTO bad_constraint
    FROM pg_constraint c
    JOIN pg_class t        ON t.oid = c.conrelid
    JOIN pg_attribute a    ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
    WHERE c.contype = 'f'
      AND t.relname = '{table}'
      AND a.attname = '{column}'
      AND c.confrelid = 'auth_user'::regclass;

    IF bad_constraint IS NOT NULL THEN
        EXECUTE format(
            'ALTER TABLE {table} DROP CONSTRAINT %I',
            bad_constraint
        );
        ALTER TABLE {table}
            ADD CONSTRAINT {new_constraint}
            FOREIGN KEY ({column}) REFERENCES accounts_user(id)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("license", "0007_drop_obsolete_subtable_columns"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[_repoint_sql(table, column) for table, column in _FK_TARGETS],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
