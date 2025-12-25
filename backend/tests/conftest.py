"""
Pytest fixtures for License Manager testing
Provides fake database setup and common test utilities
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from faker import Faker
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# Import models
from core.models import Company, Port, ExchangeRate
from license.models import License, LicenseImportItem
from trade.models import Trade, TradeLine
from bill_of_entry.models import BillOfEntry, BillOfEntryItemDetail
from allotment.models import Allotment

User = get_user_model()
fake = Faker()


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Setup test database with initial configuration
    """
    with django_db_blocker.unblock():
        pass  # Database migrations handled automatically


@pytest.fixture
def api_client():
    """
    DRF API Client for testing endpoints
    """
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, test_user):
    """
    Authenticated API client with JWT token
    """
    refresh = RefreshToken.for_user(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
    return api_client


@pytest.fixture
def test_user(db):
    """
    Create a test user
    """
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    return user


@pytest.fixture
def admin_user(db):
    """
    Create an admin user
    """
    user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )
    return user


@pytest.fixture
def test_company(db):
    """
    Create a test company
    """
    return Company.objects.create(
        name=fake.company(),
        pan=fake.bothify(text='??#######?').upper(),
        gst_number=fake.bothify(text='##???#####?###?').upper(),
        address_line_1=fake.street_address(),
        address_line_2=fake.city(),
        phone=fake.phone_number()[:15],
        email=fake.company_email()
    )


@pytest.fixture
def test_company_2(db):
    """
    Create a second test company for trade testing
    """
    return Company.objects.create(
        name=fake.company(),
        pan=fake.bothify(text='??#######?').upper(),
        gst_number=fake.bothify(text='##???#####?###?').upper(),
        address_line_1=fake.street_address(),
        address_line_2=fake.city(),
        phone=fake.phone_number()[:15],
        email=fake.company_email()
    )


@pytest.fixture
def test_port(db):
    """
    Create a test port
    """
    return Port.objects.create(
        code=fake.bothify(text='IN???#').upper(),
        name=fake.city() + ' Port',
        country='India'
    )


@pytest.fixture
def test_exchange_rate(db):
    """
    Create a test exchange rate
    """
    return ExchangeRate.objects.create(
        date=datetime.now().date(),
        usd=Decimal('84.50'),
        eur=Decimal('91.20'),
        gbp=Decimal('106.80')
    )


@pytest.fixture
def test_license(db, test_company, test_port):
    """
    Create a test DFIA license with items
    """
    license_number = fake.bothify(text='03########').upper()
    license = License.objects.create(
        license_number=license_number,
        license_date=datetime.now().date(),
        exporter_name=test_company.name,
        exporter_iec=fake.bothify(text='##########'),
        port=test_port,
        scheme_code='DFIA',
        notification='NOTIFICATION'
    )
    
    # Create license items
    for i in range(1, 4):
        LicenseImportItem.objects.create(
            license=license,
            sr_number=i,
            description=f'Test Item {i}',
            hs_code='49070000',
            quantity=Decimal('1000.00'),
            uqc='KGS',
            total_quantity=Decimal('1000.00'),
            fob_value_inr=Decimal('100000.00'),
            balance_quantity=Decimal('1000.00')
        )
    
    return license


@pytest.fixture
def test_bill_of_entry(db, test_company, test_port, test_license):
    """
    Create a test Bill of Entry
    """
    boe = BillOfEntry.objects.create(
        bill_of_entry_number=fake.bothify(text='#######'),
        bill_of_entry_date=datetime.now().date(),
        importer_name=test_company.name,
        port=test_port,
        exchange_rate=Decimal('84.50'),
        total_duty=Decimal('50000.00'),
        invoice_no=None,  # Not linked to trade yet
        license=test_license
    )
    
    # Create BOE items
    for item in test_license.import_items.all():
        BillOfEntryItemDetail.objects.create(
            bill_of_entry=boe,
            sr_number=item.sr_number,
            item_description=item.description,
            hs_code=item.hs_code,
            qty=Decimal('100.00'),
            cif_fc=Decimal('1000.00'),
            cif_inr=Decimal('84500.00'),
            uqc='KGS'
        )
    
    return boe


