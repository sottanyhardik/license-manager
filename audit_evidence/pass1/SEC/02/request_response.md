# Illustrative request/response (derived directly from source: CompanySerializer
fields="__all__" + MasterDataPermission's unconditional SAFE_METHODS allow)

```
GET /api/masters/companies/
Authorization: Bearer <JWT for a user whose ONLY role is INCENTIVE_LICENSE_VIEWER>

HTTP/1.1 200 OK
{
  "count": 1,
  "results": [
    {
      "id": 42,
      "iec": "1234567890",
      "name": "Acme Exports Pvt Ltd",
      "pan": "ABCDE1234F",
      "gst_number": "27ABCDE1234F1Z5",
      "contact_person": "...",
      "phone_number": "...",
      "email": "...",
      "address_line_1": "...",
      "address_line_2": "...",
      "bill_colour": "#333",
      "bank_account_number": "000123456789",
      "bank_name": "HDFC Bank",
      "ifsc_code": "HDFC0000123",
      "logo": null,
      "signature": null,
      "stamp": null,
      "created_by": ...,
      "modified_by": ...,
      "created_on": "...",
      "modified_on": "..."
    }
  ]
}
```

This user holds no `TRADE_*`, `LICENSE_*`, or `BOE_*` role — every other
endpoint touching trade/license/BOE data correctly 403s for this user via
`TradePermission`/`LicensePermission`/`BillOfEntryPermission`. The companies
master-data endpoint does not apply any equivalent role check, so it returns
full banking/PAN/GST detail regardless.
