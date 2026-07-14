"""
Tests for the Trade module -- precision-critical arithmetic.

The 3-decimal-place precision for pct/rate_pct is a business-critical
hotfix requirement: pct=7.925 must yield 7925.00, not 7930.00.
"""
from decimal import Decimal

import pytest


@pytest.fixture
def patch_managed(monkeypatch):
    """Allow managed=False models to use the test DB."""
    from apps.trade import models as trade_models
    for model in [
        trade_models.LicenseTrade,
        trade_models.LicenseTradeLine,
        trade_models.IncentiveTradeLine,
        trade_models.LicenseTradePayment,
    ]:
        model._meta.managed = True
    yield
    for model in [
        trade_models.LicenseTrade,
        trade_models.LicenseTradeLine,
        trade_models.IncentiveTradeLine,
        trade_models.LicenseTradePayment,
    ]:
        model._meta.managed = False


# -- Unit tests for compute_amount (no DB needed) --

class TestLicenseTradeLinePrecision:
    """Critical precision tests -- pct must use 3dp, never rounded to 2dp first."""

    def _make_line(self, mode, **kwargs):
        from apps.trade.models import LicenseTradeLine
        line = LicenseTradeLine.__new__(LicenseTradeLine)
        # Set all defaults
        line.mode = mode
        line.qty_kg = Decimal("0")
        line.rate_inr_per_kg = Decimal("0")
        line.cif_inr = Decimal("0")
        line.fob_inr = Decimal("0")
        line.pct = Decimal("0")
        line.cif_fc = Decimal("0")
        line.exc_rate = Decimal("0")
        for k, v in kwargs.items():
            setattr(line, k, v)
        return line

    def test_pct_3dp_precision_cif(self):
        """pct=7.925, cif=100000 -> 7925.00 (NOT 7930.00 from wrong rounding)."""
        line = self._make_line("CIF_INR", pct=Decimal("7.925"), cif_inr=Decimal("100000.00"))
        result = line.compute_amount()
        assert result == Decimal("7925.00"), f"Expected 7925.00, got {result}"

    def test_pct_3dp_precision_fob(self):
        """pct=7.925, fob=100000 -> 7925.00."""
        line = self._make_line("FOB_INR", pct=Decimal("7.925"), fob_inr=Decimal("100000.00"))
        result = line.compute_amount()
        assert result == Decimal("7925.00"), f"Expected 7925.00, got {result}"

    def test_billing_mode_qty(self):
        """qty=100.5000, rate=250.00 -> 25125.00."""
        line = self._make_line("QTY", qty_kg=Decimal("100.5000"), rate_inr_per_kg=Decimal("250.00"))
        result = line.compute_amount()
        assert result == Decimal("25125.00"), f"Expected 25125.00, got {result}"

    def test_billing_mode_cif_inr(self):
        """pct=10.000, cif=500000 -> 50000.00."""
        line = self._make_line("CIF_INR", pct=Decimal("10.000"), cif_inr=Decimal("500000.00"))
        result = line.compute_amount()
        assert result == Decimal("50000.00")

    def test_billing_mode_fob_inr(self):
        """pct=5.500, fob=200000 -> 11000.00."""
        line = self._make_line("FOB_INR", pct=Decimal("5.500"), fob_inr=Decimal("200000.00"))
        result = line.compute_amount()
        assert result == Decimal("11000.00")

    def test_zero_pct_returns_zero(self):
        line = self._make_line("CIF_INR", pct=Decimal("0"), cif_inr=Decimal("100000.00"))
        assert line.compute_amount() == Decimal("0.00")

    def test_none_pct_treated_as_zero(self):
        line = self._make_line("CIF_INR", cif_inr=Decimal("100000.00"))
        line.pct = None
        assert line.compute_amount() == Decimal("0.00")


class TestIncentiveTradeLinePrecision:
    """Critical precision tests for IncentiveTradeLine rate_pct."""

    def _make_line(self, **kwargs):
        from apps.trade.models import IncentiveTradeLine
        line = IncentiveTradeLine.__new__(IncentiveTradeLine)
        line.license_value = Decimal("0")
        line.rate_pct = Decimal("0")
        for k, v in kwargs.items():
            setattr(line, k, v)
        return line

    def test_rate_pct_3dp_precision(self):
        """rate_pct=2.125, license_value=500000 -> 10625.00."""
        line = self._make_line(rate_pct=Decimal("2.125"), license_value=Decimal("500000.00"))
        result = line.compute_amount()
        assert result == Decimal("10625.00"), f"Expected 10625.00, got {result}"

    def test_rate_pct_round_number(self):
        """rate_pct=5.000, license_value=100000 -> 5000.00."""
        line = self._make_line(rate_pct=Decimal("5.000"), license_value=Decimal("100000.00"))
        result = line.compute_amount()
        assert result == Decimal("5000.00")

    def test_none_rate_pct_treated_as_zero(self):
        line = self._make_line(license_value=Decimal("500000.00"))
        line.rate_pct = None
        assert line.compute_amount() == Decimal("0.00")
