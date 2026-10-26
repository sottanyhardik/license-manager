"""Per-save memo of the financial balance: computed once per licence inside the block, never outside it."""
from decimal import Decimal

import pytest

from apps.license.services.balance_calculator import LicenseBalanceCalculator, financial_balance_memo


class _Licence:
    def __init__(self, pk):
        self.pk = pk


@pytest.fixture
def counted(monkeypatch):
    calls = []

    def fake(cls, license_obj):
        calls.append(license_obj.pk)
        return Decimal("100.00") + Decimal(license_obj.pk or 0)

    monkeypatch.setattr(LicenseBalanceCalculator, "_calculate_financial_balance", classmethod(fake))
    return calls


def test_inside_the_block_each_licence_is_computed_once(counted):
    with financial_balance_memo():
        first = LicenseBalanceCalculator.calculate_financial_balance(_Licence(7))
        again = LicenseBalanceCalculator.calculate_financial_balance(_Licence(7))
        other = LicenseBalanceCalculator.calculate_financial_balance(_Licence(8))
    assert first == again == Decimal("107.00")
    assert other == Decimal("108.00")
    assert counted == [7, 8]


def test_outside_the_block_nothing_is_cached(counted):
    LicenseBalanceCalculator.calculate_financial_balance(_Licence(7))
    LicenseBalanceCalculator.calculate_financial_balance(_Licence(7))
    assert counted == [7, 7]


def test_memo_is_cleared_when_the_block_ends(counted):
    with financial_balance_memo():
        LicenseBalanceCalculator.calculate_financial_balance(_Licence(7))
    LicenseBalanceCalculator.calculate_financial_balance(_Licence(7))
    assert counted == [7, 7]


def test_unsaved_licence_is_never_cached(counted):
    with financial_balance_memo():
        LicenseBalanceCalculator.calculate_financial_balance(_Licence(None))
        LicenseBalanceCalculator.calculate_financial_balance(_Licence(None))
    assert counted == [None, None]
