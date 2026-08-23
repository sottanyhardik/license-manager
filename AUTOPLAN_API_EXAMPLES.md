# Auto Plan Service — API Usage Examples

## Authentication

All requests require authentication via session cookie or Authorization header:

```bash
# Using curl with authentication
curl -H "Authorization: Bearer TOKEN" ...

# Or with session cookies (Django session-based auth)
curl -b "sessionid=SESSIONID" ...
```

## Single License Planning

### Plan a license (NEW mode — default)

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "license_id": 42,
    "mode": "NEW"
  }'
```

**Response:**
```json
{
  "license_id": 42,
  "license_number": "PLC/2024/0042",
  "mode": "NEW",
  "applicable_sions": [
    {
      "sion_id": 5,
      "sion_code": "E1",
      "status": "EXECUTED",
      "rules_executed": [
        {
          "id": 1,
          "version": 1,
          "priority": 1
        }
      ],
      "write_results": [
        {
          "license_id": 42,
          "status": "PLANNED",
          "write_results": [
            {
              "import_item_id": 101,
              "requested_quantity": "50.00",
              "unit_price": "25.50"
            },
            {
              "import_item_id": 102,
              "requested_quantity": "30.00",
              "unit_price": "28.75"
            },
            {
              "import_item_id": 103,
              "requested_quantity": "20.00",
              "unit_price": "22.00"
            }
          ]
        }
      ]
    }
  ],
  "total_results": {
    "sions_processed": 1,
    "sions_executed": 1,
    "total_lines_written": 3
  }
}
```

### Plan a license (ALL mode — force replan)

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "license_id": 42,
    "mode": "ALL"
  }'
```

With ALL mode, the license is replanned even if already planned to >=99% coverage.

### Plan a license without specifying mode

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "license_id": 42
  }'
```

Defaults to `mode: "NEW"`.

## Multiple SION Support

When a license has multiple SION norms on its export manifest, the endpoint plans all of them:

### Example response with multiple SIONs

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"license_id": 42}'
```

**Response with both E1 and E5:**
```json
{
  "license_id": 42,
  "license_number": "PLC/2024/0042",
  "mode": "NEW",
  "applicable_sions": [
    {
      "sion_id": 5,
      "sion_code": "E1",
      "status": "EXECUTED",
      "rules_executed": [{"id": 1, "version": 1, "priority": 1}],
      "write_results": [...]
    },
    {
      "sion_id": 8,
      "sion_code": "E5",
      "status": "EXECUTED",
      "rules_executed": [{"id": 2, "version": 2, "priority": 1}],
      "write_results": [...]
    }
  ],
  "total_results": {
    "sions_processed": 2,
    "sions_executed": 2,
    "total_lines_written": 8
  }
}
```

## Bulk License Planning

### Plan multiple licenses

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-licenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "license_ids": [42, 43, 44],
    "mode": "NEW"
  }'
```

**Response:**
```json
{
  "mode": "NEW",
  "licenses_processed": [
    {
      "license_id": 42,
      "license_number": "PLC/2024/0042",
      "applicable_sions": [
        {
          "sion_id": 5,
          "sion_code": "E1",
          "write_result": {
            "license_id": 42,
            "status": "PLANNED",
            "write_results": [...]
          }
        }
      ],
      "total_lines_written": 3
    },
    {
      "license_id": 43,
      "license_number": "PLC/2024/0043",
      "applicable_sions": [
        {
          "sion_id": 8,
          "sion_code": "E5",
          "write_result": {
            "license_id": 43,
            "status": "PLANNED",
            "write_results": [...]
          }
        }
      ],
      "total_lines_written": 5
    },
    {
      "license_id": 44,
      "license_number": "PLC/2024/0044",
      "applicable_sions": [...],
      "total_lines_written": 2
    }
  ],
  "summary": {
    "total_licenses": 3,
    "total_sions": 2,
    "total_lines_written": 10,
    "sion_execution_log": [
      {
        "sion_id": 5,
        "sion_code": "E1",
        "licenses_executed": 1,
        "rules_executed": [{"id": 1, "version": 1, "priority": 1}]
      },
      {
        "sion_id": 8,
        "sion_code": "E5",
        "licenses_executed": 2,
        "rules_executed": [{"id": 2, "version": 2, "priority": 1}]
      }
    ]
  }
}
```

### Plan with ALL mode

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-licenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "license_ids": [42, 43, 44],
    "mode": "ALL"
  }'
```

## Error Responses

### License not found

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"license_id": 99999}'
```

**Response (400):**
```json
{
  "error": "License 99999 not found.",
  "code": "LICENSE_NOT_FOUND"
}
```

### License has no export manifest

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"license_id": 50}'
```

**Response (400):**
```json
{
  "error": "License 50 has no export manifest.",
  "code": "NO_EXPORT_MANIFEST"
}
```

