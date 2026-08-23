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


# ---------------------------------------------------------------------------
# Regression: the view SQL must filter on the codes actually stored in the
# column. `RowDetails.transaction_type` is max_length=2 and holds "C"/"D";
# the SQL previously compared against the words 'DEBIT'/'CREDIT', which can
# never be stored, so every JOIN/CASE matched zero rows and utilisation always
# read as 0 — silently inflating balance_cif and available_quantity.
# ---------------------------------------------------------------------------

_VIEW_SQL_WITH_TRANSACTION_TYPE = (
    materialized_views.LICENSE_BALANCE_VIEW,
    materialized_views.ITEM_BALANCE_VIEW,
)


@pytest.mark.parametrize("sql", _VIEW_SQL_WITH_TRANSACTION_TYPE)
def test_view_sql_never_compares_transaction_type_to_word_forms(sql):
    assert "'DEBIT'" not in sql
    assert "'CREDIT'" not in sql


@pytest.mark.parametrize("sql", _VIEW_SQL_WITH_TRANSACTION_TYPE)
def test_view_sql_uses_canonical_transaction_type_codes(sql):
    from apps.core.constants import CREDIT, DEBIT

    assert f"rd.transaction_type = '{DEBIT}'" in sql
    assert f"rd.transaction_type IN ('{DEBIT}', '{CREDIT}')" in sql


def test_canonical_codes_fit_the_transaction_type_column():
    """The codes the SQL filters on must be storable in the real column."""
    from apps.core.constants import CREDIT, DEBIT
    from apps.bill_of_entry.models import RowDetails

    field = RowDetails._meta.get_field("transaction_type")
    stored_codes = {choice[0] for choice in field.choices}

    assert {DEBIT, CREDIT} == stored_codes
    for code in (DEBIT, CREDIT):
        assert len(code) <= field.max_length
