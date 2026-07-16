from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense, LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.ledger_service import (
    build_license_queryset,
    get_ledger_summary,
    get_license_wise_trades,
    get_sold_status,
    prepare_incentive_data,
    search_licenses,
)
from apps.trade.models import LicenseTrade, LicenseTradeLine


@pytest.fixture
def company():
    return CompanyModel.objects.create(iec="1234567890", name="Ledger Exporter")


@pytest.fixture
def buyer_company():
    return CompanyModel.objects.create(iec="1234567891", name="Ledger Buyer")


@pytest.fixture
def port():
    return PortModel.objects.create(code="INLED1", name="Ledger Port")


@pytest.fixture
def dfia_license(company, port):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="DFIA-LEDGER-001",
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=365),
        exporter=company,
        port=port,
    )
    LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Ledger item",
        quantity=Decimal("10.000"),
        available_quantity=Decimal("10.000"),
        cif_fc=Decimal("100.00"),
        cif_inr=Decimal("8400.00"),
    )
    return license_obj


@pytest.fixture
def incentive_license(company, port):
    license_date = date.today()
    return IncentiveLicense.objects.create(
        license_type="RODTEP",
        license_number="RODTEP-LEDGER-001",
        license_date=license_date,
        license_expiry_date=license_date + timedelta(days=730),
        exporter=company,
        port_code=port,
        license_value=Decimal("1250.00"),
    )


@pytest.fixture
def dfia_trade(dfia_license, company, buyer_company):
    trade = LicenseTrade.objects.create(
        direction="PURCHASE",
        license_type="DFIA",
        from_company=company,
        to_company=buyer_company,
        invoice_number="LEDGER-TRADE-001",
        invoice_date=date.today(),
    )
    import_item = dfia_license.import_license.get(serial_number=1)
    LicenseTradeLine.objects.create(
        trade=trade,
        sr_number=import_item,
        description="Ledger item",
        mode="CIF_INR",
        cif_inr=Decimal("8400.00"),
        pct=Decimal("10.000"),
    )
    return trade


def test_get_sold_status_handles_nullish_totals():
    assert get_sold_status(None, None) == "YES"
    assert get_sold_status(Decimal("100.00"), None) == "YES"
    assert get_sold_status(Decimal("100.00"), Decimal("100.00")) == "NO"
    assert get_sold_status(Decimal("100.00"), Decimal("25.00")) == "PARTIAL"


@pytest.mark.django_db
def test_prepare_incentive_data_accepts_plain_model_lists(incentive_license):
    data = prepare_incentive_data([incentive_license])

    assert data == [
        {
            "id": incentive_license.id,
            "license_type": "RODTEP",
            "license_number": "RODTEP-LEDGER-001",
            "license_date": incentive_license.license_date,
            "license_expiry_date": incentive_license.license_expiry_date,
            "exporter_name": incentive_license.exporter.name,
            "exporter_id": incentive_license.exporter.id,
            "port_name": incentive_license.port_code.name,
            "total_value": 0.0,
            "balance_value": 0.0,
            "sold_value": 0.0,
            "purchase_amount": 0.0,
            "sale_amount": 0.0,
            "profit_loss": 0.0,
            "currency": "INR",
            "is_expired": False,
            "is_active": True,
            "sold_status": "YES",
        }
    ]


@pytest.mark.django_db
def test_ledger_filters_ignore_malformed_values(dfia_license, incentive_license):
    params = {
        "active_only": None,
        "company": "not-a-company",
        "min_balance": "NaN",
        "purchase_date_from": "not-a-date",
        "purchase_date_to": "2026-99-99",
    }

    data = build_license_queryset(params)
    summary = get_ledger_summary(params)

    assert isinstance(data, list)
    assert set(summary) == {"dfia", "incentive"}


@pytest.mark.django_db
def test_search_licenses_normalizes_type_and_rejects_blank_queries(incentive_license):
    assert search_licenses({"q": "   "}) is None

    result = search_licenses(
        {
            "q": "rodtep-ledger",
            "license_type": "rodtep",
            "min_balance": "Infinity",
        }
    )

    assert result["license_type"] == "RODTEP"
    assert result["count"] == 1
    assert result["results"][0]["license_number"] == incentive_license.license_number


@pytest.mark.django_db
def test_license_wise_trades_ignores_invalid_date_filters(dfia_trade):
    result = get_license_wise_trades(
        {
            "purchase_date_from": "not-a-date",
            "purchase_date_to": "2026-99-99",
        }
    )

    assert "licenses" in result
