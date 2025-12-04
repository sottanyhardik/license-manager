# Expiring Licenses Report

This report shows licenses that are expiring within a specified period (default: 30 days from today) along with detailed item-level balance information for each license.

## Overview

The Expiring Licenses Report helps you:
- **Track expiring licenses** - See all licenses expiring in the next X days
- **Monitor balances** - View remaining inventory for each license (minimum balance: 100)
- **Plan ahead** - Identify licenses that need renewal or utilization
- **Item-level details** - See all items with their balance status

**Important:** Only licenses with balance CIF ≥ 100 are included in the report to focus on significant balances.

## API Endpoints

### REST API

#### 1. Get Expiring Licenses Report
```
GET /api/license/expiring-licenses/
```

**Query Parameters:**
- `days` (optional): Number of days from today (default: 30)
- `sion_norm` (optional): Filter by specific SION norm

**Example:**
```bash
# Get licenses expiring in next 30 days
curl http://localhost:8000/api/license/expiring-licenses/

# Get licenses expiring in next 7 days
curl http://localhost:8000/api/license/expiring-licenses/?days=7

# Filter by SION norm
curl http://localhost:8000/api/license/expiring-licenses/?days=30&sion_norm=E1
```

**Response:**
```json
{
  "report_period": {
    "from_date": "2025-11-27",
    "to_date": "2025-12-27",
    "days": 30
  },
  "summary": {
    "total_licenses": 15,
    "total_items": 245,
    "total_balance_cif": 2500000.50
  },
  "licenses": [
    {
      "license_number": "1234567890",
      "license_date": "2024-01-15",
      "license_expiry_date": "2025-12-15",
      "days_to_expiry": 18,
      "exporter": "ABC Company",
      "port": "Mumbai",
      "sion_norms": ["E1", "E5"],
      "export_summary": {
        "total_quantity": 50000.0,
        "total_cif_fc": 250000.0,
        "total_fob_fc": 200000.0
      },
      "balance_cif": 125000.50,
      "import_summary": {
        "total_quantity": 75000.0,
        "debited_quantity": 45000.0,
        "allotted_quantity": 15000.0,
        "available_quantity": 15000.0
      },
      "items": [
        {
          "serial_number": 1,
          "item_name": "wheat flour",
          "description": "Wheat Flour",
          "hs_code": "11010000",
          "unit": "KG",
          "quantity": 25000.0,
          "debited_quantity": 15000.0,
          "allotted_quantity": 5000.0,
          "available_quantity": 5000.0,
          "cif_fc": 50000.0,
          "available_value": 10000.0
        }
      ]
    }
  ]
}
```

#### 2. Export to Excel
```
GET /api/license/expiring-licenses/export/
```

**Query Parameters:**
- `days` (optional): Number of days from today (default: 30)
- `sion_norm` (optional): Filter by specific SION norm

**Example:**
```bash
# Export to Excel
curl -O http://localhost:8000/api/license/expiring-licenses/export/

# Export 7-day report
curl -O "http://localhost:8000/api/license/expiring-licenses/export/?days=7"
```

#### 3. Get Summary Only
```
GET /api/license/expiring-licenses/summary/
```

Returns only the summary statistics without detailed item data.

**Example:**
```bash
curl http://localhost:8000/api/license/expiring-licenses/summary/?days=30
```

**Response:**
```json
{
  "report_period": {
    "from_date": "2025-11-27",
    "to_date": "2025-12-27",
    "days": 30
  },
  "summary": {
    "total_licenses": 15,
    "total_items": 245,
    "total_balance_cif": 2500000.50
  }
}
```

### Legacy Endpoint

```
GET /api/license/reports/expiring-licenses/?days=30&format=json
GET /api/license/reports/expiring-licenses/?days=30&format=excel
```

**Parameters:**
- `days` (optional): Number of days from today (default: 30)
- `format`: 'json' or 'excel' (default: json)
- `sion_norm` (optional): Filter by SION norm

## Report Structure

