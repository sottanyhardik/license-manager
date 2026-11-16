from decimal import Decimal

from django.test import SimpleTestCase

from apps.license.models import LicenseBalance


class LicenseBalanceNegativeTests(SimpleTestCase):
    def test_balance_cif_field_accepts_negative(self):
        field = LicenseBalance._meta.get_field("balance_cif")
        # Signed balances approved 2026-11-16; must not raise.
        field.clean(Decimal("-10.50"), None)
        self.assertEqual(field.validators and [v for v in field.validators if type(v).__name__ == "MinValueValidator"], [])
