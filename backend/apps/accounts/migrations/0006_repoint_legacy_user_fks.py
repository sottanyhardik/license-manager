"""Re-point foreign keys that still reference the legacy auth_user table.

accounts.User (table accounts_user) is the swapped user model, but live
databases kept constraints created while auth.User was in use, so audit
columns still reference auth_user. Migration state already matches the
models, so makemigrations never regenerates these constraints.

Behaviour:
- Only constraints that currently reference auth_user are touched. Fresh
  databases have none, so the migration is a no-op there.
- Fail closed: the migration raises before any DDL when a referencing row
  holds an id missing from accounts_user, or when a legacy constraint has an
  unexpected ON UPDATE / ON DELETE action or is multi-column. The migration
  runs in one transaction, so nothing is partially applied.
- Each affected column ends with exactly one deferrable constraint on
  accounts_user(id). ON DELETE SET NULL is kept when a legacy duplicate had it,
  which preserves the deletion semantics the database already enforced.
- Reverse is a no-op: pointing back at auth_user would reintroduce the bug.

Locks: DROP CONSTRAINT takes ACCESS EXCLUSIVE on the referencing table, and
ADD CONSTRAINT takes SHARE ROW EXCLUSIVE on both tables. NOT VALID skips the
full scan while those locks are held; VALIDATE then only takes SHARE UPDATE
EXCLUSIVE on the referencing table. lock_timeout makes the migration fail
instead of queueing behind long-running transactions.
"""

import hashlib

from django.db import migrations

LEGACY_USER_TABLE = "auth_user"
USER_TABLE = "accounts_user"

# Legacy auth.User join tables keep their own FK, and these two upload tables
# have no model in this codebase.
SKIP_TABLES = frozenset({
    "auth_user_groups",
    "auth_user_user_permissions",
    "ebrc_fileuploaddetails",
    "shipping_bill_fileuploaddetails",
})

# pg_constraint action codes.
NO_ACTION = "a"
SET_NULL = "n"

FIND_LEGACY_FKS = """
    SELECT cl.relname, a.attname, con.conname, con.confdeltype, con.confupdtype,
           cardinality(con.conkey), a.attnotnull
    FROM pg_constraint con
    JOIN pg_class cl ON cl.oid = con.conrelid
    JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1]
    WHERE con.contype = 'f' AND con.confrelid = to_regclass(%s)
    ORDER BY cl.relname, a.attname, con.conname
"""


def _constraint_name(table, column):
    digest = hashlib.sha256(f"{table}.{column}".encode()).hexdigest()[:8]
    return f"{table[:30]}_{column[:12]}_{digest}_fk_acct"


def _fail(message):
    raise RuntimeError(f"Legacy auth_user FK repoint stopped before changing anything: {message}")


def repoint_legacy_user_fks(schema_editor, legacy_table=LEGACY_USER_TABLE, skip_tables=SKIP_TABLES):
    quote = schema_editor.quote_name
    schema_editor.execute("SET LOCAL lock_timeout = '10s'")

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(FIND_LEGACY_FKS, [legacy_table])
        found = [row for row in cursor.fetchall() if row[0] not in skip_tables]

    if not found:
        return

    problems = [
        f"{table}.{column} ({name}) on_delete={delete} on_update={update} columns={keys}"
        for table, column, name, delete, update, keys, _not_null in found
        if keys != 1 or update != NO_ACTION or delete not in (NO_ACTION, SET_NULL)
    ]
    if problems:
        _fail("unexpected legacy constraint actions: " + "; ".join(problems))

    columns = {}
    for table, column, _name, delete, _update, _keys, not_null in found:
        entry = columns.setdefault((table, column), {"not_null": not_null, "set_null": False})
        entry["set_null"] = entry["set_null"] or delete == SET_NULL

    unsatisfiable = [f"{t}.{c}" for (t, c), e in columns.items() if e["set_null"] and e["not_null"]]
    if unsatisfiable:
        _fail(f"ON DELETE SET NULL on NOT NULL columns: {unsatisfiable}")

    orphans = {}
    with schema_editor.connection.cursor() as cursor:
        for table, column in columns:
            cursor.execute(
                f"SELECT count(*) FROM {quote(table)} "
                f"WHERE {quote(column)} IS NOT NULL "
                f"AND {quote(column)} NOT IN (SELECT id FROM {quote(USER_TABLE)})"
            )
            count = cursor.fetchone()[0]
            if count:
                orphans[f"{table}.{column}"] = count
    if orphans:
        _fail(f"rows reference ids missing from {USER_TABLE}: {orphans}")

    for table, _column, name, *_rest in found:
        schema_editor.execute(f"ALTER TABLE {quote(table)} DROP CONSTRAINT {quote(name)}")

    for (table, column), entry in sorted(columns.items()):
        constraint = quote(_constraint_name(table, column))
        on_delete = " ON DELETE SET NULL" if entry["set_null"] else ""
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} ADD CONSTRAINT {constraint} "
            f"FOREIGN KEY ({quote(column)}) REFERENCES {quote(USER_TABLE)} (id){on_delete} "
            "DEFERRABLE INITIALLY DEFERRED NOT VALID"
        )
        schema_editor.execute(f"ALTER TABLE {quote(table)} VALIDATE CONSTRAINT {constraint}")


def _forward(apps, schema_editor):
    repoint_legacy_user_fks(schema_editor)


class Migration(migrations.Migration):

    dependencies = [("accounts", "0005_revokedaccesstoken")]

    operations = [
        migrations.RunPython(_forward, reverse_code=migrations.RunPython.noop),
    ]