@pytest.fixture
def test_trade(db, test_company, test_company_2, test_bill_of_entry):
    """
    Create a test trade (purchase)
    """
    trade = Trade.objects.create(
        direction='PURCHASE',
        license_type='DFIA',
        from_company=test_company,
        to_company=test_company_2,
        boe=test_bill_of_entry,
        invoice_number=fake.bothify(text='INV-####'),
        invoice_date=datetime.now().date(),
        remarks='Test trade'
    )
    
    # Create trade lines
    for i, item in enumerate(test_bill_of_entry.item_details.all()[:2], 1):
        TradeLine.objects.create(
            trade=trade,
            sr_number=test_bill_of_entry.license.import_items.filter(sr_number=item.sr_number).first(),
            description=item.item_description,
            hsn_code=item.hs_code,
            mode='CIF_INR',
            qty_kg=item.qty,
            cif_inr=item.cif_inr,
            pct=Decimal('7.9'),
            amount_inr=item.cif_inr * Decimal('0.079')
        )
    
    # Update BOE invoice reference
    test_bill_of_entry.invoice_no = trade.invoice_number
    test_bill_of_entry.save()
    
    return trade


@pytest.fixture
def test_allotment(db, test_company, test_port):
    """
    Create a test allotment
    """
    return Allotment.objects.create(
        company=test_company,
        type='AT',
        port=test_port,
        item_name='Crude Palm Oil',
        required_quantity=Decimal('1000.00'),
        cif_inr=Decimal('100000.00'),
        exchange_rate=Decimal('84.50'),
        cif_fc=Decimal('1183.43'),
        unit_value_per_unit=Decimal('1.183'),
        estimated_arrival_date=datetime.now().date() + timedelta(days=30),
        is_approved=False,
        is_boe=False
    )


@pytest.fixture
def fake_license_data():
    """
    Generate fake license data for POST requests
    """
    return {
        'license_number': fake.bothify(text='03########'),
        'license_date': datetime.now().date().isoformat(),
        'exporter_name': fake.company(),
        'exporter_iec': fake.bothify(text='##########'),
        'scheme_code': 'DFIA',
        'notification': 'NOTIFICATION'
    }


@pytest.fixture
def fake_trade_data(test_company, test_company_2):
    """
    Generate fake trade data for POST requests
    """
    return {
        'direction': 'PURCHASE',
        'license_type': 'DFIA',
        'from_company': test_company.id,
        'to_company': test_company_2.id,
        'invoice_number': fake.bothify(text='INV-####'),
        'invoice_date': datetime.now().date().isoformat(),
        'remarks': 'Test trade',
        'lines': [
            {
                'description': 'Test Item',
                'hsn_code': '49070000',
                'mode': 'CIF_INR',
                'qty_kg': 100.0,
                'cif_inr': 10000.0,
                'pct': 7.9,
                'amount_inr': 790.0
            }
        ],
        'payments': []
    }


@pytest.fixture
def fake_allotment_data(test_company, test_port):
    """
    Generate fake allotment data for POST requests
    """
    return {
        'company': test_company.id,
        'type': 'AT',
        'port': test_port.id,
        'item_name': 'Crude Palm Oil',
        'required_quantity': 1000.0,
        'cif_inr': 100000.0,
        'exchange_rate': 84.50,
        'cif_fc': 1183.43,
        'unit_value_per_unit': 1.183,
        'is_approved': False,
        'is_boe': False
    }


# Utility fixtures
@pytest.fixture
def clear_database(db):
    """
    Clear all data from database tables
    """
    from django.core.management import call_command
    call_command('flush', '--no-input')


@pytest.fixture
def load_test_fixtures(db):
    """
    Load test fixtures from JSON files if they exist
    """
    from django.core.management import call_command
    try:
        call_command('loaddata', 'test_fixtures.json')
    except Exception:
        pass  # Fixtures file doesn't exist yet
