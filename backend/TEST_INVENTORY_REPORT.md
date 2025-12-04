# Testing Inventory Balance Report

## Quick Test

```bash
# Start Django server
python manage.py runserver

# Test endpoints
curl http://localhost:8000/api/license/inventory-balance/

# Test specific SION norm (replace E1 with actual norm in your DB)
curl http://localhost:8000/api/license/inventory-balance/E1/

# Test Excel export
curl -O http://localhost:8000/api/license/inventory-balance/E1/export/
```

## Test with Python

```python
import requests

# List all SION norms
response = requests.get('http://localhost:8000/api/license/inventory-balance/')
print(response.json())

# Get E1 report
response = requests.get('http://localhost:8000/api/license/inventory-balance/E1/')
print(response.json())
```

## Expected Response Structure

```json
{
  "sion_norm": {
    "code": "E1",
    "description": "Biscuits (Sweet/Savory)",
    "head_norm": "Food Products"
  },
  "summary": {
    "total_licenses": 15,
    "total_items": 45,
    "total_quantity": 150000.5,
    "total_debited": 85000.25,
    "total_allotted": 25000.0,
    "total_available": 40000.25,
    "total_cif_value": 5000000.0,
    "available_cif_value": 1500000.0
  },
  "items": [...]
}
```

## Verification Checklist

- [ ] URLs are properly configured
- [ ] ViewSet returns list of SION norms
- [ ] Detail view returns report data
- [ ] Excel export downloads file
- [ ] Summary endpoint works
- [ ] Data aggregation is correct
