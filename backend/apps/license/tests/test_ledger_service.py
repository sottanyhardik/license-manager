from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense, LicenseDetailsModel, LicenseFlags, LicenseImportItemsModel
from apps.license.services.ledger_service import (
    build_license_queryset,
    get_ledger_summary,
    get_license_wise_trades,
    get_sold_status,
    prepare_incentive_data,
    search_licenses,
)
from apps.trade.models import IncentiveTradeLine, LicenseTrade, LicenseTradeLine


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


# ---------------------------------------------------------------------------
# New tests for get_license_wise_trades() and build_license_queryset()
# changes: company filter, active_only, search-by-exporter, min_balance,
# ordering, and active_only not bypassed when company is present.
# ---------------------------------------------------------------------------


def _make_dfia_license(company, port, *, license_number, license_date=None, expired=False):
    """Create a DFIA license with one import item and its LicenseFlags row."""
    ld = date.today() if license_date is None else license_date
    expiry = ld - timedelta(days=1) if expired else ld + timedelta(days=365)
    lic = LicenseDetailsModel.objects.create(
        license_number=license_number,
        license_date=ld,
        license_expiry_date=expiry,
        exporter=company,
        port=port,
    )
    LicenseImportItemsModel.objects.create(
        license=lic,
        serial_number=1,
        description="Test item",
        quantity=Decimal("10.000"),
        available_quantity=Decimal("10.000"),
        cif_fc=Decimal("100.00"),
        cif_inr=Decimal("8400.00"),
    )
    # Ensure LicenseFlags row exists (post_save signal normally creates it, but
    # get_or_create guarantees it in the test transaction).
    flags, _ = LicenseFlags.objects.get_or_create(license=lic)
    if expired:
        flags.is_expired = True
        flags.save()
    return lic


def _make_dfia_trade(lic, from_company, to_company, *, invoice_number):
    """Create a PURCHASE trade with one line tied to the first import item."""
    trade = LicenseTrade.objects.create(
        direction="PURCHASE",
        license_type="DFIA",
        from_company=from_company,
        to_company=to_company,
        invoice_number=invoice_number,
        invoice_date=date.today(),
    )
    import_item = lic.import_license.get(serial_number=1)
    LicenseTradeLine.objects.create(
        trade=trade,
        sr_number=import_item,
        description="Test item",
        mode="CIF_INR",
        cif_inr=Decimal("8400.00"),
        pct=Decimal("10.000"),
    )
    return trade


def _make_incentive_license(company, port, *, license_number, license_type="RODTEP",
                             expired=False, balance_value=Decimal("1000.00")):
    """Create an IncentiveLicense, active or expired."""
    ld = date.today()
    expiry = ld - timedelta(days=1) if expired else ld + timedelta(days=730)
    return IncentiveLicense.objects.create(
        license_type=license_type,
        license_number=license_number,
        license_date=ld,
        license_expiry_date=expiry,
        exporter=company,
        port_code=port,
        license_value=balance_value,
        balance_value=balance_value,
        is_active=not expired,
    )


def _make_incentive_trade(incentive_lic, from_company, to_company, *, invoice_number,
                           amount=Decimal("500.00")):
    """Create a PURCHASE incentive trade with one incentive trade line."""
    trade = LicenseTrade.objects.create(
        direction="PURCHASE",
        license_type="INCENTIVE",
        from_company=from_company,
        to_company=to_company,
        invoice_number=invoice_number,
        invoice_date=date.today(),
    )
    IncentiveTradeLine.objects.create(
        trade=trade,
        incentive_license=incentive_lic,
        license_value=incentive_lic.license_value,
        rate_pct=Decimal("50.000"),
        amount_inr=amount,
    )
    return trade


