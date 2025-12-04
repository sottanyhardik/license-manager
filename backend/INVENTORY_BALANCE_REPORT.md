# Inventory Balance Report by SION Norm

This report provides detailed inventory balance information for items grouped by SION norm classification. It shows total quantities, debits, allotments, and available balances for each item across all licenses associated with a specific SION norm.

## Overview

The Inventory Balance Report helps track:
- **Total Quantity**: Original quantity allocated in licenses for each item
- **Debited Quantity**: Quantity already used/consumed through BOEs
- **Allotted Quantity**: Quantity allocated but not yet consumed
- **Available Quantity**: Remaining balance available for use
- **CIF Values**: Total and available CIF values for financial tracking

## API Endpoints

### REST API (Recommended)

#### 1. List All SION Norms
```
GET /api/license/inventory-balance/
```

Returns all SION norms with item counts.

**Response:**
```json
{
  "count": 8,
  "results": [
    {
      "norm_class": "E1",
      "description": "Biscuits (Sweet/Savory)",
      "head_norm": "Food Products",
      "item_count": 45
    },
    {
      "norm_class": "E5",
      "description": "Confectionery Products",
      "head_norm": "Food Products",
      "item_count": 38
    }
  ]
}
```

#### 2. Get Detailed Balance Report
```
GET /api/license/inventory-balance/{sion_norm}/
```

**Parameters:**
- `sion_norm` (path): SION norm class (e.g., E1, E5)
- `include_zero` (query): Include items with zero balance (default: false)

**Example:**
```bash
# Get balance report for E1
curl http://localhost:8000/api/license/inventory-balance/E1/

# Include items with zero balance
curl http://localhost:8000/api/license/inventory-balance/E1/?include_zero=true
```

**Response:**
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
    "total_quantity": 150000.500,
    "total_debited": 85000.250,
    "total_allotted": 25000.000,
    "total_available": 40000.250,
    "total_cif_value": 5000000.00,
    "available_cif_value": 1500000.00
  },
  "items": [
    {
      "item_name": "wheat flour",
      "hs_code": "11010000",
      "unit": "KG",
      "description": "Wheat Flour",
      "total_quantity": 50000.000,
      "debited_quantity": 30000.000,
      "allotted_quantity": 5000.000,
      "available_quantity": 15000.000,
      "total_cif_value": 250000.00,
      "available_cif_value": 75000.00,
      "license_count": 8
    },
    {
      "item_name": "sugar",
      "hs_code": "17011100",
      "unit": "KG",
      "description": "Refined Sugar",
      "total_quantity": 25000.000,
      "debited_quantity": 15000.000,
      "allotted_quantity": 3000.000,
      "available_quantity": 7000.000,
      "total_cif_value": 150000.00,
      "available_cif_value": 45000.00,
      "license_count": 5
    }
  ]
}
```

#### 3. Export to Excel
```
GET /api/license/inventory-balance/{sion_norm}/export/
```

Downloads an Excel file with the report data.

**Example:**
```bash
# Export E5 report to Excel
curl -O http://localhost:8000/api/license/inventory-balance/E5/export/

# With Python requests
import requests

response = requests.get('http://localhost:8000/api/license/inventory-balance/E5/export/')
with open('inventory_balance_E5.xlsx', 'wb') as f:
    f.write(response.content)
```

#### 4. Get Overall Summary
```
GET /api/license/inventory-balance/summary/
```

Returns summary statistics across all SION norms.

**Response:**
```json
{
  "total_licenses": 250,
  "total_norms": 8,
  "total_items": 320,
  "totals": {
    "total_quantity": 2500000.000,
    "debited_quantity": 1200000.000,
    "allotted_quantity": 450000.000,
    "available_quantity": 850000.000,
    "total_cif_value": 75000000.00,
    "available_cif_value": 28000000.00
  }
}
```

### Legacy Endpoint

For backward compatibility, a simple endpoint is also available:

```
GET /api/license/reports/inventory-balance/?sion_norm=E1&format=json
GET /api/license/reports/inventory-balance/?sion_norm=E1&format=excel
```

**Parameters:**
- `sion_norm` (required): SION norm class
- `format`: 'json' or 'excel' (default: json)
- `include_zero`: Include items with zero balance (default: false)

## Usage Examples

### Python

```python
import requests

# List all SION norms
response = requests.get('http://localhost:8000/api/license/inventory-balance/')
norms = response.json()['results']
print(f"Found {len(norms)} SION norms")

# Get detailed report for E1
response = requests.get('http://localhost:8000/api/license/inventory-balance/E1/')
report = response.json()

print(f"SION {report['sion_norm']['code']}: {report['sion_norm']['description']}")
print(f"Total items: {report['summary']['total_items']}")
print(f"Available quantity: {report['summary']['total_available']}")

# Export to Excel
response = requests.get('http://localhost:8000/api/license/inventory-balance/E1/export/')
with open('e1_inventory.xlsx', 'wb') as f:
    f.write(response.content)
print("Excel file saved")
```

### JavaScript/React

```javascript
// Fetch all SION norms
const response = await fetch('/api/license/inventory-balance/');
const data = await response.json();
console.log(`Found ${data.count} SION norms`);

// Get detailed report
const normResponse = await fetch('/api/license/inventory-balance/E1/');
const report = await normResponse.json();

console.log(`Items in E1: ${report.summary.total_items}`);
console.log(`Available: ${report.summary.total_available}`);

// Display items
report.items.forEach(item => {
  console.log(`${item.item_name}: ${item.available_quantity} ${item.unit}`);
});

