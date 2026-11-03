"""Unit tests for the canonical D-1 licence financial position (pure, no DB)."""

from datetime import datetime, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from apps.license.services.financial_position import calculate_financial_position

FIXED_TS = datetime(2026, 11, 2, tzinfo=timezone.utc)


def position(original, boe=0, allotment=0, billed=0, **kwargs):
    return calculate_financial_position(
        original_cif=original,
        boe_cif=boe,
        allotment_cif=allotment,
        billed_without_boe_cif=billed,
        calculated_at=FIXED_TS,
        **kwargs,
    )


class ApprovedExamplesTests(SimpleTestCase):
    """D-1 section 3.2 and 3.3 worked examples."""

    def test_example_3_2_all_categories_leave_available_35_lakh(self):
        p = position("10000000", boe="3500000", allotment="2000000", billed="1000000")
        self.assertEqual(p.utilised_cif, Decimal("6500000.00"))
        self.assertEqual(p.available_cif, Decimal("3500000.00"))
        self.assertFalse(p.is_over_utilised)
        self.assertEqual(p.over_utilisation_cif, Decimal("0.00"))
        self.assertEqual(p.utilisation_pct, Decimal("65.00"))

    def test_example_3_3_over_utilisation_is_negative_not_floored(self):
        p = position("10000000", boe="8000000", allotment="2500000", billed="1000000")
        self.assertEqual(p.utilised_cif, Decimal("11500000.00"))
        self.assertEqual(p.available_cif, Decimal("-1500000.00"))
        self.assertTrue(p.is_over_utilised)
        self.assertEqual(p.over_utilisation_cif, Decimal("1500000.00"))
        self.assertEqual(p.utilisation_pct, Decimal("115.00"))


class CategoryCombinationTests(SimpleTestCase):
    def test_no_utilisation_leaves_full_original(self):
        p = position("100.00")
        self.assertEqual(p.utilised_cif, Decimal("0.00"))
        self.assertEqual(p.available_cif, Decimal("100.00"))
        self.assertEqual(p.utilisation_pct, Decimal("0.00"))

    def test_boe_only(self):
        p = position("100", boe="30")
        self.assertEqual((p.utilised_cif, p.available_cif), (Decimal("30.00"), Decimal("70.00")))

    def test_allotment_only(self):
        p = position("100", allotment="25")
        self.assertEqual((p.utilised_cif, p.available_cif), (Decimal("25.00"), Decimal("75.00")))

    def test_billed_without_boe_only(self):
        p = position("100", billed="10")
        self.assertEqual((p.utilised_cif, p.available_cif), (Decimal("10.00"), Decimal("90.00")))

    def test_boe_and_allotment(self):
        p = position("100", boe="30", allotment="20")
        self.assertEqual(p.available_cif, Decimal("50.00"))

    def test_boe_and_billed(self):
        p = position("100", boe="30", billed="10")
        self.assertEqual(p.available_cif, Decimal("60.00"))

    def test_fully_utilised_is_zero_available_not_over(self):
        p = position("100", boe="60", allotment="30", billed="10")
        self.assertEqual(p.available_cif, Decimal("0.00"))
        self.assertFalse(p.is_over_utilised)
        self.assertEqual(p.utilisation_pct, Decimal("100.00"))

    def test_multiple_categories_are_summed_exactly(self):
        p = position("1000.00", boe="0.10", allotment="0.20", billed="0.30")
        self.assertEqual(p.utilised_cif, Decimal("0.60"))
        self.assertEqual(p.available_cif, Decimal("999.40"))


class DoubleCountingInvariantTests(SimpleTestCase):
    """Conversions must move CIF between categories without changing utilisation."""

    def test_partial_allotment_to_boe_conversion_keeps_total_utilisation(self):
        before = position("100", allotment="20")
        # 12 of the 20 is now represented by a BOE; 8 stays as reservation (D-1 s3.4).
        after = position("100", boe="12", allotment="8")
        self.assertEqual(before.utilised_cif, after.utilised_cif)
        self.assertEqual(before.available_cif, after.available_cif)

    def test_full_allotment_to_boe_conversion_keeps_total_utilisation(self):
        before = position("100", allotment="20")
        after = position("100", boe="20")
        self.assertEqual(before.utilised_cif, after.utilised_cif)

    def test_invoice_moving_from_billed_to_boe_keeps_total_utilisation(self):
        before = position("100", billed="10")
        after = position("100", boe="10")
        self.assertEqual(before.utilised_cif, after.utilised_cif)

    def test_partial_allotment_cancellation_releases_only_the_cancelled_part(self):
        before = position("100", allotment="20")
        after = position("100", allotment="5")
        self.assertEqual(after.available_cif - before.available_cif, Decimal("15.00"))

    def test_full_allotment_cancellation_restores_available(self):
        p = position("100", allotment="0")
        self.assertEqual(p.available_cif, Decimal("100.00"))

    def test_reversal_returns_identical_position(self):
        original_inputs = dict(original_cif="100", boe_cif="30", allotment_cif="20", billed_without_boe_cif="10")
        first = calculate_financial_position(**original_inputs, calculated_at=FIXED_TS)
        second = calculate_financial_position(**original_inputs, calculated_at=FIXED_TS)
        self.assertEqual(first, second)