@pytest.mark.django_db
def test_license_wise_trades_company_filter_returns_only_matching_licenses():
    """
    When company_a is the filter, only licenses where company_a is the buyer (PURCHASE)
    or seller (SALE) should appear.  Licenses traded by company_b must be excluded, and
    the company row inside the matched license must show company_a — not a counterparty.

    The previous fixture had company_a as from_company (seller/source) in a PURCHASE
    trade. With the corrected role-aware filter
        Q(direction='PURCHASE', to_company_id=company_a) | Q(direction='SALE', from_company_id=company_a)
    that trade was (correctly) excluded. The fixture is updated so company_a is the
    buyer (to_company) in each PURCHASE trade, matching the new filter semantics.
    """
    company_a = CompanyModel.objects.create(iec="CWA0000001", name="Alpha Exporter")
    company_b = CompanyModel.objects.create(iec="CWB0000001", name="Beta Exporter")
    seller = CompanyModel.objects.create(iec="CWSEL00001", name="Common Seller")
    port = PortModel.objects.create(code="CWPORT1", name="CW Port")

    lic_a = _make_dfia_license(company_a, port, license_number="DFIA-CW-A001", expired=False)
    lic_b = _make_dfia_license(company_b, port, license_number="DFIA-CW-B001", expired=False)

    # company_a is the BUYER (to_company) → matches Q(direction='PURCHASE', to_company_id=company_a)
    _make_dfia_trade(lic_a, seller, company_a, invoice_number="INV-CW-A001")
    # company_b is the BUYER (to_company) → does NOT match company_a filter
    _make_dfia_trade(lic_b, seller, company_b, invoice_number="INV-CW-B001")

    result = get_license_wise_trades({"company": str(company_a.id), "active_only": "false"})

    license_numbers = [lic["license_number"] for lic in result["licenses"]]
    assert "DFIA-CW-A001" in license_numbers, "lic_a should appear when company_a is buyer"
    assert "DFIA-CW-B001" not in license_numbers, "lic_b (company_b's trade) must be excluded"

    # The company row inside lic_a must be company_a only — no counterparty leaking in
    lic_a_entry = next(lic for lic in result["licenses"] if lic["license_number"] == "DFIA-CW-A001")
    company_names = [c["company_name"] for c in lic_a_entry["companies"]]
    assert company_a.name in company_names, "company_a must appear in its own license row"
    assert seller.name not in company_names, "the counterparty (seller) must NOT leak into the row"


@pytest.mark.django_db
def test_license_wise_trades_active_only_false_includes_inactive():
    """active_only=false must include expired incentive licenses; default (true) must exclude them."""
    company = CompanyModel.objects.create(iec="AOEXP00001", name="AO Exporter")
    buyer = CompanyModel.objects.create(iec="AOBUY00001", name="AO Buyer")
    port = PortModel.objects.create(code="AOPORT1", name="AO Port")

    active_lic = _make_incentive_license(company, port, license_number="RODTEP-AO-ACTIVE", expired=False)
    expired_lic = _make_incentive_license(company, port, license_number="RODTEP-AO-EXPIRED", expired=True)

    _make_incentive_trade(active_lic, company, buyer, invoice_number="INV-AO-ACT")
    _make_incentive_trade(expired_lic, company, buyer, invoice_number="INV-AO-EXP")

    result_all = get_license_wise_trades({"active_only": "false"})
    all_numbers = [lic["license_number"] for lic in result_all["licenses"]]
    assert "RODTEP-AO-ACTIVE" in all_numbers
    assert "RODTEP-AO-EXPIRED" in all_numbers

    result_active = get_license_wise_trades({"active_only": "true"})
    active_numbers = [lic["license_number"] for lic in result_active["licenses"]]
    assert "RODTEP-AO-ACTIVE" in active_numbers
    assert "RODTEP-AO-EXPIRED" not in active_numbers


@pytest.mark.django_db
def test_license_wise_trades_search_by_exporter_name():
    """A search term matching an exporter name must return only that license."""
    company_match = CompanyModel.objects.create(iec="SEM0000001", name="Searchable Unique Exporter")
    company_other = CompanyModel.objects.create(iec="SEO0000001", name="Unrelated Supplier")
    buyer = CompanyModel.objects.create(iec="SEBUY00001", name="SE Buyer")
    port = PortModel.objects.create(code="SEPORT1", name="SE Port")

    lic_match = _make_incentive_license(company_match, port, license_number="RODTEP-SE-MATCH")
    lic_other = _make_incentive_license(company_other, port, license_number="RODTEP-SE-OTHER")

    _make_incentive_trade(lic_match, company_match, buyer, invoice_number="INV-SE-M")
    _make_incentive_trade(lic_other, company_other, buyer, invoice_number="INV-SE-O")

    result = get_license_wise_trades({"search": "Searchable Unique", "active_only": "false"})

    license_numbers = [lic["license_number"] for lic in result["licenses"]]
    assert "RODTEP-SE-MATCH" in license_numbers
    assert "RODTEP-SE-OTHER" not in license_numbers


