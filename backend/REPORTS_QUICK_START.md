# Reports Quick Start Guide

## Available Reports

### 1. Inventory Balance Report by SION Norm
Shows item-level inventory grouped by SION norm classification.

**Endpoints:**
```bash
# List all SION norms
GET /api/license/inventory-balance/

# Get report for specific norm
GET /api/license/inventory-balance/E1/

# Export to Excel
GET /api/license/inventory-balance/E1/export/

# Overall summary
GET /api/license/inventory-balance/summary/
```

**Example:**
```bash
curl http://localhost:8000/api/license/inventory-balance/E1/
```

**Use Case:** Track inventory balances for items under specific SION norm.

---

### 2. Expiring Licenses Report
Shows licenses expiring within specified period with item balances.

**Note:** Only includes licenses with balance CIF ≥ 100.

**Endpoints:**
```bash
# Get expiring licenses (default 30 days)
GET /api/license/expiring-licenses/

# Export to Excel
GET /api/license/expiring-licenses/export/

# Get summary only
GET /api/license/expiring-licenses/summary/
```

**Parameters:**
- `days` - Number of days from today (default: 30)
- `sion_norm` - Filter by SION norm (optional)

**Examples:**
```bash
# Licenses expiring in next 30 days
curl http://localhost:8000/api/license/expiring-licenses/

# Urgent: expiring in 7 days
curl "http://localhost:8000/api/license/expiring-licenses/?days=7"

# Filter by SION norm
curl "http://localhost:8000/api/license/expiring-licenses/?days=30&sion_norm=E1"

# Export to Excel
curl -O http://localhost:8000/api/license/expiring-licenses/export/
```

**Use Case:** Monitor licenses about to expire and their remaining balances.

---

## Quick Comparison

| Feature | Inventory Balance | Expiring Licenses |
|---------|------------------|-------------------|
| **Groups By** | SION Norm | License |
| **Time Filter** | No | Yes (days to expiry) |
| **Shows Balances** | Yes | Yes |
| **Item Details** | Yes | Yes |
| **Excel Export** | Yes | Yes |
| **Permissions** | AllowAny | AllowAny |

---

## Common Use Cases

### 1. Daily Operations
```bash
# Check today's critical items
curl "http://localhost:8000/api/license/expiring-licenses/?days=1"
```

### 2. Weekly Planning
```bash
# Get 7-day outlook
curl "http://localhost:8000/api/license/expiring-licenses/?days=7"
```

### 3. Monthly Review
```bash
# Download monthly report
curl -O "http://localhost:8000/api/license/expiring-licenses/export/?days=30"
```

### 4. SION-specific Analysis
```bash
# Check E1 inventory
curl http://localhost:8000/api/license/inventory-balance/E1/

# E1 licenses expiring soon
curl "http://localhost:8000/api/license/expiring-licenses/?days=15&sion_norm=E1"
```

### 5. Management Dashboard
```bash
# Get all summaries
curl http://localhost:8000/api/license/inventory-balance/summary/
curl http://localhost:8000/api/license/expiring-licenses/summary/
```

---

## Response Structure

### Inventory Balance Report
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
    "total_available": 40000.25
  },
  "items": [
    {
      "item_name": "wheat flour",
      "quantity": 50000.0,
      "available_quantity": 15000.0
    }
  ]
}
```

### Expiring Licenses Report
```json
{
  "report_period": {
    "from_date": "2025-11-27",
    "to_date": "2025-12-27",
    "days": 30
  },
  "summary": {
    "total_licenses": 15,
    "total_items": 245
  },
  "licenses": [
    {
      "license_number": "1234567890",
      "days_to_expiry": 18,
      "balance_cif": 125000.50,
      "items": [
        {
          "item_name": "wheat flour",
          "available_quantity": 5000.0
        }
      ]
    }
  ]
}
```

---

## Excel Export

Both reports support Excel export with:
- Formatted headers
- Auto-adjusted columns
- Summary sections
- Professional styling

**Download:**
```bash
# Inventory balance
curl -O http://localhost:8000/api/license/inventory-balance/E1/export/

# Expiring licenses
curl -O http://localhost:8000/api/license/expiring-licenses/export/?days=30
```

---

## Integration Examples

### Python
```python
import requests

# Get expiring licenses
response = requests.get('http://localhost:8000/api/license/expiring-licenses/?days=7')
data = response.json()

for license in data['licenses']:
    if license['days_to_expiry'] < 3:
        print(f"URGENT: {license['license_number']} expires in {license['days_to_expiry']} days")
```

### JavaScript
```javascript
// Fetch inventory balance
const response = await fetch('/api/license/inventory-balance/E1/');
const data = await response.json();

console.log(`E1 has ${data.summary.total_items} items`);
console.log(`Available: ${data.summary.total_available}`);
```

### Shell Script
```bash
#!/bin/bash
# Daily expiring licenses alert

DAYS=7
RESPONSE=$(curl -s "http://localhost:8000/api/license/expiring-licenses/summary/?days=$DAYS")
COUNT=$(echo $RESPONSE | jq '.summary.total_licenses')

if [ $COUNT -gt 0 ]; then
    echo "Alert: $COUNT licenses expiring in next $DAYS days"
    # Send email or notification
fi
```

---

## Troubleshooting

### No Data Returned
```bash
# Check if licenses exist
curl http://localhost:8000/api/license/licenses/

# Check SION norms
curl http://localhost:8000/api/license/inventory-balance/
```

### Excel Export Error (Fixed)
The MergedCell error has been fixed. Both reports now properly handle merged cells in Excel export.

### Slow Response
For large datasets, use summary endpoints:
```bash
curl http://localhost:8000/api/license/expiring-licenses/summary/
curl http://localhost:8000/api/license/inventory-balance/summary/
```

---

## Permissions

Both reports use **AllowAny** permissions:
- No authentication required
- Accessible to all users
- Suitable for dashboards and public interfaces

---

## Documentation

Full documentation available:
- [Inventory Balance Report](./INVENTORY_BALANCE_REPORT.md)
- [Expiring Licenses Report](./EXPIRING_LICENSES_REPORT.md)

---

## Status

✅ **Production Ready**
- Both reports fully implemented
- Excel export working
- AllowAny permissions configured
- Comprehensive documentation
- MergedCell bug fixed
