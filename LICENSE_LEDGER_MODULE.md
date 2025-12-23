# License Ledger Module

## Overview
A unified ledger module that displays available balance for both DFIA and Incentive licenses, helping you know what's available to sell.

## Features

### 1. **Unified View**
- Shows both DFIA and Incentive licenses in a single view
- Separate balance calculations for each type:
  - **DFIA**: Balance CIF $ (Total Export CIF - Allotments - BOE - Trades)
  - **Incentive**: Balance Value INR (License Value - Sold Value)

### 2. **Summary Cards**
- **DFIA Summary**: Shows total licenses, total value (USD), sold value, and available balance
- **Incentive Summary**: Shows total licenses, total value (INR), sold value, and available balance with breakdown by type (RODTEP/ROSTL/MEIS)

### 3. **Filters**
- **License Type**: Filter by ALL, DFIA, Incentive (all), RODTEP, ROSTL, MEIS
- **Min Balance**: Show only licenses with balance >= specified amount
- **Search**: Search by license number or exporter name
- **Sort By**: Latest first, Oldest first, Highest balance, Lowest balance
- **Active Only**: Show only active/non-expired licenses

### 4. **License Table**
Displays the following columns:
- Type (DFIA/RODTEP/ROSTL/MEIS)
- License Number
- License Date
- Expiry Date (with expired badge if applicable)
- Exporter Name
- Total Value (in USD for DFIA, INR for Incentive)
- Sold Value (in red)
- Available Balance (in green, bold)
- Status (Available/Partial/Sold Out)
- Actions (View Details, Create Sale)

### 5. **Quick Actions**
- **View Details**: Navigate to license detail page
- **Create Sale**: Create a new trade/sale for licenses with available balance

## API Endpoints

### Base URL: `/api/license-ledger/`

#### 1. List Licenses
```
GET /api/license-ledger/
```
Query Parameters:
- `license_type`: ALL, DFIA, INCENTIVE, RODTEP, ROSTL, MEIS
- `min_balance`: Minimum balance filter (Decimal)
- `search`: Search term
- `ordering`: Field to sort by (license_date, balance_value, license_expiry_date)
- `active_only`: true/false (default: true)
- `exporter`: Exporter ID filter

Response:
```json
[
  {
    "id": 1,
    "license_type": "DFIA",
    "license_number": "0311045493",
    "license_date": "2025-08-07",
    "license_expiry_date": "2026-08-07",
    "exporter_name": "S K IMPEX",
    "exporter_id": 1,
    "port_name": "NHAVA SHEVA SEA (INNSA1)",
    "total_value": 50000.00,
    "balance_value": 35000.00,
    "sold_value": 15000.00,
    "currency": "USD",
    "is_expired": false,
    "is_active": true,
    "sold_status": "PARTIAL"
  },
  {
    "id": 2,
    "license_type": "RODTEP",
    "license_number": "RODTEP/2024/001",
    "license_date": "2024-01-15",
    "license_expiry_date": "2026-01-15",
    "exporter_name": "ABC EXPORTS",
    "exporter_id": 2,
    "port_name": "MUMBAI",
    "total_value": 500000.00,
    "balance_value": 450000.00,
    "sold_value": 50000.00,
    "currency": "INR",
    "is_expired": false,
    "is_active": true,
    "sold_status": "PARTIAL"
  }
]
```

#### 2. Summary Statistics
```
GET /api/license-ledger/summary/
```
Response:
```json
{
  "dfia": {
    "total_licenses": 10,
    "total_value_usd": 500000.00,
    "sold_value_usd": 150000.00,
    "balance_value_usd": 350000.00
  },
  "incentive": {
    "total_licenses": 15,
    "total_value_inr": 5000000.00,
    "sold_value_inr": 1000000.00,
    "balance_value_inr": 4000000.00,
    "breakdown": {
      "RODTEP": {
        "count": 8,
        "balance": 2500000.00
      },
      "ROSTL": {
        "count": 5,
        "balance": 1200000.00
      },
      "MEIS": {
        "count": 2,
        "balance": 300000.00
      }
    }
  }
}
```

#### 3. Available for Sale
```
GET /api/license-ledger/available_for_sale/
```
Query Parameters:
- `min_balance`: Minimum balance (default: 100)

Response:
```json
{
  "count": 15,
  "min_balance_filter": 100.00,
  "licenses": [...]
}
```

## Usage

### Frontend Route
Navigate to: `/license-ledger`

### Use Cases

1. **Check Available Balance Before Selling**
   - View all licenses with their available balance
   - Filter by minimum balance to see only viable licenses for sale
   - Check expiry dates to prioritize licenses nearing expiry

2. **Track Sales Progress**
   - See sold status (Available/Partial/Sold Out)
   - Monitor sold value vs total value
   - Track balance remaining for each license

3. **Quick Trade Creation**
   - Click "Create Sale" button to directly create a new trade
   - System pre-fills license information
   - Available balance is shown for reference

4. **Portfolio Overview**
   - Summary cards show total portfolio value
   - See breakdown by license type
   - Monitor overall available balance

## Balance Calculation

### DFIA Licenses
```
Balance CIF $ = Total Export CIF $
                - Allotment $ (not having BOE)
                - BOE $ (not having Invoice)
                - Trade $
```

### Incentive Licenses (RODTEP/ROSTL/MEIS)
```
Balance Value INR = License Value INR - Sold Value INR
```

Where:
- **Sold Value** = Sum of all SALE trade amounts for this license
- **Balance Value** = Remaining value available for sale

## Auto-Update
- DFIA balances update automatically when:
  - Export items are added/modified
  - BOE debits are created/modified
  - Allotments are created/modified
  - Trade lines are created/modified/deleted

- Incentive balances update automatically when:
  - Trade sales are created/modified/deleted
  - Updates happen via signals after each transaction

## Files Created/Modified

### Backend
- `backend/license/views/ledger.py` - Main ledger viewset
- `backend/license/urls.py` - Added route registration

### Frontend
- `frontend/src/pages/LicenseLedger.jsx` - Main ledger page
- `frontend/src/App.jsx` - Added route

## Notes
- All balances are quantized to 2 decimal places
- Expired licenses can be excluded using the "Active Only" filter
- Search works on license number and exporter name
- Sorting is available on date and balance fields
