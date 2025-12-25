# Backend Scripts

This directory contains utility scripts used by the License Manager application.

## 📁 Active Scripts

### 1. **veg_oil_allocator.py**
**Purpose**: Vegetable oil allocation logic for license management

**Used by**:
- `license/models.py`

**Function**: `allocate_priority_oils_with_min_pomace()`
- Allocates vegetable oils based on priority
- Ensures minimum pomace requirements
- Used in license calculation logic

---

### 2. **dgft_shipping_bill.py**
**Purpose**: Fetch shipping bill details from DGFT portal

**Used by**:
- `lmanagement/tasks.py` (Celery tasks)

**Functions**:
- `get_shipping_dgft_cookies()` - Authenticate with DGFT portal
- `get_dgft_shipping_details()` - Fetch shipping bill information

**Note**: Used for automated data fetching from government portals

---

### 3. **parse_ledger.py**
**Purpose**: Parse license ledger data (original implementation)

**Used by**:
- `core/management/commands/convert_license_table.py`
- `license/views/ledger_upload.py`

**Functions**:
- `parse_license_data()` - Parse uploaded ledger files
- `create_object()` - Create database objects from parsed data

**Status**: Original implementation, still in active use

---

### 4. **ledger_parser_refactored.py**
**Purpose**: Refactored license ledger parser

**Used by**:
- `license/views_actions.py` (referenced)

**Status**: Refactored version with improved performance and error handling

**Note**: Both parse_ledger.py and ledger_parser_refactored.py coexist
- Original (parse_ledger.py) for backward compatibility
- Refactored version for new features

---

## 🗑️ Recently Removed

The following unused/obsolete scripts were removed:

1. **BOE.py** - Legacy Bill of Entry scraper (unused)
2. **ebrc.py** - Duplicate of `ebrc/scripts/ebrc.py`
3. **shipping.py** - Legacy shipping operations (no active usage)
4. **start_celery_beat.sh** - Replaced by supervisor configuration
5. **start_celery_worker.sh** - Replaced by supervisor configuration

**Reason**:
- Celery is now managed by supervisor (see `auto-deploy.sh`)
- Government portal scrapers are legacy code
- Duplicate functionality exists in other modules

---

## 📝 Usage Examples

### Vegetable Oil Allocation
```python
from backend.scripts.veg_oil_allocator import allocate_priority_oils_with_min_pomace

# Called internally by license models
result = allocate_priority_oils_with_min_pomace(license_data)
```

### DGFT Shipping Bill Fetch
```python
from backend.scripts.dgft_shipping_bill import get_shipping_dgft_cookies, get_dgft_shipping_details

# Get authentication cookies
cookies = get_shipping_dgft_cookies()

# Fetch shipping details
details = get_dgft_shipping_details(cookies, data_dict)
```

### License Ledger Parsing
```python
from scripts.parse_ledger import parse_license_data, create_object

# Parse uploaded ledger file
parsed_data = parse_license_data(file_path)

# Create database objects
create_object(parsed_data)
```

---

## 🔧 Maintenance

### Adding New Scripts
1. Place script in this directory
2. Import and use in relevant modules
3. Document in this README

### Testing Scripts
```bash
# Test import (in Django shell)
python manage.py shell
>>> from scripts.parse_ledger import parse_license_data
>>> # Test functionality
```

### Removing Scripts
1. Search for imports: `grep -r "from scripts.<script_name>" backend/`
2. Verify no active usage
3. Remove file
4. Update this README

---

## 🔒 Security Notes

⚠️  **Government Portal Credentials**
- DGFT scripts may contain hardcoded credentials
- Review before committing to public repos
- Use environment variables for sensitive data

---

## 📚 Related Documentation

- **Parent**: `/backend/` - Django backend
- **Celery Tasks**: `/backend/lmanagement/tasks.py`
- **License Models**: `/backend/license/models.py`
- **Management Commands**: `/backend/core/management/commands/`

---

**Last Updated**: December 25, 2024
**Total Scripts**: 5 (down from 11)
**Status**: Clean, actively maintained
