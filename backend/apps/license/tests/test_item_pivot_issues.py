from decimal import Decimal

from apps.license.services.item_pivot_service import _positive_issue


def issue(**values):
    return {
        "actual_excess_qty": "0.000",
        "actual_excess_cif": "0.00",
        "planned_excess_qty": "0.000",
        "planned_excess_cif": "0.00",
        **values,
    }


def test_decimal_zero_strings_are_not_item_pivot_issues():
    assert not _positive_issue(issue())
    assert not _positive_issue(issue(actual_excess_qty=Decimal("0.000")))
    assert not _positive_issue(issue(planned_excess_cif=None))


def test_only_positive_quantity_or_cif_is_an_item_pivot_issue():
    assert _positive_issue(issue(actual_excess_qty="0.001"))
    assert _positive_issue(issue(planned_excess_cif="0.01"))