class OverUtilisationTests(SimpleTestCase):
    def test_negative_available_is_never_hidden(self):
        p = position("100", boe="150")
        self.assertEqual(p.available_cif, Decimal("-50.00"))
        self.assertTrue(p.is_over_utilised)

    def test_exactly_at_limit_is_not_over_utilised(self):
        self.assertFalse(position("100", boe="100").is_over_utilised)

    def test_one_paisa_over_is_over_utilised(self):
        p = position("100", boe="100.01")
        self.assertTrue(p.is_over_utilised)
        self.assertEqual(p.over_utilisation_cif, Decimal("0.01"))

    def test_zero_original_has_no_percentage(self):
        p = position("0", boe="5")
        self.assertIsNone(p.utilisation_pct)
        self.assertTrue(p.is_over_utilised)


class PrecisionTests(SimpleTestCase):
    def test_decimal_inputs_avoid_binary_float_error(self):
        p = position("0.30", boe="0.10", allotment="0.20")
        self.assertEqual(p.available_cif, Decimal("0.00"))

    def test_half_up_rounding_on_output(self):
        # 10.00 - 1.005 = 8.995, which rounds half-up to 9.00.
        p = position("10.00", boe="1.005")
        self.assertEqual(p.available_cif, Decimal("9.00"))

    def test_outputs_are_quantized_to_two_places(self):
        p = position("100", boe="33.333")
        self.assertEqual(p.utilised_cif, Decimal("33.33"))
        self.assertEqual(p.available_cif, Decimal("66.67"))

    def test_large_values_keep_precision(self):
        p = position("1234567890123.45", boe="0.01")
        self.assertEqual(p.available_cif, Decimal("1234567890123.44"))


class InputValidationTests(SimpleTestCase):
    def test_float_is_rejected(self):
        with self.assertRaises(TypeError):
            position(100.0)

    def test_bool_is_rejected(self):
        with self.assertRaises(TypeError):
            position(True)

    def test_non_numeric_string_is_rejected(self):
        with self.assertRaises(ValueError):
            position("abc")

    def test_nan_and_infinity_are_rejected(self):
        with self.assertRaises(ValueError):
            position("NaN")
        with self.assertRaises(ValueError):
            position("Infinity")

    def test_negative_category_is_rejected(self):
        with self.assertRaises(ValueError):
            position("100", boe="-1")

    def test_blank_currency_is_rejected(self):
        with self.assertRaises(ValueError):
            position("100", currency="  ")


class MetadataTests(SimpleTestCase):
    def test_currency_is_carried_without_conversion(self):
        p = position("100", boe="10", currency="USD")
        self.assertEqual(p.currency, "USD")
        self.assertEqual(p.available_cif, Decimal("90.00"))

    def test_reconciliation_warnings_are_returned(self):
        p = position("100", reconciliation_warnings=("allotment residue unmatched",))
        self.assertEqual(p.reconciliation_warnings, ("allotment residue unmatched",))

    def test_default_timestamp_is_timezone_aware(self):
        p = calculate_financial_position(
            original_cif="1", boe_cif="0", allotment_cif="0", billed_without_boe_cif="0"
        )
        self.assertIsNotNone(p.calculated_at.tzinfo)


class Licence2583ScenarioTests(SimpleTestCase):
    """Pure arithmetic for licence 2583 (0311054433) as verified from source records.

    Inputs come from the read-only audit in
    docs/09-module-implementation/licence-2583-financial-forensic-audit.md.
    Amounts are USD (FC). Billed-without-BOE uses sales with no BOE link
    (9,560.00 + 400,000.00), whose INR basis is unverified (see business questions).
    """

    ORIGINAL = "615999.98"
    BOE_INCLUDING_HIDDEN = "204526.37"  # 182,856.60 non-hidden + 21,669.77 hidden BOE 27622
    BOE_NON_HIDDEN = "182856.60"
    BILLED_WITHOUT_BOE = "409560.00"

    def test_hidden_boe_counted_as_boe_gives_engine_balance(self):
        p = position(self.ORIGINAL, boe=self.BOE_INCLUDING_HIDDEN, billed=self.BILLED_WITHOUT_BOE)
        self.assertEqual(p.utilised_cif, Decimal("614086.37"))
        self.assertEqual(p.available_cif, Decimal("1913.61"))

    def test_hidden_boe_excluded_gives_higher_balance(self):
        p = position(self.ORIGINAL, boe=self.BOE_NON_HIDDEN, billed=self.BILLED_WITHOUT_BOE)
        self.assertEqual(p.available_cif, Decimal("23583.38"))

    def test_engine_balance_equals_customs_minus_billed_without_boe(self):
        # Customs ledger 411,473.61 = original - all BOEs (incl. hidden); the billed
        # category is the only term the customs view omits.
        customs = Decimal("411473.61")
        p = position(self.ORIGINAL, boe=self.BOE_INCLUDING_HIDDEN, billed=self.BILLED_WITHOUT_BOE)
        self.assertEqual(customs - Decimal(self.BILLED_WITHOUT_BOE), p.available_cif)
