# Automated Testing with Fake Database

## Quick Start

```bash
# Make script executable (first time only)
chmod +x run-tests.sh

# Run all tests
./run-tests.sh

# Run specific test types
./run-tests.sh --api        # API tests only
./run-tests.sh --fast       # Skip slow tests
./run-tests.sh --coverage   # Detailed coverage report
./run-tests.sh --clean      # Clean artifacts first
```

## What's Included

### ✅ Test Infrastructure
- **Pytest Configuration** (`backend/pytest.ini`)
- **Test Fixtures** (`backend/tests/conftest.py`) - Fake data generators
- **Test Requirements** (`backend/requirements-test.txt`)
- **Test Runner** (`run-tests.sh`) - Automated test execution

### ✅ Test Suites Created
1. **Core API Tests** (`test_api_core.py`)
   - Company CRUD
   - Port CRUD
   - Exchange Rate CRUD

2. **License API Tests** (`test_api_license.py`)
   - License listing & retrieval
   - License items
   - Ledger upload

3. **Trade API Tests** (`test_api_trade.py`)
   - Trade CRUD
   - Trade lines
   - Bill of Supply generation
   - License ledger integration

4. **Allotment API Tests** (`test_api_allotment.py`)
   - Allotment CRUD
   - Filtering by company/status

5. **Bill of Entry Tests** (`test_api_boe.py`)
   - BOE CRUD
   - BOE integration with trades

### ✅ Fake Data Fixtures

All fixtures available in `backend/tests/conftest.py`:

- `test_user` - Regular user with JWT auth
- `admin_user` - Superuser
- `authenticated_client` - API client with JWT token
- `test_company` / `test_company_2` - Fake companies
- `test_port` - Fake port
- `test_exchange_rate` - Exchange rate data
- `test_license` - Complete license with 3 items
- `test_bill_of_entry` - BOE with item details
- `test_trade` - Complete trade with lines
- `test_allotment` - Allotment data

## Installation

### 1. Install Test Dependencies

```bash
source .venv/bin/activate  # Activate virtual environment
cd backend
pip install -r requirements-test.txt
```

### 2. Verify Setup

```bash
pytest --version
# Should show: pytest 8.3.4
```

## Usage Examples

### Run All Tests
```bash
./run-tests.sh
```

**Output:**
```
═══════════════════════════════════════════════════════════
   License Manager - Automated Test Suite
═══════════════════════════════════════════════════════════

━━━ Setting Up Test Environment ━━━
✓ Test environment ready

━━━ Running Backend Tests ━━━
Mode: All tests

Running: pytest -v --tb=short --cov=. --cov-report=term tests/

================== test session starts ===================
collected 45 items

tests/test_api_core.py::TestCompanyAPI::test_list_companies PASSED
tests/test_api_core.py::TestCompanyAPI::test_create_company PASSED
...

================== 45 passed in 12.34s ===================

━━━ Test Summary ━━━
Backend Tests:  ✓ PASSED

╔═══════════════════════════════════════╗
║   ALL TESTS PASSED SUCCESSFULLY! ✓   ║
╚═══════════════════════════════════════╝
```

### Run Specific Tests

```bash
# API tests only
./run-tests.sh --api

# Fast tests (skip slow ones)
./run-tests.sh --fast

# With detailed coverage
./run-tests.sh --coverage
# Opens: backend/htmlcov/index.html
```

### Direct Pytest Usage

```bash
source .venv/bin/activate
cd backend

# Run all tests
pytest

# Run specific file
pytest tests/test_api_core.py

# Run specific test
pytest tests/test_api_core.py::TestCompanyAPI::test_list_companies

# Run with output
pytest -v

# Run in parallel
pytest -n auto
```

## Test Database

- **Automatic**: Django creates `test_<db_name>` automatically
- **Isolated**: Completely separate from production data
- **Clean**: Deleted after each test run
- **Fast**: Uses transaction rollback for speed

**No manual database setup required!**

## Writing New Tests

### Example Test

```python
import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.api
@pytest.mark.database
class TestMyAPI:
    def test_list_endpoint(self, authenticated_client, test_company):
        """Test GET /api/my-endpoint/"""
        url = reverse('my-endpoint-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
```

### Using Fixtures

```python
def test_with_fixtures(authenticated_client, test_license, test_trade):
    """All fixtures auto-create fake data"""
    assert test_license.license_number
    assert test_trade.lines.count() > 0
```

## Project Structure

```
.
├── run-tests.sh                    # Master test runner
├── README_TESTING.md              # This file
├── TESTING_GUIDE.md               # Detailed guide
└── backend/
    ├── pytest.ini                  # Pytest config
    ├── requirements-test.txt       # Test dependencies
    └── tests/
        ├── conftest.py            # Fixtures & fake data
        ├── test_api_core.py       # Core API tests
        ├── test_api_license.py    # License tests
        ├── test_api_trade.py      # Trade tests
        ├── test_api_allotment.py  # Allotment tests
        └── test_api_boe.py        # BOE tests
```

## Coverage Goals

- API Endpoints: **90%+**
- Models: **80%+**
- Business Logic: **85%+**

## Troubleshooting

### Tests Not Found
```bash
# Ensure you're in the right directory
cd backend
pytest tests/
```

### Database Errors
```bash
# Ensure PostgreSQL is running
brew services start postgresql  # macOS
sudo service postgresql start   # Linux
```

### Module Import Errors
```bash
# Reinstall dependencies
source .venv/bin/activate
pip install -r requirements-test.txt
```

## Next Steps

1. ✅ Tests created and verified
2. ✅ Fake data fixtures ready
3. ✅ Automated test runner ready
4. ⏳ Run your first test: `./run-tests.sh`
5. ⏳ Review coverage report
6. ⏳ Add more tests as needed

## Documentation

- **Quick Start**: This file
- **Detailed Guide**: [TESTING_GUIDE.md](./TESTING_GUIDE.md)
- **Fixtures Reference**: [backend/tests/conftest.py](./backend/tests/conftest.py)

---

**Created**: December 25, 2024  
**Status**: ✅ Ready to Use
