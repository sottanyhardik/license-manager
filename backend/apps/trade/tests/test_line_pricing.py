"""
Owner-approved trade line pricing rules T1–T4 (2026-11-17,
docs/decisions/2026-11-17-trade-line-pricing-and-m2m-consumption.md).

Expected values are independent hand calculations, not re-runs of the code under test.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.trade.models import LicenseTrade, LicenseTradeLine
from apps.trade.services.line_pricing import cif_inr_warnings


@pytest.fixture
def item(test_license):
    from apps.license.models import LicenseImportItemsModel

    return LicenseImportItemsModel.objects.create(license=test_license, serial_number=91, description="pricing-item")


def _payload(test_company, test_company_2, lines, invoice="PRICING-001"):
    return {
        "direction": "PURCHASE",
        "from_company": test_company.pk,
        "to_company": test_company_2.pk,
        "invoice_number": invoice,
        "invoice_date": "2026-11-17",
        "lines": lines,
        "payments": [],
    }


def _cif_line(item, **kw):
    line = {"sr_number": item.pk, "mode": "CIF_INR", "cif_inr": "100001.00", "pct": "7.900", "amount_inr": "7900"}
    line.update(kw)
    return line


def _create(client, payload):
    r = client.post(reverse("trade:trade-list"), payload, format="json")
    assert r.status_code == 201, r.data
    return LicenseTrade.objects.get(pk=r.data["id"])


# ── T1 + T3: server authoritative, paise ─────────────────────────────────────

@pytest.mark.django_db
def test_t1_t3_create_ignores_client_amount_and_prices_in_paise(authenticated_client, test_company, test_company_2, item):
    # 100,001.00 × 7.9% = 7,900.079 → 7,900.08 (paise, half-up); client sent whole-rupee 7,900.
    trade = _create(authenticated_client, _payload(test_company, test_company_2, [_cif_line(item)]))
    line = trade.lines.get()
    assert line.amount_inr == Decimal("7900.08")
    assert line.amount_override is False
    trade.refresh_from_db()
    assert trade.subtotal_amount == Decimal("7900.08")
    assert trade.roundoff == Decimal("-0.08")
    assert trade.total_amount == Decimal("7900.00")


@pytest.mark.django_db
def test_t1_override_with_reason_keeps_manual_amount(authenticated_client, test_company, test_company_2, item):
    line = _cif_line(item, cif_inr="0", pct="0", amount_inr="132500.00",
                     amount_override=True, amount_override_reason="Negotiated lump sum")
    trade = _create(authenticated_client, _payload(test_company, test_company_2, [line]))
    stored = trade.lines.get()
    assert stored.amount_inr == Decimal("132500.00")
    assert stored.amount_override is True
    assert stored.amount_override_reason == "Negotiated lump sum"


@pytest.mark.django_db
def test_t1_override_without_reason_is_rejected(authenticated_client, test_company, test_company_2, item):
    payload = _payload(test_company, test_company_2, [_cif_line(item, amount_override=True, amount_override_reason=" ")])
    r = authenticated_client.post(reverse("trade:trade-list"), payload, format="json")
    assert r.status_code == 400
    assert "amount_override_reason" in str(r.data)
    assert not LicenseTrade.objects.filter(invoice_number="PRICING-001").exists()


@pytest.mark.django_db
def test_t1_unchanged_historical_line_keeps_stored_amount(authenticated_client, test_trade, item):
    # Historical manual amount written outside the API (legacy behaviour).
    legacy = LicenseTradeLine.objects.create(
        trade=test_trade, sr_number=item, mode="CIF_INR", cif_inr=Decimal("100001.00"),
        pct=Decimal("7.900"), amount_inr=Decimal("7900.00"),
    )
    data = authenticated_client.get(reverse("trade:trade-detail", args=[test_trade.pk])).data
    r = authenticated_client.patch(
        reverse("trade:trade-detail", args=[test_trade.pk]),
        {"lines": data["lines"], "remarks": "header-only edit"}, format="json",
    )
    assert r.status_code == 200, r.data
    legacy.refresh_from_db()
    assert legacy.amount_inr == Decimal("7900.00")  # not silently recomputed


@pytest.mark.django_db
def test_t1_changed_line_is_recomputed_on_update(authenticated_client, test_company, test_company_2, item):
    trade = _create(authenticated_client, _payload(test_company, test_company_2, [_cif_line(item)]))
    data = authenticated_client.get(reverse("trade:trade-detail", args=[trade.pk])).data
    lines = data["lines"]
    lines[0]["pct"] = "8.000"
    lines[0]["amount_inr"] = "1"  # stale client value must not win
    r = authenticated_client.patch(reverse("trade:trade-detail", args=[trade.pk]), {"lines": lines}, format="json")
    assert r.status_code == 200, r.data
    # 100,001.00 × 8% = 8,000.08 — in the DB and in the response body (no stale prefetch)
    assert trade.lines.get().amount_inr == Decimal("8000.08")
    assert Decimal(str(r.data["lines"][0]["amount_inr"])) == Decimal("8000.08")


@pytest.mark.django_db
def test_t1_lines_endpoint_create_and_update(authenticated_client, test_trade, item):
    url = reverse("trade:trade-line-list")
    r = authenticated_client.post(url, {
        "trade": test_trade.pk, "sr_number": item.pk, "mode": "QTY",
        "qty_kg": "10.0000", "rate_inr_per_kg": "5.125", "amount_inr": "999.00",
    }, format="json")
    assert r.status_code == 201, r.data
    line = LicenseTradeLine.objects.get(pk=r.data["id"])
    assert line.amount_inr == Decimal("51.25")  # 10 × 5.125

    r = authenticated_client.patch(reverse("trade:trade-line-detail", args=[line.pk]), {"qty_kg": "20.0000"}, format="json")
    assert r.status_code == 200, r.data
    line.refresh_from_db()
    assert line.amount_inr == Decimal("102.50")

    r = authenticated_client.patch(reverse("trade:trade-line-detail", args=[line.pk]),
                                   {"amount_override": True, "amount_inr": "100.00"}, format="json")
    assert r.status_code == 400
    assert "amount_override_reason" in str(r.data)


# ── T2: 3-dp rate precision ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_t2_qty_mode_uses_full_three_decimal_rate(test_trade, item):
    line = LicenseTradeLine(trade=test_trade, sr_number=item, mode="QTY",
                            qty_kg=Decimal("124970.1500"), rate_inr_per_kg=Decimal("1.745"))
    # 124,970.15 × 1.745 = 218,072.91175 → 218,072.91 (was 218,697.76 with the 2-dp truncation)
    assert line.compute_amount() == Decimal("218072.91")


@pytest.mark.django_db
def test_t3_half_up_at_exact_half_paisa(test_trade, item):
    line = LicenseTradeLine(trade=test_trade, sr_number=item, mode="QTY",
                            qty_kg=Decimal("1.0000"), rate_inr_per_kg=Decimal("0.005"))
    assert line.compute_amount() == Decimal("0.01")


# ── T4: accept and warn ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_t4_inconsistent_cif_inr_is_accepted_with_warning(authenticated_client, test_company, test_company_2, item):
    line = _cif_line(item, cif_fc="88800.00", exc_rate="95.9000", cif_inr="4536070.00")
    r = authenticated_client.post(reverse("trade:trade-list"), _payload(test_company, test_company_2, [line]), format="json")
    assert r.status_code == 201, r.data
    warnings = r.data["lines"][0]["warnings"]
    assert len(warnings) == 1
    assert "8515920.00" in warnings[0]  # 88,800 × 95.90
    assert LicenseTradeLine.objects.filter(cif_inr=Decimal("4536070.00")).exists()


def test_t4_within_tolerance_or_incomplete_has_no_warning():
    class L:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    assert cif_inr_warnings(L(cif_fc=Decimal("1000"), exc_rate=Decimal("83.4567"), cif_inr=Decimal("83457.70"))) == []
    assert cif_inr_warnings(L(cif_fc=Decimal("1000"), exc_rate=Decimal("83.4567"), cif_inr=Decimal("83458.71"))) != []
    assert cif_inr_warnings(L(cif_fc=Decimal("0"), exc_rate=Decimal("83"), cif_inr=Decimal("5"))) == []


@pytest.mark.django_db
def test_t1_override_flags_are_mirrored_to_counterpart(test_company, test_company_2, item):
    from apps.trade.services.trade_service import _copy_to_counterpart

    sale = LicenseTrade.objects.create(
        direction="SALE", from_company=test_company, to_company=test_company_2,
        invoice_number="PRICING-MIRROR-1", invoice_date="2026-11-17",
    )
    LicenseTradeLine.objects.create(
        trade=sale, sr_number=item, mode="CIF_INR", cif_inr=Decimal("0"), pct=Decimal("0"),
        amount_inr=Decimal("132500.00"), amount_override=True, amount_override_reason="Lump sum",
    )
    _, purchase, created = _copy_to_counterpart(sale.pk, source_direction="SALE")
    assert created
    mirrored = purchase.lines.get()
    assert mirrored.amount_override is True
    assert mirrored.amount_override_reason == "Lump sum"
    assert mirrored.amount_inr == Decimal("132500.00")