### License has no SION norms

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"license_id": 51}'
```

**Response (400):**
```json
{
  "error": "License 51 has no SION norms in export manifest.",
  "code": "NO_SION_NORMS"
}
```

### Company isolation error

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"license_id": 52}'
```

**Response (403):** (when license belongs to another user's company)
```json
{
  "error": "License 52 belongs to another company."
}
```

### Permission denied

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer VIEWER_TOKEN" \
  -d '{"license_id": 42}'
```

**Response (403):** (when user doesn't have LICENSE_MANAGER role)
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### Invalid request (missing license_ids in bulk)

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-licenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"license_ids": []}'
```

**Response (400):**
```json
{
  "license_ids": ["This list may not be empty."]
}
```

### SION planning error

```bash
curl -X POST http://localhost:8000/api/sion-planning-rules/plan-license/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"license_id": 42}'
```

**Response (400):** (when SION has no active rules)
```json
{
  "error": "The selected SION has no active saved rules.",
  "code": "PLANNING_ERROR"
}
```

## Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000/api/sion-planning-rules"
HEADERS = {
    "Authorization": "Bearer YOUR_TOKEN",
    "Content-Type": "application/json",
}

# Single license planning
response = requests.post(
    f"{BASE_URL}/plan-license/",
    json={"license_id": 42, "mode": "NEW"},
    headers=HEADERS,
)
if response.status_code == 200:
    result = response.json()
    print(f"Planned {result['license_number']}")
    print(f"Total lines written: {result['total_results']['total_lines_written']}")
else:
    print(f"Error: {response.status_code} - {response.json()}")

# Bulk license planning
response = requests.post(
    f"{BASE_URL}/plan-licenses/",
    json={"license_ids": [42, 43, 44], "mode": "ALL"},
    headers=HEADERS,
)
if response.status_code == 200:
    result = response.json()
    print(f"Planned {result['summary']['total_licenses']} licenses")
    print(f"Total lines: {result['summary']['total_lines_written']}")
    for lic in result['licenses_processed']:
        print(f"  - {lic['license_number']}: {lic['total_lines_written']} lines")
```

## JavaScript/TypeScript Client Example

```typescript
const BASE_URL = "http://localhost:8000/api/sion-planning-rules";
const HEADERS = {
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json",
};

// Single license planning
async function planLicense(licenseId: number, mode: "NEW" | "ALL" = "NEW") {
  const response = await fetch(`${BASE_URL}/plan-license/`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({ license_id: licenseId, mode }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Planning failed");
  }

  return response.json();
}

// Bulk license planning
async function planLicenses(
  licenseIds: number[],
  mode: "NEW" | "ALL" = "NEW"
) {
  const response = await fetch(`${BASE_URL}/plan-licenses/`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({ license_ids: licenseIds, mode }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || "Planning failed");
  }

  return response.json();
}

// Usage
try {
  const result = await planLicense(42);
  console.log(`Planned ${result.license_number}`);
  console.log(`Total SION norms: ${result.applicable_sions.length}`);
  console.log(`Total lines written: ${result.total_results.total_lines_written}`);
} catch (error) {
  console.error(error);
}
```

## Integration with Frontend

### Button in License Detail Page

```tsx
<button
  onClick={() => planLicense(license.id)}
  className="btn btn-primary"
  disabled={isLoading}
>
  {isLoading ? "Planning..." : "Auto Plan"}
</button>
```

### Display Planning Results

```tsx
{planResult && (
  <div className="alert alert-success">
    <h4>Planning Complete</h4>
    <p>License: {planResult.license_number}</p>
    <p>Mode: {planResult.mode}</p>
    <p>SION Norms: {planResult.applicable_sions.length}</p>
    <p>Total Lines Written: {planResult.total_results.total_lines_written}</p>
    
    {planResult.applicable_sions.map((sion) => (
      <div key={sion.sion_id} className="mt-2">
        <strong>{sion.sion_code}</strong>
        <p>Status: {sion.status}</p>
        <p>Rules Executed: {sion.rules_executed.length}</p>
      </div>
    ))}
  </div>
)}
```

## Pagination & Bulk Operations

For bulk planning with very large license lists (1000+), consider:

1. **Split into batches:**
   ```bash
   # First batch
   curl -X POST .../plan-licenses/ \
     -d '{"license_ids": [1, 2, 3, ..., 100]}'
   
   # Second batch
   curl -X POST .../plan-licenses/ \
     -d '{"license_ids": [101, 102, 103, ..., 200]}'
   ```

2. **Monitor progress via audit log:**
   ```bash
   # Query audit log for completion
   curl http://localhost:8000/api/activity-logs/ \
     -H "Authorization: Bearer TOKEN" \
     -d 'filter[module]=SION_PLANNING&filter[description]=LICENSES_PLAN_EXECUTED'
   ```

3. **Implement retry logic for failures:**
   - On timeout: Retry with fewer licenses per batch
   - On 400 error: Check specific license for issues
   - On 403 error: Verify user permissions and company isolation
