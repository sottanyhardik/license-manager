"""Migrations 0058 / 0059 / 0060 are additive and repeatable: backwards removes only their own
tables, forwards recreates them, and no pre-existing table is touched."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

NEW_TABLES = {"license_productmatchdecision", "license_productmatchingjob", "license_producttextembedding", "license_productmatchsuggestion",
              # 0060 product intelligence registry
              "license_productalias", "license_productinteldataset", "license_productintelmodel", "license_productintelauditevent",
              "license_productmatchselection", "license_mappingchange"}
LATEST = "0063_mapping_change_propagation"


class ProductMatchingMigrationRoundTripTests(TransactionTestCase):
    def _tables(self):
        return set(connection.introspection.table_names())

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("license", target)])

    def test_backwards_and_forwards_round_trip(self):
        before = self._tables()
        assert NEW_TABLES <= before
        try:
            self._migrate("0057_licensebalance_balance_cif_signed")
            after_back = self._tables()
            assert not (NEW_TABLES & after_back)
            assert after_back == before - NEW_TABLES  # nothing else removed or added
            self._migrate(LATEST)
            assert self._tables() == before
            self._migrate(LATEST)  # idempotent re-run
            assert self._tables() == before
        finally:
            self._migrate(LATEST)
