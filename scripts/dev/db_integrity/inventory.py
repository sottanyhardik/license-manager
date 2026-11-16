"""Structural DB inventory (read-only): server, table row counts, constraint and
index health, applied migrations per app.

Usage: backend/.venv/bin/python scripts/dev/db_integrity/inventory.py [OUT.txt]
Use the output as the before/after snapshot around any migration.
"""
from __future__ import annotations

import sys

from _common import read_only, setup


def main(out_path: str | None) -> int:
    setup()
    lines: list[str] = []
    with read_only() as conn, conn.cursor() as cur:
        cur.execute("select version(), current_database(), inet_server_addr()::text, "
                    "pg_size_pretty(pg_database_size(current_database())), pg_is_in_recovery()")
        lines.append(f"SERVER: {cur.fetchone()}")
        cur.execute("select contype, count(*), count(*) filter (where not convalidated) "
                    "from pg_constraint c join pg_namespace n on n.oid=c.connamespace "
                    "where n.nspname='public' group by 1 order by 1")
        lines.append(f"constraints (type,count,not_validated): {cur.fetchall()}")
        cur.execute("select count(*) from pg_index i join pg_class c on c.oid=i.indexrelid "
                    "join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and not i.indisvalid")
        lines.append(f"invalid indexes: {cur.fetchone()[0]}")
        cur.execute("select app, count(*) from django_migrations group by 1 order by 1")
        lines.append("migrations: " + ", ".join(f"{a}={n}" for a, n in cur.fetchall()))
        cur.execute("select tablename from pg_tables where schemaname='public' order by 1")
        tables = [t for (t,) in cur.fetchall()]
        total = 0
        lines.append(f"tables: {len(tables)}")
        for t in tables:
            cur.execute(f'select count(*) from "{t}"')  # names come from pg_catalog, quoted
            n = cur.fetchone()[0]
            total += n
            lines.append(f"  {t}\t{n}")
        lines.append(f"total rows: {total}")
    text = "\n".join(lines)
    if out_path:
        with open(out_path, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {out_path} (tables={len(tables)}, rows={total})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
