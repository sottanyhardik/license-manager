from decimal import Decimal
from types import SimpleNamespace

from apps.license.serializers.incentive import IncentiveLicenseSerializer


def _incentive_stub(*, sold_value=None, balance_value=None):
    return SimpleNamespace(sold_value=sold_value, balance_value=balance_value)


def test_incentive_serializer_uses_cached_decimal_fields_directly():
    serializer = IncentiveLicenseSerializer()
    incentive = _incentive_stub(
        sold_value=Decimal("12.50"),
        balance_value=Decimal("87.50"),
    )

    assert serializer.get_sold_value(incentive) == 12.5
    assert serializer.get_balance_value(incentive) == 87.5
    assert serializer.get_sold_status(incentive) == "PARTIAL"


def test_incentive_serializer_treats_missing_cached_values_as_zero():
    serializer = IncentiveLicenseSerializer()
    incentive = _incentive_stub()

    assert serializer.get_sold_value(incentive) == 0.0
    assert serializer.get_balance_value(incentive) == 0.0
    assert serializer.get_sold_status(incentive) == "NO"


def test_incentive_serializer_keeps_frontend_expiry_date_write_contract():
    serializer = IncentiveLicenseSerializer()

    assert serializer.fields["license_expiry_date"].read_only is False
