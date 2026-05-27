"""
One-shot DB repair command.

Many FK constraints on the database still point to Django's legacy
`auth_user` table, even though the model definitions use
`settings.AUTH_USER_MODEL = "accounts.User"`. Users created via the custom
model (e.g. priyanka, ID 19) exist in `accounts_user` but not in
`auth_user`, so any save that tries to fill `modified_by`/`created_by`
fails with:

    insert or update on table "..." violates foreign key constraint
    "..._fk_auth_user"
    DETAIL:  Key (modified_by_id)=(19) is not present in table "auth_user".

This command:
  1. Discovers every FK constraint in the public schema that points to
     `auth_user` (or `accounts_user`).
  2. For each such constraint, NULLs out any row whose value is not present
     in the target `accounts_user` table (so we don't leave orphan rows).
  3. Drops the old constraint and recreates it pointing to `accounts_user`.

Idempotent — re-running on a healthy DB is a no-op.

Run with --dry-run first to preview.
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Repair FK constraints that still point to auth_user instead of accounts_user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making any DB modifications.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN — no DB changes will be made."))

        with connection.cursor() as cur:
            # Sanity: make sure accounts_user exists.
            cur.execute(
                "SELECT to_regclass('public.accounts_user'), to_regclass('public.auth_user')"
            )
            accounts_tbl, auth_tbl = cur.fetchone()
            if accounts_tbl is None:
                self.stderr.write(self.style.ERROR(
                    "accounts_user table not found. Aborting — check AUTH_USER_MODEL."
                ))
                return
            if auth_tbl is None:
                self.stdout.write("auth_user table not present — nothing to migrate.")
                return

            # Find every FK constraint pointing to auth_user.
            # Skip Django's internal junction tables for the legacy auth.User
            # (auth_user_groups, auth_user_user_permissions, auth_permission) —
            # those belong to the old model and shouldn't be repointed.
            cur.execute("""
                SELECT
                    pc.conname,
                    pc.conrelid::regclass::text AS source_table,
                    a.attname                  AS source_column
                FROM pg_constraint pc
                JOIN pg_attribute a
                  ON a.attrelid = pc.conrelid
                 AND a.attnum   = ANY (pc.conkey)
                WHERE pc.contype = 'f'
                  AND pc.confrelid::regclass::text = 'auth_user'
                  AND pc.conrelid::regclass::text NOT IN (
                      'auth_user_groups',
                      'auth_user_user_permissions'
                  )
                ORDER BY pc.conrelid::regclass::text, pc.conname
            """)
            constraints = cur.fetchall()
            if not constraints:
                self.stdout.write(self.style.SUCCESS(
                    "No FK constraints pointing to auth_user — nothing to do."
                ))
                return

            self.stdout.write(
                f"Found {len(constraints)} FK constraints pointing to auth_user.\n"
            )

            for conname, table, column in constraints:
                # Count orphan rows (FK value not in accounts_user)
                cur.execute(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE {column} IS NOT NULL "
                    f"  AND {column} NOT IN (SELECT id FROM accounts_user)"
                )
                orphans = cur.fetchone()[0]

                action = "would null" if dry else "nulling"
                if orphans:
                    self.stdout.write(
                        f"  {table}.{column}: {orphans} orphan(s) — {action} them"
                    )

                if dry:
                    # Show what the new constraint would look like.
                    self.stdout.write(
                        f"    would drop  {conname}\n"
                        f"    would add   FK {table}.{column} → accounts_user(id) ON DELETE SET NULL\n"
                    )
                    continue

                with transaction.atomic():
                    # 1. NULL orphan rows
                    if orphans:
                        cur.execute(
                            f"UPDATE {table} SET {column} = NULL "
                            f"WHERE {column} IS NOT NULL "
                            f"  AND {column} NOT IN (SELECT id FROM accounts_user)"
                        )

                    # 2. Drop the old constraint
                    cur.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{conname}"')

                    # 3. Add the new constraint pointing to accounts_user. Derive
                    # the new name from the OLD name so duplicates on the same
                    # column don't collide (some tables have two legacy FKs).
                    if "auth_user" in conname:
                        new_name = conname.replace("auth_user", "accounts_user")
                    else:
                        new_name = f"{conname}_acc"
                    new_name = new_name[:63]  # Postgres identifier cap

                    # If the chosen name is already taken (idempotent re-run or
                    # second-pass of a duplicate), suffix with column to disambiguate.
                    cur.execute(
                        "SELECT 1 FROM pg_constraint WHERE conname = %s",
                        [new_name],
                    )
                    if cur.fetchone():
                        new_name = f"{table[:30]}_{column}_fk_accounts_user"[:63]
                        # Last-resort: append a numeric suffix if still colliding
                        suffix = 1
                        base = new_name
                        while True:
                            cur.execute(
                                "SELECT 1 FROM pg_constraint WHERE conname = %s",
                                [new_name],
                            )
                            if not cur.fetchone():
                                break
                            new_name = f"{base[:60]}_{suffix}"
                            suffix += 1

                    cur.execute(
                        f'ALTER TABLE {table} '
                        f'ADD CONSTRAINT "{new_name}" '
                        f'FOREIGN KEY ({column}) REFERENCES accounts_user(id) '
                        f'ON DELETE SET NULL '
                        f'DEFERRABLE INITIALLY DEFERRED'
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"  {table}.{column}: re-pointed → accounts_user ({new_name})"
                    ))

        if dry:
            self.stdout.write(self.style.WARNING("\nDRY-RUN complete — no changes saved."))
        else:
            self.stdout.write(self.style.SUCCESS("\nFK constraint repair complete."))
