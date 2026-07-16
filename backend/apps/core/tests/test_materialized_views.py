import pytest

from apps.core import materialized_views


class FakeCursor:
    def __init__(self, rows=None, description=None):
        self.executed = []
        self._rows = rows or []
        self.description = description or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def test_refresh_materialized_view_rejects_unknown_view_before_sql(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(materialized_views, "connection", FakeConnection(cursor))

    with pytest.raises(ValueError, match="Unknown materialized view"):
        materialized_views.refresh_materialized_view("license_balance_mv; DROP TABLE users")

    assert cursor.executed == []


def test_refresh_materialized_view_uses_allowlisted_identifier(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(materialized_views, "connection", FakeConnection(cursor))

    materialized_views.refresh_materialized_view("license_balance_mv", concurrently=True)

    assert cursor.executed == [
        ("REFRESH MATERIALIZED VIEW CONCURRENTLY license_balance_mv", None),
    ]


def test_get_materialized_view_stats_uses_pg_stat_rel_columns(monkeypatch):
    cursor = FakeCursor(
        rows=[("public", "license_balance_mv", "16 kB", 1, 2, 3, None, None)],
        description=[
            ("schemaname",),
            ("view_name",),
            ("size",),
            ("rows_inserted",),
            ("rows_updated",),
            ("rows_deleted",),
            ("last_autovacuum",),
            ("last_autoanalyze",),
        ],
    )
    monkeypatch.setattr(materialized_views, "connection", FakeConnection(cursor))

    stats = materialized_views.get_materialized_view_stats()

    executed_sql = cursor.executed[0][0]
    assert "relname as view_name" in executed_sql
    assert "pg_total_relation_size(relid)" in executed_sql
    assert stats == [
        {
            "schemaname": "public",
            "view_name": "license_balance_mv",
            "size": "16 kB",
            "rows_inserted": 1,
            "rows_updated": 2,
            "rows_deleted": 3,
            "last_autovacuum": None,
            "last_autoanalyze": None,
        }
    ]