@pytest.mark.django_db
def test_license_wise_trades_min_balance_filter():
    """Only licenses with balance_value >= min_balance threshold should appear."""
    company = CompanyModel.objects.create(iec="MBEXP00001", name="MB Exporter")
    buyer = CompanyModel.objects.create(iec="MBBUY00001", name="MB Buyer")
    port = PortModel.objects.create(code="MBPORT1", name="MB Port")

    high_balance_lic = _make_incentive_license(
        company, port, license_number="RODTEP-MB-HIGH", balance_value=Decimal("5000.00")
    )
    low_balance_lic = _make_incentive_license(
        company, port, license_number="RODTEP-MB-LOW", balance_value=Decimal("100.00")
    )

    _make_incentive_trade(high_balance_lic, company, buyer, invoice_number="INV-MB-HIGH")
    _make_incentive_trade(low_balance_lic, company, buyer, invoice_number="INV-MB-LOW")

    result = get_license_wise_trades({"min_balance": "1000", "active_only": "false"})

    license_numbers = [lic["license_number"] for lic in result["licenses"]]
    assert "RODTEP-MB-HIGH" in license_numbers
    assert "RODTEP-MB-LOW" not in license_numbers


@pytest.mark.django_db
def test_license_wise_trades_ordering_date_ascending():
    """ordering=license_date (ascending) must put the older license first."""
    company = CompanyModel.objects.create(iec="ORDEXP0001", name="Order Exporter")
    buyer = CompanyModel.objects.create(iec="ORDBUY0001", name="Order Buyer")
    port = PortModel.objects.create(code="ORDPORT1", name="Order Port")

    older_date = date.today() - timedelta(days=90)
    newer_date = date.today() - timedelta(days=10)

    lic_older = _make_dfia_license(company, port, license_number="DFIA-ORD-OLD", license_date=older_date)
    lic_newer = _make_dfia_license(company, port, license_number="DFIA-ORD-NEW", license_date=newer_date)

    _make_dfia_trade(lic_older, company, buyer, invoice_number="INV-ORD-OLD")
    _make_dfia_trade(lic_newer, company, buyer, invoice_number="INV-ORD-NEW")

    result = get_license_wise_trades({"ordering": "license_date", "active_only": "false"})

    license_numbers = [lic["license_number"] for lic in result["licenses"]]
    # Both must appear and older must come before newer
    assert "DFIA-ORD-OLD" in license_numbers
    assert "DFIA-ORD-NEW" in license_numbers
    assert license_numbers.index("DFIA-ORD-OLD") < license_numbers.index("DFIA-ORD-NEW")


@pytest.mark.django_db
def test_build_license_queryset_active_only_applies_with_company():
    """active_only must filter out expired licenses even when company is provided.

    Previously a guard (`and not company_id`) caused active_only to be skipped
    when company was selected; that guard has been removed.
    """
    company = CompanyModel.objects.create(iec="BLQEXP0001", name="BLQ Exporter")
    buyer = CompanyModel.objects.create(iec="BLQBUY0001", name="BLQ Buyer")
    port = PortModel.objects.create(code="BLQPORT1", name="BLQ Port")

    expired_lic = _make_dfia_license(company, port, license_number="DFIA-BLQ-EXP", expired=True)
    _make_dfia_trade(expired_lic, company, buyer, invoice_number="INV-BLQ-EXP")

    result = build_license_queryset({"company": str(company.id), "active_only": "true"})

    license_numbers = [lic["license_number"] for lic in result]
    assert "DFIA-BLQ-EXP" not in license_numbers
