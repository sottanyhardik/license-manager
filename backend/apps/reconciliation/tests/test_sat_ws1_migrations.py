"""SAT WS1 migrations reconciliation 0006 (action choices) and 0007
(ItemCifAdjustmentRecord) are additive and reversible: backwards to 0005 drops
only the new table, forwards recreates it, re-running is a no-op, and no other
table is touched."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

NEW_TABLE = "reconciliation_itemcifadjustmentrecord"
LATEST = "0007_item_cif_adjustment_record"


class WS1MigrationRoundTripTests(TransactionTestCase):
    def _tables(self):
        return set(connection.introspection.table_names())

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("reconciliation", target)])

    def _fk_constraints(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, NEW_TABLE)
        return [c for c in constraints.values() if c.get("foreign_key")]

    def test_backwards_and_forwards_round_trip(self):
        before = self._tables()
        assert NEW_TABLE in before
        try:
            self._migrate("0005_alter_reconciliationlog_action")
            after_back = self._tables()
            assert NEW_TABLE not in after_back
            assert after_back == before - {NEW_TABLE}
            self._migrate(LATEST)
            assert self._tables() == before
            self._migrate(LATEST)
            assert self._tables() == before
        finally:
            self._migrate(LATEST)

    def test_audit_fks_have_no_db_constraint(self):
        # Audit F4: the append-only log never blocks deleting a licence/item.
        fks = {c["foreign_key"][0] for c in self._fk_constraints()}
        assert not ({"license_licensedetailsmodel", "license_licenseimportitemsmodel"} & fks), fks
