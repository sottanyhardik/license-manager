# Bill of Entry API Documentation

## Overview

The Bill of Entry API provides CRUD operations for managing Bills of Entry (BOE) with nested item details (RowDetails). This API follows the same pattern as the License API with support for nested fields.

## Base URL

```
/api/bill-of-entries/
```

## Endpoints

### 1. List Bill of Entries

**GET** `/api/bill-of-entries/`

Returns a paginated list of all Bills of Entry.

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 20)
- `search` (string): Search in bill number, invoice number, product name
- `company` (int): Filter by company ID
- `port` (int): Filter by port ID
- `bill_of_entry_date__gte` (date): Filter by BOE date from
- `bill_of_entry_date__lte` (date): Filter by BOE date to
- `is_fetch` (boolean): Filter by fetch status
- `ordering` (string): Sort field (prefix with `-` for descending)

**Example Request:**
```bash
GET /api/bill-of-entries/?search=BOE-2024&page=1&page_size=20
```

**Example Response:**
```json
{
  "count": 100,
  "next": "/api/bill-of-entries/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "company": 1,
      "company_name": "ABC Exports Pvt Ltd",
      "bill_of_entry_number": "BOE-2024-001",
      "bill_of_entry_date": "2024-01-15",
      "port": 1,
      "port_name": "Mumbai Port",
      "exchange_rate": "83.2500",
      "product_name": "Electronic Components",
      "invoice_no": "INV-2024-001",
      "invoice_date": "2024-01-10",
      "total_fc": "10000.00",
      "total_inr": "832500.00",
      "total_quantity": "500.000",
      "licenses": "LIC-2024-001, LIC-2024-002",
      "is_fetch": false,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

### 2. Retrieve Bill of Entry

**GET** `/api/bill-of-entries/{id}/`

Returns detailed information for a specific Bill of Entry including nested item details.

**Example Request:**
```bash
GET /api/bill-of-entries/1/
```

**Example Response:**
```json
{
  "id": 1,
  "company": 1,
  "company_name": "ABC Exports Pvt Ltd",
  "bill_of_entry_number": "BOE-2024-001",
  "bill_of_entry_date": "2024-01-15",
  "port": 1,
  "port_name": "Mumbai Port",
  "exchange_rate": "83.2500",
  "product_name": "Electronic Components",
  "invoice_no": "INV-2024-001",
  "invoice_date": "2024-01-10",
  "is_fetch": false,
  "failed": 0,
  "appraisement": "APP-2024-001",
  "ooc_date": "2024-01-16",
  "cha": "CHA-001",
  "comments": "Sample comments",
  "item_details": [
    {
      "id": 1,
      "row_type": "IT",
      "sr_number": 1,
      "transaction_type": "DB",
      "cif_inr": "416250.00",
      "cif_fc": "5000.00",
      "qty": "250.000",
      "license_number": "LIC-2024-001",
      "item_description": "Electronic Component A",
      "hs_code": "85371010"
    },
    {
      "id": 2,
      "row_type": "IT",
      "sr_number": 2,
      "transaction_type": "DB",
      "cif_inr": "416250.00",
      "cif_fc": "5000.00",
      "qty": "250.000",
      "license_number": "LIC-2024-002",
      "item_description": "Electronic Component B",
      "hs_code": "85371020"
    }
  ],
  "total_inr": "832500.00",
  "total_fc": "10000.00",
  "total_quantity": "500.000",
  "licenses": "LIC-2024-001, LIC-2024-002",
  "unit_price": "20.000",
  "allotments": [
    {
      "id": 1,
      "allotment_no": "ALL-2024-001",
      "allotment_date": "2024-01-14"
    }
  ],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### 3. Create Bill of Entry

**POST** `/api/bill-of-entries/`

Creates a new Bill of Entry with nested item details.

**Request Body:**
```json
{
  "company": 1,
  "bill_of_entry_number": "BOE-2024-001",
  "bill_of_entry_date": "2024-01-15",
  "port": 1,
  "exchange_rate": "83.2500",
  "product_name": "Electronic Components",
  "invoice_no": "INV-2024-001",
  "invoice_date": "2024-01-10",
  "appraisement": "APP-2024-001",
  "ooc_date": "2024-01-16",
  "cha": "CHA-001",
  "comments": "Sample comments",
  "item_details": [
    {
      "row_type": "IT",
      "sr_number": 1,
      "transaction_type": "DB",
      "cif_inr": "416250.00",
      "cif_fc": "5000.00",
      "qty": "250.000"
    },
    {
      "row_type": "IT",
      "sr_number": 2,
      "transaction_type": "DB",
      "cif_inr": "416250.00",
      "cif_fc": "5000.00",
      "qty": "250.000"
    }
  ]
}
```

**Response:** Returns the created Bill of Entry with `201 Created` status.

---

### 4. Update Bill of Entry

**PUT** `/api/bill-of-entries/{id}/`

Updates an existing Bill of Entry completely (all fields required).

**PATCH** `/api/bill-of-entries/{id}/`

Partially updates a Bill of Entry (only provided fields are updated).

**Request Body (PATCH example):**
```json
{
  "product_name": "Updated Product Name",
  "comments": "Updated comments",
  "item_details": [
    {
      "id": 1,
      "cif_inr": "500000.00",
      "cif_fc": "6000.00"
    },
    {
      "row_type": "IT",
      "sr_number": 3,
      "transaction_type": "DB",
      "cif_inr": "332500.00",
      "cif_fc": "4000.00",
      "qty": "200.000"
    }
  ]
}
```

**Notes:**
- Items with `id` will be updated
- Items without `id` will be created
- Items not included in the update will be deleted
- To preserve all items, include all existing items in the request

**Response:** Returns the updated Bill of Entry with `200 OK` status.

---

### 5. Delete Bill of Entry

**DELETE** `/api/bill-of-entries/{id}/`

Deletes a Bill of Entry and all its nested item details.

**Response:** Returns `204 No Content` status on success.

---

## Nested Field Configuration

### Item Details (RowDetails)

Each Bill of Entry can have multiple item details with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | integer | No (for create) | Item ID (read-only for existing items) |
| `row_type` | string | Yes | Row type (choices: IT, HD) |
| `sr_number` | integer | Yes | Foreign key to License Import Item |
| `transaction_type` | string | Yes | Transaction type (choices: CR, DB) |
| `cif_inr` | decimal | Yes | CIF value in INR |
| `cif_fc` | decimal | Yes | CIF value in foreign currency |
| `qty` | decimal | Yes | Quantity |
| `license_number` | string | No | License number (read-only) |
| `item_description` | string | No | Item description (read-only) |
| `hs_code` | string | No | HS Code (read-only) |

### Field Choices

**Row Type (row_type):**
- `IT` - Item
- `HD` - Header

**Transaction Type (transaction_type):**
- `CR` - Credit
- `DB` - Debit

---

## Computed Fields

The following fields are automatically calculated and are read-only:

| Field | Description |
|-------|-------------|
| `total_inr` | Sum of all item CIF values in INR |
| `total_fc` | Sum of all item CIF values in FC |
| `total_quantity` | Sum of all item quantities |
| `licenses` | Comma-separated list of associated license numbers |
| `unit_price` | Average unit price (total_fc / total_quantity) |
| `company_name` | Display name of the company |
| `port_name` | Display name of the port |

---

## Related Endpoints

### License Items Dropdown

**GET** `/api/license-items/`

Returns a list of license items for use in BOE item dropdowns.

**Query Parameters:**
- `search` (string): Search in description, license number, HS code
- `license` (int): Filter by license ID
- `hs_code` (int): Filter by HS code ID

**Example Response:**
```json
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "serial_number": 1,
      "description": "Electronic Component A",
      "license_number": "LIC-2024-001",
      "hs_code": "85371010",
      "label": "LIC-2024-001 - S.No.1 - Electronic Component A"
    }
  ]
}
```

---

## Error Responses

### 400 Bad Request

Returned when validation fails.

```json
{
  "bill_of_entry_number": ["This field is required."],
  "item_details": [
    {
      "sr_number": ["This field is required."]
    }
  ]
}
```

### 404 Not Found

Returned when the requested Bill of Entry doesn't exist.

```json
{
  "detail": "Not found."
}
```

### 500 Internal Server Error

Returned when an unexpected error occurs.

```json
{
  "detail": "An error occurred while processing your request."
}
```

---

## Usage Examples

### Create BOE with Multiple Items

```python
import requests

url = "http://localhost:8000/api/bill-of-entries/"
data = {
    "company": 1,
    "bill_of_entry_number": "BOE-2024-001",
    "bill_of_entry_date": "2024-01-15",
    "port": 1,
    "exchange_rate": "83.25",
    "product_name": "Electronic Components",
    "invoice_no": "INV-2024-001",
    "invoice_date": "2024-01-10",
    "item_details": [
        {
            "row_type": "IT",
            "sr_number": 1,
            "transaction_type": "DB",
            "cif_inr": "416250.00",
            "cif_fc": "5000.00",
            "qty": "250.000"
        },
        {
            "row_type": "IT",
            "sr_number": 2,
            "transaction_type": "DB",
            "cif_inr": "416250.00",
            "cif_fc": "5000.00",
            "qty": "250.000"
        }
    ]
}

response = requests.post(url, json=data)
print(response.json())
```

### Update BOE Item

```python
import requests

url = "http://localhost:8000/api/bill-of-entries/1/"
data = {
    "item_details": [
        {
            "id": 1,
            "cif_inr": "500000.00",
            "cif_fc": "6000.00",
            "qty": "300.000"
        }
    ]
}

response = requests.patch(url, json=data)
print(response.json())
```

### Search and Filter

```python
import requests

# Search by BOE number
url = "http://localhost:8000/api/bill-of-entries/?search=BOE-2024"
response = requests.get(url)

# Filter by date range and company
url = "http://localhost:8000/api/bill-of-entries/?company=1&bill_of_entry_date__gte=2024-01-01&bill_of_entry_date__lte=2024-12-31"
response = requests.get(url)

# Sort by date descending
url = "http://localhost:8000/api/bill-of-entries/?ordering=-bill_of_entry_date"
response = requests.get(url)
```

---

## Frontend Integration

### Example React Component

```javascript
import { useState, useEffect } from 'react';
import api from './services/api';

function BillOfEntryForm() {
  const [boe, setBoe] = useState({
    company: '',
    bill_of_entry_number: '',
    bill_of_entry_date: '',
    port: '',
    item_details: []
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await api.post('/bill-of-entries/', boe);
      console.log('BOE created:', response.data);
    } catch (error) {
      console.error('Error creating BOE:', error.response.data);
    }
  };

  const addItem = () => {
    setBoe({
      ...boe,
      item_details: [
        ...boe.item_details,
        {
          row_type: 'IT',
          sr_number: '',
          transaction_type: 'DB',
          cif_inr: '',
          cif_fc: '',
          qty: ''
        }
      ]
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* BOE fields */}
      <input
        type="text"
        value={boe.bill_of_entry_number}
        onChange={(e) => setBoe({ ...boe, bill_of_entry_number: e.target.value })}
        placeholder="BOE Number"
      />

      {/* Item details */}
      {boe.item_details.map((item, index) => (
        <div key={index}>
          <select
            value={item.sr_number}
            onChange={(e) => {
              const newItems = [...boe.item_details];
              newItems[index].sr_number = e.target.value;
              setBoe({ ...boe, item_details: newItems });
            }}
          >
            <option value="">Select License Item</option>
            {/* Populate from /api/license-items/ */}
          </select>
          {/* Other item fields */}
        </div>
      ))}

      <button type="button" onClick={addItem}>Add Item</button>
      <button type="submit">Save BOE</button>
    </form>
  );
}
```

---

## Notes

1. **Unique Constraint**: Bills of Entry are unique by the combination of `(bill_of_entry_number, bill_of_entry_date, port)`

2. **Exchange Rate**: If not provided, the exchange rate is auto-calculated from total_inr / total_fc

3. **Cascading Deletes**: Deleting a Bill of Entry will also delete all associated item details

4. **License Item Reference**: The `sr_number` field in item_details references `LicenseImportItemsModel.id`

5. **Computed Totals**: All total fields are computed from the sum of item details and are cached for performance

6. **Allotment Relationship**: Bills of Entry can be linked to multiple allotments via many-to-many relationship

---

## API Schema

The full API schema is available at:

```
GET /api/schema/
```

This provides OpenAPI/Swagger documentation for all endpoints.