### License Information
- **License Number** - License identification
- **License Date** - Original license date
- **License Expiry Date** - When license expires
- **Days to Expiry** - Calculated days remaining
- **Exporter** - Company name
- **Port** - License port
- **SION Norms** - List of associated SION norm codes

### Export Summary (per license)
- **Total Quantity** - Total export quantity
- **Total CIF FC** - Total CIF value (foreign currency)
- **Total FOB FC** - Total FOB value (foreign currency)

### Balance Information
- **Balance CIF** - Current CIF balance for license

### Import Summary (per license)
- **Total Quantity** - Original import quantity allocated
- **Debited Quantity** - Quantity used in BOEs
- **Allotted Quantity** - Quantity allocated but not used
- **Available Quantity** - Remaining balance

### Item Details (per license)
Each license shows all import items with:
- Serial Number
- Item Name
- Description
- HS Code
- Unit
- Quantity (original)
- Debited Quantity (used)
- Allotted Quantity (allocated)
- Available Quantity (remaining)
- CIF FC (value)
- Available Value (remaining value)

## Usage Examples

### Python

```python
import requests
from datetime import date, timedelta

# Get licenses expiring in next 30 days
response = requests.get('http://localhost:8000/api/license/expiring-licenses/')
data = response.json()

print(f"Found {data['summary']['total_licenses']} expiring licenses")
print(f"Total balance: ${data['summary']['total_balance_cif']:.2f}")

# Print each license
for license in data['licenses']:
    print(f"\nLicense: {license['license_number']}")
    print(f"  Expires: {license['license_expiry_date']} ({license['days_to_expiry']} days left)")
    print(f"  Balance: ${license['balance_cif']:.2f}")
    print(f"  Items: {len(license['items'])}")

    # Print items with available balance
    for item in license['items']:
        if item['available_quantity'] > 0:
            print(f"    - {item['item_name']}: {item['available_quantity']} {item['unit']} available")

# Export to Excel
response = requests.get('http://localhost:8000/api/license/expiring-licenses/export/?days=7')
with open('expiring_licenses_7days.xlsx', 'wb') as f:
    f.write(response.content)
print("Excel file saved")
```

### JavaScript/React

```javascript
// Fetch expiring licenses
const fetchExpiringLicenses = async (days = 30) => {
  const response = await fetch(`/api/license/expiring-licenses/?days=${days}`);
  const data = await response.json();
  return data;
};

// Component example
function ExpiringLicensesReport() {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    fetchExpiringLicenses(days).then(setData);
  }, [days]);

  if (!data) return <div>Loading...</div>;

  return (
    <div className="expiring-licenses-report">
      <h1>Licenses Expiring in Next {days} Days</h1>

      <div className="summary">
        <div>Total Licenses: {data.summary.total_licenses}</div>
        <div>Total Items: {data.summary.total_items}</div>
        <div>Total Balance: ${data.summary.total_balance_cif.toFixed(2)}</div>
      </div>

      <div className="filters">
        <select value={days} onChange={(e) => setDays(e.target.value)}>
          <option value="7">7 days</option>
          <option value="15">15 days</option>
          <option value="30">30 days</option>
          <option value="60">60 days</option>
        </select>

        <button onClick={() => window.open(`/api/license/expiring-licenses/export/?days=${days}`)}>
          Export to Excel
        </button>
      </div>

      {data.licenses.map(license => (
        <div key={license.license_number} className="license-card">
          <h3>
            {license.license_number}
            <span className={license.days_to_expiry < 7 ? 'urgent' : ''}>
              {license.days_to_expiry} days left
            </span>
          </h3>

          <div className="license-info">
            <div>Exporter: {license.exporter}</div>
            <div>Balance: ${license.balance_cif.toFixed(2)}</div>
            <div>SION Norms: {license.sion_norms.join(', ')}</div>
          </div>

          <table className="items-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Quantity</th>
                <th>Debited</th>
                <th>Available</th>
              </tr>
            </thead>
            <tbody>
              {license.items.map((item, idx) => (
                <tr key={idx}>
                  <td>{item.item_name}</td>
                  <td>{item.quantity.toFixed(3)} {item.unit}</td>
                  <td>{item.debited_quantity.toFixed(3)}</td>
                  <td>{item.available_quantity.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
```

