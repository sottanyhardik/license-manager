"""
Pytest fixtures for License Manager testing.
Uses the actual model names from the current schema.
"""
import uuid
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# Core models
from apps.core.models import CompanyModel, PortModel, ExchangeRateModel

# License models
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

# Domain models
from apps.trade.models import LicenseTrade, LicenseTradeLine
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.allotment.models import AllotmentModel

User = get_user_model()


def _unique_iec():
    """Return a unique 10-char IEC-style code."""
    return str(uuid.uuid4().int)[:10]


def _unique_license_number():
    return "03" + str(uuid.uuid4().int)[:8]


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123!",
        is_superuser=True,  # superuser sees everything in the API
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    refresh = RefreshToken.for_user(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123!",
    )


# ---------------------------------------------------------------------------
# Master-data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_company(db):
    return CompanyModel.objects.create(
        iec=_unique_iec(),
        name="Test Exporter Ltd",
        address_line_1="123 Test Street",
        address_line_2="Mumbai",
    )


@pytest.fixture
def test_company_2(db):
    return CompanyModel.objects.create(
        iec=_unique_iec(),
        name="Test Importer Ltd",
        address_line_1="456 Import Road",
        address_line_2="Delhi",
    )


@pytest.fixture
def test_port(db):
    return PortModel.objects.create(
        code="INMUN1",
        name="Mumbai Port",
    )


@pytest.fixture
def test_exchange_rate(db):
    return ExchangeRateModel.objects.create(
        date=datetime.now().date(),
        usd=Decimal("84.5000"),
        euro=Decimal("91.2000"),
        pound_sterling=Decimal("106.8000"),
        chinese_yuan=Decimal("11.6000"),
    )


# ---------------------------------------------------------------------------
# License fixture — creates 3 import items (tests assert on count)
# ---------------------------------------------------------------------------

@pytest.fixture
def test_license(db, test_company, test_port):
    license_obj = LicenseDetailsModel.objects.create(
        license_number=_unique_license_number(),
        license_date=datetime.now().date(),
        license_expiry_date=datetime.now().date() + timedelta(days=365),
        exporter=test_company,
        port=test_port,
    )
    for i in range(1, 4):
        LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=i,
            description=f"Test Import Item {i}",
            quantity=Decimal("1000.000"),
            available_quantity=Decimal("1000.000"),
            cif_fc=Decimal("10000.00"),
            cif_inr=Decimal("845000.00"),
        )
    return license_obj


# ---------------------------------------------------------------------------
# Bill of Entry fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_bill_of_entry(db, test_company, test_port, test_license):
    boe = BillOfEntryModel.objects.create(
        company=test_company,
        bill_of_entry_number=str(uuid.uuid4().int)[:7],
        bill_of_entry_date=datetime.now().date(),
        port=test_port,
        exchange_rate=Decimal("84.50"),
        product_name="Test Product",
    )
    # Attach RowDetails against each import item
    for item in test_license.import_license.all():
        RowDetails.objects.create(
            bill_of_entry=boe,
            sr_number=item,
            cif_inr=Decimal("84500.00"),
            cif_fc=Decimal("1000.00"),
            qty=Decimal("100.000"),
        )
    return boe


# ---------------------------------------------------------------------------
# Trade fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_trade(db, test_company, test_company_2, test_bill_of_entry):
    trade = LicenseTrade.objects.create(
        direction="PURCHASE",
        from_company=test_company,
        to_company=test_company_2,
        boe=test_bill_of_entry,
        invoice_number=f"INV-TEST-{uuid.uuid4().int % 9999:04d}",
        invoice_date=datetime.now().date(),
        remarks="Test trade",
    )
    # Create one trade line per BOE RowDetails
    for row in test_bill_of_entry.item_details.all():
        LicenseTradeLine.objects.create(
            trade=trade,
            sr_number=row.sr_number,
            description=row.sr_number.description or "Test Item",
            hsn_code="49070000",
            mode="CIF_INR",
            qty_kg=row.qty,
            cif_inr=row.cif_inr,
        )
    # Link BOE to the trade invoice
    test_bill_of_entry.invoice_no = trade.invoice_number
    test_bill_of_entry.save(update_fields=["invoice_no"])
    return trade


# ---------------------------------------------------------------------------
# Allotment fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_allotment(db, test_company, test_port):
    return AllotmentModel.objects.create(
        company=test_company,
        type="AT",
        port=test_port,
        item_name="Crude Palm Oil",
        required_quantity=Decimal("1000.00"),
        cif_inr=Decimal("100000.00"),
        exchange_rate=Decimal("84.500000"),
        cif_fc=Decimal("1183.43"),
        is_approved=False,
        is_boe=False,
    )


# ---------------------------------------------------------------------------
# POST-body fixtures (dicts for API create calls)
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_allotment_data(test_company, test_port):
    return {
        "company": test_company.id,
        "type": "AT",
        "port": test_port.id,
        "item_name": "Crude Palm Oil",
        "required_quantity": "1000.00",
        "cif_inr": "100000.00",
        "exchange_rate": "84.500000",
        "cif_fc": "1183.43",
        "is_approved": False,
        "is_boe": False,
    }


@pytest.fixture
def fake_trade_data(test_company, test_company_2):
    return {
        "direction": "PURCHASE",
        "from_company": test_company.id,
        "to_company": test_company_2.id,
        "invoice_number": f"INV-{uuid.uuid4().int % 9999:04d}",
        "invoice_date": datetime.now().date().isoformat(),
        "remarks": "Test trade",
        "lines": [
            {
                "description": "Test Item",
                "hsn_code": "49070000",
                "mode": "CIF_INR",
                "qty_kg": "100.0000",
                "cif_inr": "10000.00",
            }
        ],
        "payments": [],
    }
