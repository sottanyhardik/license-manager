# License Manager - Testing Guide

Complete guide for automated testing with fake database

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Setup](#test-setup)
3. [Running Tests](#running-tests)
4. [Test Structure](#test-structure)
5. [Writing Tests](#writing-tests)
6. [Fake Data](#fake-data)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Run All Tests
```bash
./run-tests.sh
```

### Run Specific Test Types
```bash
./run-tests.sh --api           # API tests only
./run-tests.sh --fast          # Skip slow tests
./run-tests.sh --coverage      # Generate detailed coverage report
./run-tests.sh --clean         # Clean artifacts first
```

---

## Test Setup

### 1. Install Test Dependencies

```bash
cd backend
pip install -r requirements-test.txt
```

**Dependencies Installed:**
- `pytest` - Testing framework
- `pytest-django` - Django integration
- `pytest-cov` - Coverage reporting
- `faker` - Fake data generation
- `factory-boy` - Model factories
- `responses` - HTTP mocking

### 2. Test Database Configuration

Tests use Django's test database (automatically created/destroyed):
- Database: `test_<your_database_name>`
- Isolated from production data
- Automatically migrated before tests
- Cleaned up after tests

**No manual database setup required!**

---

## Running Tests

### Command Line Options

```bash
# Run all tests with coverage
./run-tests.sh

# Run only fast tests (skip @pytest.mark.slow)
./run-tests.sh --fast

# Run only API tests
./run-tests.sh --api

# Run only unit tests
./run-tests.sh --unit

# Run integration tests
./run-tests.sh --integration

# Clean artifacts before running
./run-tests.sh --clean

# Generate HTML coverage report
./run-tests.sh --coverage
```

### Direct Pytest Commands

```bash
cd backend

# Run all tests
pytest

# Run specific test file
pytest tests/test_api_core.py

# Run specific test class
pytest tests/test_api_core.py::TestCompanyAPI

# Run specific test method
pytest tests/test_api_core.py::TestCompanyAPI::test_list_companies

# Run with coverage
pytest --cov=. --cov-report=html

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x

# Run in parallel (faster)
pytest -n auto
```

---

## Test Structure

### Directory Layout

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Fixtures and configuration
│   ├── test_api_core.py         # Company, Port, ExchangeRate tests
│   ├── test_api_license.py      # License and LicenseItem tests
│   ├── test_api_trade.py        # Trade and TradeLine tests
│   ├── test_api_allotment.py    # Allotment tests
│   └── test_api_boe.py          # Bill of Entry tests
├── pytest.ini                    # Pytest configuration
└── requirements-test.txt         # Test dependencies
```

### Test Categories

Tests are marked with pytest markers:

- **@pytest.mark.api** - API endpoint tests
- **@pytest.mark.unit** - Unit tests (isolated functions)
- **@pytest.mark.integration** - Integration tests (multiple components)
- **@pytest.mark.database** - Tests requiring database
- **@pytest.mark.slow** - Slow tests (can be skipped)

---

## Fake Data & Fixtures

### Available Fixtures

#### Authentication
```python
def test_my_api(authenticated_client):
    """authenticated_client has JWT token"""
    response = authenticated_client.get('/api/endpoint/')
```

#### Users
```python
def test_with_user(test_user, admin_user):
    """test_user - regular user, admin_user - superuser"""
    assert test_user.is_active
    assert admin_user.is_superuser
```

#### Core Data
```python
def test_with_company(test_company, test_company_2):
    """Pre-created companies with fake data"""
    assert test_company.name
    assert test_company.pan
```

```python
def test_with_port(test_port):
    """Pre-created port"""
    assert test_port.code
```

```python
def test_with_exchange_rate(test_exchange_rate):
    """Pre-created exchange rate"""
    assert test_exchange_rate.usd == Decimal('84.50')
```

#### License Data
```python
def test_with_license(test_license):
    """Complete license with 3 import items"""
    assert test_license.license_number
    assert test_license.import_items.count() == 3
```

#### Bill of Entry
```python
def test_with_boe(test_bill_of_entry):
    """BOE with item details"""
    assert test_bill_of_entry.item_details.count() >= 3
```

#### Trade
```python
def test_with_trade(test_trade):
    """Complete trade with lines"""
    assert test_trade.lines.count() >= 2
```

#### Allotment
```python
def test_with_allotment(test_allotment):
    """Pre-created allotment"""
    assert test_allotment.item_name
```

### Fake Data Generators

Use Faker for generating test data:

```python
from faker import Faker
fake = Faker()

# Generate fake data
company_name = fake.company()
email = fake.company_email()
phone = fake.phone_number()
address = fake.street_address()
license_number = fake.bothify(text='03########')
```

### Factory Pattern

Fixtures in `conftest.py` provide factory-like data generation:

```python
@pytest.fixture
def fake_trade_data(test_company, test_company_2):
    """Generate fake trade data for POST requests"""
    return {
        'direction': 'PURCHASE',
        'from_company': test_company.id,
        'to_company': test_company_2.id,
        'invoice_number': fake.bothify(text='INV-####'),
        'lines': [...]
    }
```

---

## Writing Tests

### Test Class Structure

```python
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.api
@pytest.mark.database
class TestMyAPI:
    """Test description"""
    
    def test_list_endpoint(self, authenticated_client, test_model):
        """Test GET /api/endpoint/"""
        url = reverse('endpoint-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
    
    def test_create_endpoint(self, authenticated_client):
        """Test POST /api/endpoint/"""
        url = reverse('endpoint-list')
        data = {'field': 'value'}
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['field'] == 'value'
```

### Best Practices

1. **Use descriptive test names**
   ```python
   def test_create_company_with_valid_data()  # ✓ Good
   def test_company()  # ✗ Bad
   ```

2. **Follow AAA pattern** (Arrange, Act, Assert)
   ```python
   def test_example(authenticated_client):
       # Arrange
       url = reverse('company-list')
       data = {'name': 'Test Company'}
       
       # Act
       response = authenticated_client.post(url, data)
       
       # Assert
       assert response.status_code == 201
   ```

3. **Use fixtures for setup**
   ```python
   def test_with_fixture(test_license):  # ✓ Good
       assert test_license.license_number
   
   def test_without_fixture():  # ✗ Bad
       license = License.objects.create(...)
   ```

4. **Mark tests appropriately**
   ```python
   @pytest.mark.api
   @pytest.mark.database
   def test_api_endpoint(authenticated_client):
       pass
   ```

5. **Test edge cases**
   ```python
   def test_create_with_missing_required_field()
   def test_create_with_invalid_data()
   def test_delete_nonexistent_resource()
   ```

---

## Test Coverage

### View Coverage Report

After running with `--coverage`:

```bash
# Terminal output shows coverage %
# HTML report available at:
open backend/htmlcov/index.html
```

### Coverage Goals

- **API Endpoints**: 90%+
- **Models**: 80%+
- **Business Logic**: 85%+
- **Utilities**: 75%+

---

## Example Test Scenarios

### Test CRUD Operations

```python
@pytest.mark.api
class TestCompanyCRUD:
    def test_create(self, authenticated_client):
        """Create company"""
        pass
    
    def test_list(self, authenticated_client, test_company):
        """List companies"""
        pass
    
    def test_retrieve(self, authenticated_client, test_company):
        """Get single company"""
        pass
    
    def test_update(self, authenticated_client, test_company):
        """Update company"""
        pass
    
    def test_delete(self, authenticated_client, test_company):
        """Delete company"""
        pass
```

### Test Filtering

```python
def test_filter_by_field(self, authenticated_client, test_license):
    """Test GET /licenses/?scheme_code=DFIA"""
    url = reverse('license-list')
    response = authenticated_client.get(url, {'scheme_code': 'DFIA'})
    
    assert response.status_code == 200
```

### Test File Upload

```python
def test_upload_csv(self, authenticated_client, tmp_path):
    """Test CSV file upload"""
    csv_content = "header1,header2\nvalue1,value2"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)
    
    url = reverse('upload-endpoint')
    with open(csv_file, 'rb') as f:
        response = authenticated_client.post(url, {'file': f}, format='multipart')
    
    assert response.status_code == 200
```

### Test Permissions

```python
def test_unauthorized_access(self, api_client):
    """Test without authentication"""
    url = reverse('company-list')
    response = api_client.get(url)
    
    assert response.status_code == 401
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors

**Problem**: `ModuleNotFoundError: No module named 'pytest'`

**Solution**:
```bash
cd backend
pip install -r requirements-test.txt
```

#### 2. Database Errors

**Problem**: `django.db.utils.OperationalError: FATAL: database "test_db" does not exist`

**Solution**: Django creates test database automatically. Ensure PostgreSQL is running:
```bash
# macOS
brew services start postgresql

# Ubuntu
sudo service postgresql start
```

#### 3. Migration Errors

**Problem**: `django.db.migrations.exceptions.InconsistentMigrationHistory`

**Solution**:
```bash
cd backend
python manage.py migrate
```

#### 4. Fixture Not Found

**Problem**: `fixture 'test_company' not found`

**Solution**: Ensure `conftest.py` is in the `tests/` directory and properly formatted.

#### 5. URL Reverse Errors

**Problem**: `django.urls.exceptions.NoReverseMatch: Reverse for 'company-list' not found`

**Solution**: Check URL name in `urls.py` matches the name used in `reverse()`.

### Debug Mode

Run tests with verbose output and stop on first failure:

```bash
pytest -vvs -x
```

Run specific test with print statements visible:

```bash
pytest -s tests/test_api_core.py::TestCompanyAPI::test_list_companies
```

---

## Performance Tips

### 1. Run Tests in Parallel

```bash
pytest -n auto  # Use all CPU cores
pytest -n 4     # Use 4 workers
```

### 2. Skip Slow Tests During Development

```bash
./run-tests.sh --fast
```

### 3. Run Only Failed Tests

```bash
pytest --lf  # Last failed
pytest --ff  # Failed first, then rest
```

### 4. Use Test Database Reuse (for development)

```bash
pytest --reuse-db  # Don't destroy DB between runs
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
    
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.13'
    
    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements-test.txt
    
    - name: Run tests
      run: ./run-tests.sh --coverage
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Maintenance

### Adding New Tests

1. Create test file: `tests/test_api_<module>.py`
2. Add test class with markers
3. Use fixtures from `conftest.py`
4. Run tests to verify

### Updating Fixtures

Edit `tests/conftest.py` to add/modify fixtures:

```python
@pytest.fixture
def my_new_fixture(db):
    """Description"""
    return Model.objects.create(...)
```

### Test Data Cleanup

Tests automatically clean up after themselves (transaction rollback). No manual cleanup needed.

---

## Support

For issues or questions:

1. Check this guide
2. Run with `-vvs` for detailed output
3. Review `conftest.py` for available fixtures
4. Check test examples in `tests/` directory

---

**Last Updated**: December 25, 2024  
**Version**: 1.0