### cURL Examples

```bash
# Get licenses expiring in next 30 days
curl http://localhost:8000/api/license/expiring-licenses/

# Get licenses expiring in next 7 days
curl "http://localhost:8000/api/license/expiring-licenses/?days=7"

# Filter by SION norm E1
curl "http://localhost:8000/api/license/expiring-licenses/?days=30&sion_norm=E1"

# Export to Excel
curl -O "http://localhost:8000/api/license/expiring-licenses/export/?days=30"

# Get summary only
curl "http://localhost:8000/api/license/expiring-licenses/summary/?days=15"
```

## Excel Export Format

The Excel file includes:

**Report Header:**
- Title: "Licenses Expiring in Next X Days"
- Period: From date to To date

**For Each License:**
- License header with number, expiry date, days remaining
- License details (exporter, port, SION norms, balance)
- Items table with all columns
- License summary totals

**Overall Summary:**
- Total licenses count
- Total items count
- Total balance CIF

**Styling:**
- Bold headers with colored backgrounds
- License sections clearly separated
- Auto-adjusted column widths
- Summary sections highlighted

## Use Cases

### 1. Renewal Planning
Identify licenses that need renewal soon:
```bash
curl "http://localhost:8000/api/license/expiring-licenses/?days=15"
```

### 2. Urgent Action Items
Find licenses expiring in next 7 days:
```bash
curl "http://localhost:8000/api/license/expiring-licenses/?days=7"
```

### 3. Balance Utilization
See which expiring licenses have high available balances:
```python
response = requests.get('http://localhost:8000/api/license/expiring-licenses/?days=30')
data = response.json()

high_balance = [
    lic for lic in data['licenses']
    if lic['balance_cif'] > 100000
]
print(f"Found {len(high_balance)} licenses with balance > $100,000")
```

### 4. SION-specific Monitoring
Track expiring licenses for specific SION norm:
```bash
curl "http://localhost:8000/api/license/expiring-licenses/?days=30&sion_norm=E1"
```

### 5. Weekly Reports
Generate weekly report for management:
```python
import schedule
import requests

def weekly_expiring_report():
    response = requests.get('http://localhost:8000/api/license/expiring-licenses/export/?days=30')
    filename = f'expiring_licenses_{date.today()}.xlsx'
    with open(filename, 'wb') as f:
        f.write(response.content)
    # Email the file to management
    send_email(filename)

# Run every Monday at 9 AM
schedule.every().monday.at("09:00").do(weekly_expiring_report)
```

## Report Logic

### Date Calculation
```python
today = date.today()
expiry_date = today + timedelta(days=days)

# Query licenses where:
# license_expiry_date >= today AND license_expiry_date <= expiry_date
```

### Filtering
- Only active licenses (`is_active=True`)
- Only licenses with expiry date in specified range
- Optional SION norm filter

### Balance Calculation
- Uses license's `get_balance_cif` property
- Item balances from import items model
- Aggregates quantities across all items

## Permissions

- **AllowAny** - No authentication required
- Accessible to all users

## Performance Notes

- Prefetches related models for efficiency
- Uses select_related for foreign keys
- Aggregates data at database level
- For large datasets (>100 licenses), consider pagination

## Related Reports

- [Inventory Balance Report](./INVENTORY_BALANCE_REPORT.md) - Balance by SION norm
- License Ledger - Detailed license transactions
- BOE Utilization Report - BOE-specific tracking

## Troubleshooting

### No Licenses Found
- Check date range (increase `days` parameter)
- Verify licenses have expiry dates set
- Ensure licenses are marked as active

### Missing Items
- Verify import items are linked to licenses
- Check M2M relationships between items and import records
- Ensure items have valid data

### Export Fails
- Check openpyxl is installed
- Verify file write permissions
- Check for large datasets (>1000 licenses)

## Future Enhancements

Potential improvements:
- Email notifications for urgent expiring licenses
- Automatic renewal reminders
- Integration with renewal workflow
- Historical trend analysis
- Predictive expiry alerts