// Export to Excel
const exportUrl = '/api/license/inventory-balance/E1/export/';
window.open(exportUrl, '_blank');
```

### cURL

```bash
# List all norms
curl http://localhost:8000/api/license/inventory-balance/

# Get E5 report
curl http://localhost:8000/api/license/inventory-balance/E5/

# Get E1 with zero balance items
curl "http://localhost:8000/api/license/inventory-balance/E1/?include_zero=true"

# Export E5 to Excel
curl -O http://localhost:8000/api/license/inventory-balance/E5/export/

# Get overall summary
curl http://localhost:8000/api/license/inventory-balance/summary/
```

## Report Logic

### Data Aggregation

The report aggregates data as follows:

1. **Find Licenses**: Identifies all active licenses that have export items with the specified SION norm
2. **Collect Items**: Gathers all import items from those licenses
3. **Group by Item**: Aggregates quantities by item name (handles M2M relationships)
4. **Calculate Balances**:
   - Total Quantity = Sum of all `quantity` fields
   - Debited Quantity = Sum of all `debited_quantity` fields
   - Allotted Quantity = Sum of all `allotted_quantity` fields
   - Available Quantity = Sum of all `available_quantity` fields
   - CIF Values = Sum of CIF and available value fields

### Relationships

```
LicenseDetailsModel (License)
  ├── LicenseExportItemModel (has SION norm)
  └── LicenseImportItemsModel
        └── ItemNameModel (M2M - items)
```

The report links licenses to items through:
1. License → Export Items → SION Norm (filter)
2. License → Import Items → Item Names (aggregate)

## Excel Export Format

The Excel file includes:

**Header Section:**
- Title: "Inventory Balance Report - SION Norm: {code} ({description})"

**Data Columns:**
1. Item Name
2. HS Code
3. Unit
4. Description
5. Total Quantity
6. Debited Quantity
7. Allotted Quantity
8. Available Quantity
9. Total CIF Value
10. Available CIF Value
11. License Count

**Summary Section:**
- Total row with aggregated values for all items

## Frontend Integration

### React Component Example

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

function InventoryBalanceReport() {
  const [norms, setNorms] = useState([]);
  const [selectedNorm, setSelectedNorm] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Load SION norms
    axios.get('/api/license/inventory-balance/')
      .then(res => setNorms(res.data.results))
      .catch(err => console.error(err));
  }, []);

  const loadReport = (normClass) => {
    setLoading(true);
    axios.get(`/api/license/inventory-balance/${normClass}/`)
      .then(res => {
        setReport(res.data);
        setSelectedNorm(normClass);
      })
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  };

  const exportToExcel = () => {
    window.open(
      `/api/license/inventory-balance/${selectedNorm}/export/`,
      '_blank'
    );
  };

  return (
    <div className="inventory-report">
      <h1>Inventory Balance Report</h1>

      <div className="norm-selector">
        <label>Select SION Norm:</label>
        <select onChange={(e) => loadReport(e.target.value)} value={selectedNorm}>
          <option value="">-- Select --</option>
          {norms.map(norm => (
            <option key={norm.norm_class} value={norm.norm_class}>
              {norm.norm_class} - {norm.description} ({norm.item_count} items)
            </option>
          ))}
        </select>
      </div>

      {loading && <div>Loading...</div>}

      {report && (
        <div className="report-content">
          <div className="report-header">
            <h2>{report.sion_norm.code}: {report.sion_norm.description}</h2>
            <button onClick={exportToExcel}>Export to Excel</button>
          </div>

          <div className="summary">
            <div>Total Items: {report.summary.total_items}</div>
            <div>Total Quantity: {report.summary.total_quantity.toFixed(3)}</div>
            <div>Available: {report.summary.total_available.toFixed(3)}</div>
            <div>CIF Value: ${report.summary.available_cif_value.toFixed(2)}</div>
          </div>

          <table className="items-table">
            <thead>
              <tr>
                <th>Item Name</th>
                <th>HS Code</th>
                <th>Total Qty</th>
                <th>Debited</th>
                <th>Allotted</th>
                <th>Available</th>
                <th>Licenses</th>
              </tr>
            </thead>
            <tbody>
              {report.items.map((item, idx) => (
                <tr key={idx}>
                  <td>{item.item_name}</td>
                  <td>{item.hs_code}</td>
                  <td>{item.total_quantity.toFixed(3)} {item.unit}</td>
                  <td>{item.debited_quantity.toFixed(3)}</td>
                  <td>{item.allotted_quantity.toFixed(3)}</td>
                  <td>{item.available_quantity.toFixed(3)}</td>
                  <td>{item.license_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default InventoryBalanceReport;
```

## Performance Considerations

- The report uses database aggregation for efficiency
- Prefetches related models to minimize queries
- For large datasets (>1000 items), consider pagination
- Excel export may be slow for very large reports (>10,000 rows)

## Troubleshooting

### Empty Report
- Verify licenses exist with the specified SION norm
- Check that licenses are marked as active (`is_active=True`)
- Ensure import items are linked to export items through licenses

### Incorrect Totals
- Verify M2M relationships between import items and item names
- Check that quantity fields are populated correctly
- Ensure debited/allotted quantities are being updated by BOE/allotment processes

### Excel Export Fails
- Check WorkbookBuilder is properly configured
- Verify openpyxl is installed
- Check file permissions if saving locally

## Related Documentation

- [License Management](./LICENSE_MANAGEMENT.md)
- [SION Norms Integration](./SION_NORMS.md)
- [BOE Tracking](./BOE_TRACKING.md)
- [Allotment System](./ALLOTMENT_SYSTEM.md)
