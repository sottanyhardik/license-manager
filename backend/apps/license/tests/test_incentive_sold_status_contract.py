"""
Contract between the backend sold-status rule and the frontend.

derive_sold_status is the single rule used by the cache writer, the serializer and
the list filter. The frontend (pages/masters/tables/IncentiveLicensesTable.tsx) shows:
    YES      -> Sold
    PARTIAL  -> Partial
    NO       -> Available   (the only value that may be shown as Available)
Any other value is shown as Unknown and never as Available.
"""
from decimal import Decimal

import pytest

from apps.license.models.core import derive_sold_status
from apps.license.views_incentive import IncentiveLicenseFilter

D = Decimal


@pytest.mark.parametrize(
    "sold,balance,expected",
    [
        (D("0"), D("1000"), "NO"),          # nothing sold: Available
        (D("0.00"), D("500.00"), "NO"),
        (None, None, "NO"),                 # missing values default to nothing sold
        (D("300"), D("700"), "PARTIAL"),    # some sold, balance remains
        (D("1000"), D("0"), "YES"),         # exactly sold out
        (D("1200"), D("-200"), "YES"),      # over-sold: still Sold, balance kept negative
        # Missing balance is treated as zero (fully consumed) -> YES. Conservative: a
        # sold licence is never reported as NO (Available) because a balance is missing.
        (D("50"), None, "YES"),
    ],
)
def test_derive_sold_status_values(sold, balance, expected):
    assert derive_sold_status(sold, balance) == expected


def test_only_documented_values_are_produced():
    produced = {
        derive_sold_status(sold, bal)
        for sold in (None, D("0"), D("1"), D("1000"))
        for bal in (None, D("-1"), D("0"), D("1"), D("999"))
    }
    assert produced <= {"NO", "YES", "PARTIAL"}


def test_filter_choices_match_the_frontend_contract():
    choices = {value for value, _label in IncentiveLicenseFilter.base_filters["sold_status"].extra["choices"]}
    assert choices == {"NO", "YES", "PARTIAL"}
