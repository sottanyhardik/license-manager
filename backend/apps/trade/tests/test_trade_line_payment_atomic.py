"""TradeLine / TradePayment generic CRUD is atomic."""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.trade.models import LicenseTradeLine, LicenseTradePayment
from apps.trade.views import TradeLineViewSet, TradePaymentViewSet


class _WriteThenFail:
    def __init__(self, trade):
        self.trade = trade
        self.Meta = SimpleNamespace(model=LicenseTradePayment)

    def save(self, **kwargs):
        LicenseTradePayment.objects.create(trade=self.trade, amount=Decimal("1.00"), note="atomic-probe")
        raise RuntimeError("boom after first write")


def _vs(cls):
    vs = cls()
    vs.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    return vs


@pytest.mark.django_db
@pytest.mark.parametrize("cls", [TradePaymentViewSet, TradeLineViewSet])
@pytest.mark.parametrize("op", ["perform_create", "perform_update"])
def test_write_rolls_back_on_failure(test_trade, cls, op):
    with pytest.raises(RuntimeError):
        getattr(_vs(cls), op)(_WriteThenFail(test_trade))
    assert not LicenseTradePayment.objects.filter(note="atomic-probe").exists()


@pytest.mark.django_db
def test_destroy_rolls_back_on_failure(test_trade):
    pay = LicenseTradePayment.objects.create(trade=test_trade, amount=Decimal("5.00"), note="keep")
    other = LicenseTradePayment.objects.create(trade=test_trade, amount=Decimal("6.00"), note="sibling")

    def delete_then_fail(*a, **k):
        other.delete()
        raise RuntimeError("boom")

    pay.delete = delete_then_fail
    with pytest.raises(RuntimeError):
        _vs(TradePaymentViewSet).perform_destroy(pay)
    assert LicenseTradePayment.objects.filter(note="sibling").exists()


@pytest.mark.django_db
def test_payment_api_update_and_delete_success_path_unchanged(authenticated_client, test_trade):
    # NOTE: POST is not exercised: pre-existing bug, perform_create injects
    # created_by which LicenseTradePayment does not have (unchanged by this batch).
    pay = LicenseTradePayment.objects.create(trade=test_trade, amount=Decimal("10.50"), note="ok")
    url = reverse("trade:trade-payment-detail", args=[pay.pk])
    r = authenticated_client.patch(url, {"note": "changed"}, format="json")
    assert r.status_code == 200, r.data
    assert r.data["note"] == "changed" and r.data["amount"] == "10.50"
    assert authenticated_client.delete(url).status_code == 204
    assert not LicenseTradePayment.objects.filter(pk=pay.pk).exists()
