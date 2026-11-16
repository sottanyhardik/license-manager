"""POST /trade/lines/ and /trade/payments/ must persist (models lack created_by)."""
import pytest
from django.urls import reverse

from apps.core.views.master_view import MasterViewSet
from apps.trade.models import LicenseTradeLine, LicenseTradePayment


@pytest.mark.xfail(
    strict=True, raises=Exception,
    reason="SEPARATE defect: LicenseTradePaymentSerializer (trade/api/serializers.py:49) is nested-only "
           "and exposes no `trade` field, so a standalone POST hits NOT NULL trade_id. Not owned here.",
)
@pytest.mark.django_db
def test_post_payment_creates(authenticated_client, test_trade):
    r = authenticated_client.post(
        reverse("trade:trade-payment-list"),
        {"trade": test_trade.pk, "amount": "12.50", "note": "post-pay"},
        format="json",
    )
    assert r.status_code == 201, r.data
    assert LicenseTradePayment.objects.filter(note="post-pay", trade=test_trade).exists()


@pytest.mark.django_db
def test_post_line_creates(authenticated_client, test_trade, test_license):
    from apps.license.models import LicenseImportItemsModel
    item = LicenseImportItemsModel.objects.create(license=test_license, serial_number=77, description="line-item")
    before = LicenseTradeLine.objects.count()
    r = authenticated_client.post(
        reverse("trade:trade-line-list"),
        {"trade": test_trade.pk, "sr_number": item.pk, "description": "post-line", "mode": "QTY",
         "qty_kg": "10.0000", "rate_inr_per_kg": "5.000"},
        format="json",
    )
    assert r.status_code == 201, r.data
    assert LicenseTradeLine.objects.count() == before + 1


@pytest.mark.django_db
def test_perform_create_payment_persists_without_created_by(test_user, test_trade):
    """Viewset layer: no created_by kwarg reaches the model, row persists."""
    from types import SimpleNamespace
    from apps.trade.api.views import TradePaymentViewSet

    class _S:
        Meta = SimpleNamespace(model=LicenseTradePayment)

        def save(self, **kw):
            return LicenseTradePayment.objects.create(trade=test_trade, amount="3.00", note="vs-pay", **kw)

    vs = TradePaymentViewSet()
    vs.request = SimpleNamespace(user=test_user)
    vs.perform_create(_S())
    assert LicenseTradePayment.objects.filter(note="vs-pay").exists()


class _Ser:
    def __init__(self, model):
        from types import SimpleNamespace
        self.Meta = SimpleNamespace(model=model)
        self.kwargs = None

    def save(self, **kw):
        self.kwargs = kw


@pytest.mark.django_db
def test_audit_model_still_gets_created_by_and_modified_by(test_user):
    from types import SimpleNamespace
    from apps.core.models import CompanyModel
    vs = MasterViewSet()
    vs.request = SimpleNamespace(user=test_user)
    s = _Ser(CompanyModel)
    vs.perform_create(s)
    assert s.kwargs == {"created_by": test_user}
    s = _Ser(CompanyModel)
    vs.perform_update(s)
    assert s.kwargs == {"modified_by": test_user}
